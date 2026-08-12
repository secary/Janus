# Janus 汇率数据与预测平台

Janus 是一个以 MySQL 为数据中心的汇率采集、训练、预测和展示应用。系统定时抓取中国银行外汇牌价，将历史汇率写入 `history` 表；预测任务基于同一批历史数据训练或加载 LSTM 模型，将未来结果写入 `prediction` 表；Spring Boot API 与静态前端直接消费这些数据。

当前支持澳大利亚元（AUD）、日元（JPY）和美元（USD），采集与预测统一使用 30 分钟时间粒度。

## 业务链路

```text
中国银行外汇牌价
        |
        v
app.fetcher 采集与解析
        |
        v
MySQL history 表
        |
        +-------------------------> Spring Boot API / 前端历史展示
        |
        v
app.methods 预处理与序列构造
        |
        v
app.tune + app.models.lstm 训练/调优
        |
        v
app/models/rate_lstm/*.pth
        |
        v
app.forecast 生成未来 7 天预测
        |
        v
MySQL prediction 表 -------------> Spring Boot API / 前端预测展示
```

数据库是业务链路的唯一数据源与输出位置：历史数据从 `history` 读取，预测结果写入 `prediction`，API 与前端不依赖本地 CSV 作为替代数据源。

## 重构后的架构

```text
.
├── janus.py                       # Python 任务统一入口
├── app/
│   ├── config.py                  # 环境变量、币种与数据源配置
│   ├── db.py                      # 建表及 history/prediction 数据访问
│   ├── fetcher.py                 # 中国银行汇率抓取、解析与入库
│   ├── methods.py                 # 历史读取、重采样、缩放、序列与评估
│   ├── tune.py                    # 模型调优注册表与币种任务编排
│   ├── train.py                   # 兼容训练入口，转发到调优流程
│   ├── forecast.py                # 模型加载、滚动预测与结果入库
│   ├── logger_config.py           # 控制台与数据库日志
│   └── models/
│       ├── base.py                # 预测模型接口
│       └── lstm.py                # RateLSTM 与超参数搜索
├── backend/                       # Spring Boot API 与静态前端
│   ├── src/main/java/             # 健康检查、数据 API、页面路由
│   ├── src/main/frontend/         # TypeScript 前端源码
│   └── src/main/resources/static/ # 编译后的页面和脚本
├── data/schema.sql                # 数据库表与币种映射初始化
├── docker/
│   ├── docker-entrypoint.sh       # worker 初始化数据库并启动 cron
│   └── docker-cron.cron           # 定时任务配置
├── e2e/
│   └── e2e_check.py               # Docker 端到端检查脚本
├── test/                          # Python 业务逻辑单元测试
├── Dockerfile                     # Python worker 镜像
├── docker-compose.yaml            # API 与 worker 编排
├── pyproject.toml                 # Python 依赖与 uv 配置
└── .env.example                   # 数据库配置示例
```

### 模块职责

| 模块 | 职责 |
| --- | --- |
| `janus.py` | 统一解析 `fetch`、`predict`、`train`、`tune` 命令，不承载业务规则 |
| `app.fetcher` | 请求中国银行页面，提取目标币种现汇卖出价并写入 `history` |
| `app.db` | 初始化 schema，封装历史数据、币种映射和预测结果的数据库操作 |
| `app.methods` | 将历史数据按 30 分钟重采样和插值，并完成模型输入构造与评估 |
| `app.tune` | 通过模型注册表调度训练/调优；当前注册模型为 `lstm` |
| `app.models` | 隔离模型实现，便于后续在统一数据链路下接入 Chronos |
| `app.forecast` | 加载每个币种的最新模型，滚动预测未来 7 天并写入 `prediction` |
| `backend` | 使用 JDBC 查询业务表，提供 API，并由 Spring Boot 托管前端页面 |

## 环境要求

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- MySQL 8.x 或兼容版本
- Java 17（本地运行 API 时需要）
- Node.js 与 npm（修改 TypeScript 前端并重新编译时需要）
- Docker 与 Docker Compose（容器部署时需要）

## 配置

从示例创建本地配置：

```bash
cp .env.example .env
```

填写数据库连接信息：

```dotenv
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=exchange
```

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `DB_USER` | MySQL 用户名 | `exchange_user` |
| `DB_PASSWORD` | MySQL 密码 | `your_password` |
| `DB_HOST` | MySQL 地址 | 本地运行使用 `127.0.0.1`；容器连接宿主机可用 `host.docker.internal` |
| `DB_PORT` | MySQL 端口 | `3306` |
| `DB_NAME` | 数据库名，需提前创建 | `exchange` |

Python worker 和 Spring Boot API 使用同一组变量。数据库不可用时，初始化、采集、训练、预测或 API 查询无法完成；不要使用空数据或本地文件替代正式数据库流程。

## 本地运行

### 1. 安装 Python 依赖

```bash
uv sync --frozen
```

### 2. 初始化数据库表

先创建 `.env` 中指定的数据库，再执行：

```bash
uv run python -m app.db
```

该命令执行 `data/schema.sql`，创建 `history`、`prediction`、`currency_map`、`thresholds`、`auto_switch` 和 `logs` 表，并写入 AUD、JPY、USD 的币种映射。建表语句可重复执行。

### 3. 执行 worker 任务

所有任务从项目根目录通过统一入口运行：

```bash
uv run python -m janus fetch
uv run python -m janus train lstm
uv run python -m janus predict
uv run python -m janus tune lstm
```

不传命令时默认执行抓取：

```bash
uv run python -m janus
```

建议首次运行遵循以下顺序：

1. 初始化数据库。
2. 持续执行 `fetch`，为各币种积累历史数据。
3. 历史记录达到训练门槛后执行 `train lstm` 或 `tune lstm`。
4. 模型生成后执行 `predict`。
5. 启动 Spring Boot 查看历史与预测结果。

当前训练/预测约束：

- 训练和预测读取最近 30 天的 `history` 数据。
- 数据按 30 分钟重采样并对缺失值插值。
- 单个币种至少需要 500 条历史记录，否则跳过该币种。
- LSTM 输入序列长度为 48，即一个自然日的半小时数据。
- 预测周期为未来 7 天，共 336 个时间点。
- `train` 当前是兼容入口，与 `tune` 使用同一套调优实现。
- `predict` 找不到币种模型时会尝试自动训练。

模型保存到 `app/models/rate_lstm/`，文件名包含模型类型、币种和年月，例如 `RateLSTM_USD_202608.pth`。

### 4. 启动 API 与前端

```bash
cd backend
./mvnw spring-boot:run
```

启动后访问：

- 首页：<http://localhost:8080/>
- 历史记录：<http://localhost:8080/history>
- 健康检查：<http://localhost:8080/api/health>

修改 `backend/src/main/frontend/` 下的 TypeScript 后，先编译到静态资源目录：

```bash
cd backend
npm install
npm run build:frontend
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | API 健康检查 |
| `GET` | `/api/latest` | 每个币种的最新历史汇率及对应预测值 |
| `GET` | `/api/history?currency=USD` | 最近 100 条历史数据，可按币种筛选 |
| `GET` | `/api/history/chart` | 历史与预测图表数据 |
| `GET` | `/api/logs/latest` | 最近 50 条采集任务日志 |
| `GET` | `/api/config` | 查询币种阈值 |
| `POST` | `/api/config` | 新增或更新币种上下限阈值 |

首页展示最新汇率、人民币换算、预测图和任务日志；`/history` 页面用于按币种查看历史记录。

## Docker 部署

Compose 当前包含两个服务：

| 服务 | 作用 | 持久化/端口 |
| --- | --- | --- |
| `api` | Spring Boot API 与静态前端 | 宿主机 `8080` |
| `worker` | 初始化数据库，运行 cron，执行抓取、训练和预测 | `data/` 与 `app/models/` 映射到宿主机 |

项目不在 Compose 中启动 MySQL。部署前必须准备可访问的数据库，并在 `.env` 中配置连接地址。容器访问宿主机 MySQL 时通常使用：

```dotenv
DB_HOST=host.docker.internal
DB_PORT=3306
```

构建并启动：

```bash
docker compose up -d --build --remove-orphans
```

查看状态与日志：

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
```

执行不写入业务数据库的 Docker 端到端检查：

```bash
python e2e/e2e_check.py
```

默认流程构建镜像、启动 API，并通过一次性 worker 容器校验 cron 和统一任务入口；它会绕过 worker 正式 entrypoint，不执行数据库初始化或抓取，因此脚本本身不会向业务表写入数据。如果执行前已有正式 worker 在运行，其 cron 仍可能独立入库，脚本会输出警告但不会擅自停止服务。需要验证真实抓取和入库链路时显式执行：

```bash
python e2e/e2e_check.py --with-write
```

写入模式会启动正式 worker、初始化数据库并执行一次抓取。脚本默认对应 Compose 服务 `worker`、`api` 和实际容器 `janus-app`、`janus-backend`。两种模式都不会删除容器或数据卷。可通过 `COMPOSE`、`WORKER_SERVICE`、`API_SERVICE`、`WORKER_CONTAINER`、`API_CONTAINER`、`API_URL` 和 `E2E_TIMEOUT` 环境变量覆盖默认配置。

手动触发 worker 任务：

```bash
docker compose exec worker python -m janus fetch
docker compose exec worker python -m janus train lstm
docker compose exec worker python -m janus predict
docker compose exec worker python -m janus tune lstm
```

worker 每次启动都会执行数据库初始化，然后安装 cron 配置。`data/` 和 `app/models/` 使用 bind mount，因此 schema 文件、采集产物和模型文件不会随容器重建丢失。

## 定时任务

定时规则位于 `docker/docker-cron.cron`：

```cron
*/30 * * * * python -m janus fetch
0 2 * * * python -m janus predict
0 3 1 * * python -m janus train
```

容器时区为 `Asia/Shanghai`，对应调度为：

- 每 30 分钟抓取一次汇率。
- 每天 02:00 生成预测。
- 每月 1 日 03:00 训练并保存模型。

实际 cron 命令会先切换到 `/app`，并显式使用 `/app/.venv/bin/python`；完整配置以 `docker/docker-cron.cron` 为准。

## 数据与模型约定

- `history` 的联合主键为 `Date + Currency`，重复采集会更新对应汇率。
- `prediction` 的联合主键为 `Date + Currency`，重复预测会更新对应预测值。
- `currency_map` 维护中文币种名与英文代码的映射。
- API、前端和 Python worker 共享同一数据库，不维护第二套历史或预测存储。
- 模型目录统一为 `app/models/`；容器内路径为 `/app/app/models/`。
- 当前实现仅注册 `lstm`。新增模型应复用 `app.db`、`app.methods`、`prediction` 表和现有 API 展示链路。

## 开发与测试

Python 业务逻辑测试位于 `test/`，按模块对应组织：

```text
test_fetcher.py  <-> app/fetcher.py
test_methods.py  <-> app/methods.py
test_forecast.py <-> app/forecast.py
test_train.py    <-> app/train.py
test_tune.py     <-> app/tune.py
test_lstm.py     <-> app/models/lstm.py
test_janus.py    <-> janus.py
```

代码修改后由开发者按需运行测试：

```bash
uv run python -m unittest discover -s test
```

前端 TypeScript 构建和 Spring Boot 测试分别在 `backend/` 中执行：

```bash
npm run build:frontend
./mvnw test
```

## 当前 GAP

1. [ ] 根据真实端到端运行结果继续修正汇率抓取、数据库写入、模型训练、预测和前端展示中的运行时问题。
2. [ ] 对现有 LSTM 与 Chronos 进行统一口径的历史回测，比较准确率、预测耗时和资源占用，再决定生产预测模型的切换方案。
3. [ ] 接入 Chronos 预测实现，并保持现有 `history`、`prediction` 数据结构及 API/前端展示链路兼容。
4. [ ] 梳理模型文件、下载缓存和预测产物的持久化策略，减少容器重建对模型运行的影响。
