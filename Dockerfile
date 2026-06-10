FROM ghcr.io/astral-sh/uv:0.11.5 AS uv

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

ENV TZ=Asia/Shanghai \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY config/ /app/config/
COPY utils/ /app/utils/
COPY main/ /app/main/
COPY predictor/ /app/predictor/
COPY web/ /app/web/
COPY data/ /app/data/
COPY scripts/ /app/scripts/

RUN crontab /app/scripts/exchange-rate.cron \
    && chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 5000

CMD ["/app/scripts/docker-entrypoint.sh"]
