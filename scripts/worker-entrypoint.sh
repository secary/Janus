#!/bin/sh
set -eu

printenv > /etc/environment
/app/.venv/bin/python /app/utils/createdb.py
/app/.venv/bin/python /app/scripts/sync_crontab.py

exec cron -f
