#!/bin/sh
set -eu

printenv > /etc/environment
crontab /app/scripts/exchange-rate.cron
cron

exec /app/.venv/bin/python /app/web/Javelin.py
