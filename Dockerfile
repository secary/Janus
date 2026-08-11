FROM python:3.12-slim

WORKDIR /app

ARG DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
ARG PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG UV_VERSION=0.11.5

RUN set -eux; \
    . /etc/os-release; \
    printf 'Types: deb\nURIs: %s\nSuites: %s %s-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: %s\nSuites: %s-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' \
        "$DEBIAN_MIRROR" "$VERSION_CODENAME" "$VERSION_CODENAME" \
        "$DEBIAN_SECURITY_MIRROR" "$VERSION_CODENAME" \
        > /etc/apt/sources.list.d/debian.sources; \
    rm -f /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --index-url "$PYPI_INDEX_URL" "uv==$UV_VERSION"

ENV TZ=Asia/Shanghai \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-install-project --no-dev

COPY config/ /app/config/
COPY utils/ /app/utils/
COPY main/ /app/main/
 COPY forecasting/ /app/forecasting/
RUN mkdir -p /app/data /app/forecasting/models
COPY scripts/ /app/scripts/

RUN chmod +x /app/scripts/worker-entrypoint.sh

CMD ["sh", "/app/scripts/worker-entrypoint.sh"]
