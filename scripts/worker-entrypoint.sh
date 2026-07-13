#!/bin/sh
set -eu

printenv > /etc/environment
/app/.venv/bin/python /app/utils/createdb.py
crontab /app/scripts/exchange-rate.cron

exec cron -f
