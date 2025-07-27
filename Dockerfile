# hadolint ignore=DL3007
FROM lancachenet/ubuntu-nginx:latest

LABEL org.opencontainers.image.version=3
LABEL org.opencontainers.image.description="Single container for caching game content at LAN parties."
LABEL org.opencontainers.image.authors="LanCache.Net Team <team@lancache.net>"

SHELL ["/bin/bash", "-c"]

# hadolint ignore=DL3008
RUN	<<EOF
  apt-get update
  apt-get install -y ca-certificates git jq --no-install-recommends
  apt-get -y clean
  rm -rf /var/lib/apt/lists/*
EOF

ENV \
  GENERICCACHE_VERSION=2 \
  CACHE_MODE=monolithic \
  WEBUSER=www-data \
  CACHE_INDEX_SIZE=500m \
  CACHE_DISK_SIZE=1000g \
  MIN_FREE_DISK=10g \
  CACHE_MAX_AGE=3560d \
  CACHE_SLICE_SIZE=1m \
  UPSTREAM_DNS="8.8.8.8 8.8.4.4" \
  BEAT_TIME=1h \
  LOGFILE_RETENTION=3560 \
  CACHE_DOMAINS_REPO="https://github.com/uklans/cache-domains.git" \
  CACHE_DOMAINS_BRANCH=master \
  NGINX_WORKER_PROCESSES=auto \
  NGINX_LOG_FORMAT=cachelog

COPY --link overlay/ /

RUN <<EOF
  id -u ${WEBUSER} &> /dev/null || adduser --system --home /var/www/ --no-create-home --shell /bin/false --group --disabled-login ${WEBUSER}
  mkdir -p /etc/nginx/sites-enabled /data/{cache,cachedomains,info,logs} /tmp/nginx
  rm /etc/nginx/sites-enabled/* /etc/nginx/stream-enabled/* /etc/nginx/conf.d/gzip.conf
  chown -R ${WEBUSER}: /data/
  chmod 754 /var/log/tallylog
  for file in sites-available/10_cache.conf sites-available/20_upstream.conf sites-available/30_metrics.conf stream-available/10_sni.conf; do
    ln -s "/etc/nginx/${file}" "/etc/nginx/${file/available/enabled}"
  done
EOF

RUN <<EOF
git clone --depth=1 --no-single-branch https://github.com/uklans/cache-domains/ /data/cachedomains
EOF

VOLUME ["/data/logs", "/data/cache", "/data/cachedomains", "/var/www"]

EXPOSE 80 443 8080
WORKDIR /scripts
