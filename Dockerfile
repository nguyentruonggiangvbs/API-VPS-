FROM python:3.12-alpine3.21

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk add --no-cache \
      curl \
      docker-cli \
      docker-cli-compose \
      git \
      gzip \
      procps \
      rsync \
      tar \
      tini \
      util-linux \
    && apk add --no-cache --virtual .build-deps \
      gcc \
      linux-headers \
      musl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY app.py .
COPY vps_control ./vps_control
COPY dashboard ./dashboard
COPY config ./config
COPY scripts/git-askpass.sh /usr/local/bin/api-vps-git-askpass

RUN chmod 0755 /usr/local/bin/api-vps-git-askpass \
    && mkdir -p /data/backups /data/jobs /data/logs

EXPOSE 9000

HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=4 \
  CMD wget -q -O /dev/null http://127.0.0.1:9000/api/health || exit 1

ENTRYPOINT ["/sbin/tini","--"]
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","9000","--proxy-headers","--forwarded-allow-ips=127.0.0.1"]
