#!/bin/bash
set -e

# Handle CACHE_MEM_SIZE deprecation
if [[ ! -z "${CACHE_MEM_SIZE}" ]]; then
    CACHE_INDEX_SIZE=${CACHE_MEM_SIZE}
fi

# Preprocess UPSTREAM_DNS to allow for multiple resolvers using the same syntax as lancache-dns
UPSTREAM_DNS="$(echo -n "${UPSTREAM_DNS}" | sed 's/[;]/ /g')"

echo "worker_processes ${NGINX_WORKER_PROCESSES};" > /etc/nginx/workers.conf
sed -i "s/^user .*/user ${WEBUSER};/" /etc/nginx/nginx.conf
sed -i "s/CACHE_INDEX_SIZE/${CACHE_INDEX_SIZE}/"  /etc/nginx/conf.d/20_proxy_cache_path.conf
sed -i "s/CACHE_DISK_SIZE/${CACHE_DISK_SIZE}/" /etc/nginx/conf.d/20_proxy_cache_path.conf
sed -i "s/CACHE_MAX_AGE/${CACHE_MAX_AGE}/" /etc/nginx/conf.d/20_proxy_cache_path.conf
sed -i "s/CACHE_MAX_AGE/${CACHE_MAX_AGE}/"    /etc/nginx/sites-available/cache.conf.d/root/20_cache.conf
sed -i "s/slice 1m;/slice ${CACHE_SLICE_SIZE};/" /etc/nginx/sites-available/cache.conf.d/root/20_cache.conf
sed -i "s/UPSTREAM_DNS/${UPSTREAM_DNS}/"    /etc/nginx/sites-available/cache.conf.d/10_root.conf
sed -i "s/UPSTREAM_DNS/${UPSTREAM_DNS}/"    /etc/nginx/stream-available/10_sni.conf
