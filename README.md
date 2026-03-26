# 💱 Janus
🌐 Hi！私の名前はJanus!

本项目是一个端到端的汇率数据平台，涵盖汇率抓取、数据库存储、LSTM 预测、模型训练与可视化展示，当前支持 Docker 化运行与宿主机 cron 调度。

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
├── .env.prod
├── README.md
├── config/                  # 共享配置
├── data/                    # 数据文件
├── docker-compose.yaml      # 容器编排
├── dockerfile.janus         # 爬虫镜像
├── dockerfile.javelin       # Web 镜像
├── dockerfile.jervis        # 预测镜像
├── main/
│   ├── Janus.py
│   └── requirements.txt
├── predictor/
│   ├── Jervis.py
│   ├── tune_lstm.py
│   └── requirements.txt
├── scripts/
│   └── create_crontab.sh
├── utils/                   # ORM / 数据库工具
└── web/
    ├── Javelin.py
    ├── requirements.txt
    └── app/
```

---

## ⚙️ 功能概述

| 模块 | 功能 |
|------|------|
| `Janus` | 抓取中国银行汇率并写入数据库 |
| `Jervis` | 执行汇率预测，并复用同一镜像执行训练任务 |
| `Javelin` | 提供基于 Flask 的可视化页面与 API |
| `scripts/create_crontab.sh` | 自动写入宿主机 cron 调度 |
| `docker-compose.yaml` | 编排 Web 服务与任务型容器 |

---

## 🚀 快速开始

### 1. 安装依赖

按模块分别安装：

```bash
pip install -r main/requirements.txt
pip install -r predictor/requirements.txt
pip install -r web/requirements.txt
```

### 2. 配置环境变量

参考 `.env.example` 或 `.env.prod`：

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
python utils/createdb.py
```

### 4. 本地运行

```bash
python main/Janus.py                  # 抓取汇率
python predictor/Jervis.py            # 执行预测
python predictor/tune_lstm.py         # 训练模型
python web/Javelin.py                 # 启动 Flask 前端
```

---

## 🐳 Docker 部署

构建镜像：

```bash
docker compose build
```

启动 Web 常驻服务：

```bash
docker compose up -d javelin
```

手动执行任务型容器：

```bash
docker compose run --rm janus
docker compose run --rm jervis python /Jervis/predictor/Jervis.py
docker compose run --rm jervis python /Jervis/predictor/tune_lstm.py
```

当前容器策略：

- `javelin` 为常驻 Web 服务
- `janus` 为任务型容器
- `jervis` 为任务型容器，同时承担预测与训练

当前已启用的宿主机文件映射：

- `javelin`
  - `web/app/routes.py`
  - `web/app/templates/`
- `janus`
  - `main/`
  - `config/`
  - `utils/`
- `jervis`
  - `predictor/`
  - `config/`
  - `utils/`

因此修改这些目录下的代码后，通常无需重新 build 镜像。

---

## 📈 Web 页面预览

- `index.html`：显示最新汇率、换算、预测图与实时日志
- `history.html`：查看历史汇率数据

默认访问地址：

```text
http://localhost:5024/
```

如果你修改了 `web/app/routes.py` 或 `web/app/templates/`，通常只需要重启 Web 容器：

```bash
docker compose restart javelin
```

---

## 🕒 定时任务支持

项目当前推荐使用宿主机 `cron` 调用 Docker 任务容器。

自动写入 cron：

```bash
zsh scripts/create_crontab.sh
```

当前调度规则为：

```cron
*/30 * * * * cd /path/to/Janus && docker compose run --rm janus
0 2 * * * cd /path/to/Janus && docker compose run --rm jervis python /Jervis/predictor/Jervis.py
0 3 1 * * cd /path/to/Janus && docker compose run --rm jervis python /Jervis/predictor/tune_lstm.py
```

分别对应：

- 每 30 分钟抓取一次汇率
- 每天 2 点执行一次预测
- 每月 1 日 3 点执行一次训练

---
