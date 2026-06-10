# 💱 Janus
🌐 Hi！私の名前はJanus!

本项目是一个端到端的汇率数据平台，涵盖汇率抓取、数据库存储、LSTM 预测、模型训练与可视化展示，当前使用 uv 管理依赖，并通过单个 Docker 容器运行 Web 与定时任务。

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
├── Dockerfile
├── README.md
├── config/                  # 共享配置
├── data/                    # 数据文件
├── docker-compose.yaml      # 容器编排
├── pyproject.toml           # uv 依赖配置
├── uv.lock                  # uv 锁文件
├── main/
│   └── Janus.py
├── predictor/
│   ├── Jervis.py
│   └── tune_lstm.py
├── scripts/
│   ├── docker-entrypoint.sh
│   └── exchange-rate.cron
├── utils/                   # ORM / 数据库工具
└── web/
    ├── Javelin.py
    └── app/
```

---

## ⚙️ 功能概述

| 模块 | 功能 |
|------|------|
| `Janus` | 抓取中国银行汇率并写入数据库 |
| `Jervis` | 执行汇率预测，并复用同一镜像执行训练任务 |
| `Javelin` | 提供基于 Flask 的可视化页面与 API |
| `scripts/exchange-rate.cron` | 容器内 cron 调度 |
| `docker-compose.yaml` | 编排单个 Web + 任务容器 |

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
DB_USER=exchange_user
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_NAME=exchange
```

如果容器访问宿主机数据库，`DB_HOST` 可使用：

```env
DB_HOST=host.docker.internal
```

### 3. 初始化数据库

```bash
uv run python utils/createdb.py
```

### 4. 本地运行

```bash
uv run python main/Janus.py                  # 抓取汇率
uv run python predictor/Jervis.py            # 执行预测
uv run python predictor/tune_lstm.py         # 训练模型
uv run python web/Javelin.py                 # 启动 Flask 前端
```

---

## 🐳 Docker 部署

构建并启动单容器：

```bash
docker compose up -d --build --remove-orphans
```

查看日志：

```bash
docker compose logs -f exchange-rate
```

手动执行任务：

```bash
docker compose exec exchange-rate python /app/main/Janus.py
docker compose exec exchange-rate python /app/predictor/Jervis.py
docker compose exec exchange-rate python /app/predictor/tune_lstm.py
```

当前容器策略：

- `exchange-rate` 是唯一 Compose 服务，容器名保持为 `janus`
- Flask 前端以前台进程运行
- cron 在同一容器内定时执行抓取、预测和训练

当前已启用的宿主机文件映射：

- `data/`：抓取数据文件
- `predictor/models/`：训练后的模型文件

修改代码后需要重新构建镜像；数据和模型会通过 volume 保留。

---

## 📈 Web 页面预览

- `index.html`：显示最新汇率、换算、预测图与实时日志
- `history.html`：查看历史汇率数据

默认访问地址：

```text
http://localhost:5024/
```

如果你修改了 Web 代码，重新构建并启动：

```bash
docker compose up -d --build --remove-orphans
```

---

## 🕒 定时任务支持

项目使用容器内 `cron`，规则位于 `scripts/exchange-rate.cron`。

当前调度规则为：

```cron
*/30 * * * * /app/.venv/bin/python /app/main/Janus.py
0 2 * * * /app/.venv/bin/python /app/predictor/Jervis.py
0 3 1 * * /app/.venv/bin/python /app/predictor/tune_lstm.py
```

分别对应：

- 每 30 分钟抓取一次汇率
- 每天 2 点执行一次预测
- 每月 1 日 3 点执行一次训练

---
