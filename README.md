# 💱 Exchange Rate

本项目是一个端到端的人民币汇率数据平台，涵盖定时抓取、LSTM 预测、模型训练与 Web 可视化，全部通过 Docker 容器化运行。

<!-- TOC -->
- [💱 Exchange Rate](#-exchange-rate)
  - [📁 项目结构](#-项目结构)
  - [⚙️ 架构概述](#️-架构概述)
  - [🚀 快速开始](#-快速开始)
    - [1. 配置环境变量](#1-配置环境变量)
    - [2. 初始化数据库](#2-初始化数据库)
    - [3. 本地运行（不使用 Docker）](#3-本地运行不使用-docker)
  - [🐳 Docker 部署](#-docker-部署)
  - [📈 Web 页面与 API](#-web-页面与-api)
  - [🕒 定时任务](#-定时任务)
<!-- TOC -->

---

## 📁 项目结构

```text
.
├── .env.example
├── .env.prod
├── config/                  # 共享配置（数据库、货币列表）
├── data/                    # CSV 历史数据
├── docker-compose.yaml      # 容器编排（三服务）
├── dockerfile.janus         # 爬虫镜像
├── dockerfile.javelin       # Web 镜像
├── dockerfile.jervis        # 预测镜像
├── main/
│   ├── Janus.py             # 爬虫主程序
│   ├── janus.cron           # 容器内 cron 规则
│   ├── entrypoint.sh        # 容器启动入口
│   └── requirements.txt
├── predictor/
│   ├── Jervis.py            # 预测主程序
│   ├── tune_lstm.py         # 模型训练脚本
│   ├── methods.py           # 数据预处理与模型加载
│   ├── models/
│   │   ├── base.py
│   │   ├── lstm.py          # RateLSTM 模型定义
│   │   └── RateLSTM/        # 训练好的模型权重（.pth）
│   ├── jervis.cron          # 容器内 cron 规则
│   ├── entrypoint.sh        # 容器启动入口
│   └── requirements.txt
├── scripts/
│   └── create_crontab.sh    # 宿主机 cron 写入脚本（备用）
├── utils/
│   ├── models.py            # SQLAlchemy ORM 模型
│   └── createdb.py          # 数据库初始化
└── web/
    ├── Javelin.py           # Flask 应用入口
    ├── requirements.txt
    └── app/
        ├── routes.py        # API 路由
        └── templates/
            ├── index.html   # 主页（最新汇率 + 预测图）
            └── history.html # 历史汇率页
```

---

## ⚙️ 架构概述

项目由三个独立服务组成，均以 Docker 容器运行：

| 服务 | 容器名 | 职责 |
|------|--------|------|
| **Janus** | `janus` | 每 30 分钟从中国银行抓取人民币兑 AUD / JPY / USD 汇率，写入 MySQL |
| **Jervis** | `jervis` | 每日凌晨使用 LSTM 模型预测未来 7 天汇率；每月重新训练模型 |
| **Javelin** | `javelin` | Flask Web 服务，提供可视化页面与 REST API，对外暴露 5024 端口 |

数据库使用 MySQL，由宿主机或外部容器提供（不在 compose 内管理）。

**LSTM 模型：** `RateLSTM`，双层 LSTM（hidden_dim=64，dropout=0.2），以 48 步（对应 1 天 30 分钟粒度）为序列窗口，预测未来 7 天共 336 个时间步的汇率走势。

---

## 🚀 快速开始

### 1. 配置环境变量

复制示例文件并填写数据库连接信息：

```bash
cp .env.example .env
```

```env
DB_USER=exchange_user
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_NAME=exchange
```

容器访问宿主机数据库时，将 `DB_HOST` 改为：

```env
DB_HOST=host.docker.internal
```

### 2. 初始化数据库

```bash
python utils/createdb.py
```

### 3. 本地运行（不使用 Docker）

按模块分别安装依赖：

```bash
pip install -r main/requirements.txt
pip install -r predictor/requirements.txt
pip install -r web/requirements.txt
```

逐个启动：

```bash
python main/Janus.py          # 手动触发一次抓取
python predictor/Jervis.py    # 手动触发一次预测
python predictor/tune_lstm.py # 手动触发一次训练
python web/Javelin.py         # 启动 Flask（localhost:5000）
```

---

## 🐳 Docker 部署

构建所有镜像：

```bash
docker compose build
```

启动全部服务：

```bash
docker compose up -d
```

三个容器均配置为 `restart: always`，容器内置 cron 负责定时调度，无需宿主机干预。

手动触发任务（不等待 cron）：

```bash
docker compose exec janus python /Janus/main/Janus.py
docker compose exec jervis python /Jervis/predictor/Jervis.py
docker compose exec jervis python /Jervis/predictor/tune_lstm.py
```

热更新（修改以下路径后只需重启 Web 容器，无需重新构建）：

- `web/app/routes.py`
- `web/app/templates/`

```bash
docker compose restart javelin
```

---

## 📈 Web 页面与 API

默认访问地址：`http://localhost:5024/`

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页：最新汇率卡片、汇率换算、历史 + 预测折线图、实时日志 |
| `/history` | GET | 历史汇率数据浏览页 |
| `/api/latest` | GET | 每种货币最新汇率及对应预测值 |
| `/api/history` | GET | 历史汇率列表（支持 `?currency=USD` 筛选） |
| `/api/history/chart` | GET | 最近 20 条历史点 + 未来预测点（用于图表渲染） |
| `/api/logs/latest` | GET | 最新 50 条 Janus 爬虫日志 |
| `/api/config` | GET | 查看各货币汇率告警阈值 |
| `/api/config` | POST | 更新告警阈值（`{"Currency": "USD", "Upper": 7.5, "Lower": 7.0}`） |

---

## 🕒 定时任务

定时调度由各容器内部的 cron 驱动，通过 `entrypoint.sh` 在容器启动时加载 `.cron` 文件：

| 容器 | 规则 | 执行内容 |
|------|------|---------|
| `janus` | `*/30 * * * *` | 抓取中国银行汇率写入数据库 |
| `jervis` | `0 2 * * *` | LSTM 预测未来 7 天汇率 |
| `jervis` | `0 3 1 * *` | 重新训练 LSTM 模型 |

---
