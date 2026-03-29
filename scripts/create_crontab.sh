#!/usr/bin/env zsh

# 项目根目录（scripts 的上一级）
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_COMPOSE_BIN="$(command -v docker)"

if [ -z "$DOCKER_COMPOSE_BIN" ]; then
  echo "❌ 未找到 docker 命令，无法写入 crontab"
  exit 1
fi

CRON_PREFIX="cd $BASE_DIR && $DOCKER_COMPOSE_BIN compose"

# cron 任务
CRON_JOB1="*/30 * * * * $CRON_PREFIX run --rm janus"
CRON_JOB2="0 2 * * 1 $CRON_PREFIX run --rm jervis python /Jervis/predictor/Jervis.py"
CRON_JOB3="0 3 1 * * $CRON_PREFIX run --rm jervis python /Jervis/predictor/tune_lstm.py"

# 去重 + 添加
(
  crontab -l 2>/dev/null | grep -v "compose run --rm janus" \
                          | grep -v "compose run --rm jervis" \
                          | grep -v "tune_lstm.py"
  echo "$CRON_JOB1"
  echo "$CRON_JOB2"
  echo "$CRON_JOB3"
) | crontab -

echo "✅ crontab 已更新："
crontab -l
