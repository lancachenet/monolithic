FROM lancachenet/generic:latest
MAINTAINER LanCache.Net Team <team@lancache.net>

ENV GENERICCACHE_VERSION 2
ENV WEBUSER www-data
ENV CACHE_MEM_SIZE 500m
ENV CACHE_DISK_SIZE 1000000m
ENV CACHE_MAX_AGE 3560d
ENV UPSTREAM_DNS 8.8.8.8 8.8.4.4
ENV BEAT_TIME 1h
ENV LOGFILE_RETENTION 3560
ENV CACHE_DOMAINS_REPO https://github.com/uklans/cache-domains.git
ENV CACHE_DOMAINS_BRANCH master
ENV UPSTREAM_DNS 8.8.8.8 8.8.4.4
ENV NGINX_WORKER_PROCESSES auto
ENV HEALTHCHECK_HOSTNAME lancache.lan
ENV HEALTHCHECK_ENABLE true

RUN mkdir -m 755 -p /data/cachedomains		;\
	mkdir -m 755 -p /tmp/nginx				;\
	apt-get update							;\
	apt-get install -y jq git				;

COPY overlay/ /

VOLUME ["/data/logs", "/data/cache", "/data/cachedomains", "/var/www"]

EXPOSE 80
WORKDIR /scripts
