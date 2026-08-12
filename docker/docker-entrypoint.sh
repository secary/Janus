#!/bin/sh
set -eu

printenv > /etc/environment
/app/.venv/bin/python -m app.db
crontab /app/docker/docker-cron.cron

exec cron -f
