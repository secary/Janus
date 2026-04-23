#!/usr/bin/env zsh
# Janus 和 Jervis 的调度已内置于各自容器，无需宿主 crontab。
# 如需手动触发：
#   docker compose run --rm janus python /Janus/main/Janus.py
#   docker compose run --rm jervis python /Jervis/predictor/Jervis.py
#   docker compose run --rm jervis python /Jervis/predictor/tune_lstm.py
echo "ℹ️  Janus/Jervis 调度已由容器内 cron 管理，无需写入宿主 crontab。"
