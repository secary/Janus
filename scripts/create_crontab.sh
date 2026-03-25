#!/usr/bin/env zsh

# 项目根目录（scripts 的上一级）
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$BASE_DIR/scripts"

# 三个脚本绝对路径
JANUS_SCRIPT="$SCRIPTS_DIR/run_janus.sh"
JERVIS_SCRIPT="$SCRIPTS_DIR/run_jervis.sh"
TUNE_SCRIPT="$SCRIPTS_DIR/run_tune_lstm.sh"

# cron 任务
CRON_JOB1="*/30 * * * * $JANUS_SCRIPT"
CRON_JOB2="0 2 * * * $JERVIS_SCRIPT"
CRON_JOB3="0 3 1 * * $TUNE_SCRIPT"

# 去重 + 添加
(
  crontab -l 2>/dev/null | grep -v "run_janus.sh" \
                          | grep -v "run_jervis.sh" \
                          | grep -v "run_tune_lstm.sh"
  echo "$CRON_JOB1"
  echo "$CRON_JOB2"
  echo "$CRON_JOB3"
) | crontab -

echo "✅ crontab 已更新："
crontab -l