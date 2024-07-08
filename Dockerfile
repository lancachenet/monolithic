FROM lancachenet/ubuntu-nginx:latest
LABEL version=3
LABEL description="Single caching container for caching game content at LAN parties."
LABEL maintainer="LanCache.Net Team <team@lancache.net>"

RUN	apt-get update							;\
	apt-get install -y jq git				;

ENV GENERICCACHE_VERSION=2 \
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

COPY overlay/ /

RUN rm /etc/nginx/sites-enabled/* /etc/nginx/stream-enabled/* ;\
    rm /etc/nginx/conf.d/gzip.conf ;\
    chmod 754  /var/log/tallylog ; \
    id -u ${WEBUSER} &> /dev/null || adduser --system --home /var/www/ --no-create-home --shell /bin/false --group --disabled-login ${WEBUSER} ;\
    chmod 755 /scripts/*		;\
	  mkdir -m 755 -p /data/cache		;\
	  mkdir -m 755 -p /data/info		;\
    mkdir -m 755 -p /data/logs		;\
    mkdir -m 755 -p /tmp/nginx/		;\
    chown -R ${WEBUSER}:${WEBUSER} /data/	;\
    mkdir -p /etc/nginx/sites-enabled	;\
    ln -s /etc/nginx/sites-available/10_cache.conf /etc/nginx/sites-enabled/10_generic.conf; \
    ln -s /etc/nginx/sites-available/20_upstream.conf /etc/nginx/sites-enabled/20_upstream.conf; \
    ln -s /etc/nginx/sites-available/30_metrics.conf /etc/nginx/sites-enabled/30_metrics.conf; \
    ln -s /etc/nginx/stream-available/10_sni.conf /etc/nginx/stream-enabled/10_sni.conf; \
    mkdir -m 755 -p /data/cachedomains		;\
    mkdir -m 755 -p /tmp/nginx

RUN git clone --depth=1 --no-single-branch https://github.com/uklans/cache-domains/ /data/cachedomains

VOLUME ["/data/logs", "/data/cache", "/data/cachedomains", "/var/www"]

EXPOSE 80 443 8080
WORKDIR /scripts
