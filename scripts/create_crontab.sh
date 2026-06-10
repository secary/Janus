#!/usr/bin/env zsh
# Janus 和 Jervis 的调度已内置于 janus 容器，无需宿主 crontab。
# 如需手动触发：
#   docker compose exec exchange-rate python /app/main/Janus.py
#   docker compose exec exchange-rate python /app/predictor/Jervis.py
#   docker compose exec exchange-rate python /app/predictor/tune_lstm.py
echo "Janus/Jervis 调度已由 janus 容器内 cron 管理，无需写入宿主 crontab。"
