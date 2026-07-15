# 💱 Janus
🌐 Hi！私の名前はJanus!

本项目是一个端到端的汇率数据平台，涵盖汇率抓取、数据库存储、LSTM 预测、模型训练与可视化展示，当前使用 uv 管理 Python 任务依赖，并通过 Docker Compose 拆分 Spring Boot API/前端、后台 worker 与可选 MySQL。

<!-- TOC -->
- [💱 Janus](#-janus)
  - [📁 项目结构](#-项目结构)
  - [⚙️ 功能概述](#️-功能概述)
  - [🚀 快速开始](#-快速开始)
    - [1. 安装依赖](#1-安装依赖)
    - [2. 配置环境变量](#2-配置环境变量)
    - [3. 初始化数据库](#3-初始化数据库)
    - [4. 本地运行](#4-本地运行)
  - [🐳 Docker 部署](#-docker-部署)
  - [📈 Web 页面预览](#-web-页面预览)
  - [🕒 定时任务支持](#-定时任务支持)
<!-- TOC -->

---

## 📁 项目结构

```text
.
├── .env.example
├── Dockerfile                # Python worker 镜像
├── README.md
├── backend/                  # Spring Boot API / 集成前端
│   ├── Dockerfile
│   └── src/
├── config/                  # 共享配置
├── data/                    # 数据文件
├── docker-compose.yaml      # 容器编排
├── docker-compose.mysql.yaml # 可选 MySQL 编排
├── pyproject.toml           # uv 依赖配置
├── uv.lock                  # uv 锁文件
├── main/
│   └── Janus.py
├── predictor/
│   ├── Jervis.py
│   └── tune_lstm.py
└── scripts/
    ├── init_db.py
    ├── init_db_schema.sql
    ├── worker-entrypoint.sh
    └── exchange-rate.cron
```

---

## ⚙️ 功能概述

| 模块 | 功能 |
|------|------|
| `backend` | 提供 Spring Boot API 与集成前端 |
| `Janus` | 抓取中国银行汇率并写入数据库 |
| `Jervis` | 执行汇率预测，并复用 worker 镜像执行训练任务 |
| `scripts/exchange-rate.cron` | worker 容器内 cron 调度 |
| `docker-compose.yaml` | 默认编排 API/前端与后台 worker |
| `docker-compose.mysql.yaml` | 按需追加 MySQL 容器 |

---

## 🚀 快速开始

### 1. 安装依赖

安装 uv 后同步锁定依赖：

```bash
uv sync --frozen
```

### 2. 配置环境变量

参考 `.env.example` 创建 `.env`：

```env
DB_USER=root
DB_PASSWORD=your_root_password
DB_HOST=host.docker.internal
DB_PORT=3306
DB_NAME=exchange
```

默认 Docker Compose 会使用 `.env` 里的 `DB_HOST`、`DB_PORT` 连接外部数据库。如果容器访问宿主机数据库，`DB_HOST` 可使用：

```env
DB_HOST=host.docker.internal
```

### 3. 初始化数据库

```bash
uv run python scripts/init_db.py
```

### 4. 本地运行

```bash
uv run python main/Janus.py                  # 抓取汇率
uv run python predictor/Jervis.py            # 执行预测
uv run python predictor/tune_lstm.py         # 训练模型
```

---

## 🐳 Docker 部署

默认只构建并启动 API/前端与 worker，数据库使用 `.env` 指向的外部 MySQL：

```bash
docker compose up -d --build --remove-orphans
```

如果需要同时启动容器内 MySQL，叠加 MySQL compose 文件：

```bash
docker compose -f docker-compose.yaml -f docker-compose.mysql.yaml up -d --build --remove-orphans
```

查看日志：

```bash
docker compose logs -f api
docker compose logs -f worker
```

启用容器 MySQL 时再查看数据库日志：

```bash
docker compose logs -f mysql
```

手动执行任务：

```bash
docker compose exec worker python /app/main/Janus.py
docker compose exec worker python /app/predictor/Jervis.py
docker compose exec worker python /app/predictor/tune_lstm.py
```

当前容器拆分：

- `api`：运行 Spring Boot，集成 API 与前端，宿主机通过 `localhost:8080` 访问
- `worker`：启动时初始化数据库表，然后运行 Python cron，定时执行抓取、预测和训练
- `mysql`：可选服务，启用后提供独立 MySQL 数据库，宿主机通过 `localhost:3307` 访问

当前已启用的宿主机文件映射：

- `data/`：抓取数据文件
- `predictor/models/`：训练后的模型文件
- `mysql-data`：启用容器 MySQL 时使用的 MySQL 数据卷

修改 Spring Boot 或 Python 代码后需要重新构建对应镜像；数据库、数据文件和模型会通过 volume 保留。

---

## 📈 Web 页面预览

当前 Docker 默认启动 Spring Boot API/前端容器，可先验证健康检查：

```text
http://localhost:8080/api/health
```

前端页面由 Spring Boot `api` 容器统一承载：

- `index.html`：显示最新汇率、换算、预测图与实时日志
- `history.html`：查看历史汇率数据
- `admin.html`：管理定时任务频率与启用状态

API/前端容器默认访问地址：

```text
http://localhost:8080/
```

如果你修改了 Spring Boot 代码，重新构建并启动：

```bash
docker compose up -d --build --remove-orphans
```

前端静态目录已挂载到 `api` 容器，修改
`backend/src/main/resources/static/*` 后刷新浏览器即可生效，无需重构
`api` 容器。修改 `backend/src/main/frontend/*.ts` 后需要先编译：

```bash
cd backend
npm run build:frontend
```

需要持续监听 TypeScript 变更时：

```bash
cd backend
npm run watch:frontend
```

---

## 🕒 定时任务支持

项目使用容器内 `cron`。当前调度配置写入数据库 `schedule_config` 表，worker 启动时会读取该表生成 crontab，并通过 `scripts/sync_crontab.py` 每分钟刷新一次。

如果应用数据库用户没有建表权限，需要先用数据库管理员账号执行 `scripts/init_db_schema.sql`，创建 Janus 所需表并写入默认配置。

默认调度规则为：

```cron
*/30 * * * * /app/.venv/bin/python /app/main/Janus.py
0 2 * * * /app/.venv/bin/python /app/predictor/Jervis.py
0 3 1 * * /app/.venv/bin/python /app/predictor/tune_lstm.py
```

分别对应：

- 每 30 分钟抓取一次汇率
- 每天 2 点执行一次预测
- 每月 1 日 3 点执行一次训练

管理页面：

```text
http://localhost:8080/admin
```

保存配置后，worker 会在下一次同步时把 `schedule_config` 写入容器内 crontab。

---
