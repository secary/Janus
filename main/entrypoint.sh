#!/bin/sh
# pass container env vars to cron jobs
printenv >> /etc/environment
exec cron -f
