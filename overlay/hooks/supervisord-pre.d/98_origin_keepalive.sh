#!/usr/bin/env bash
set -eu
if [ "${ORIGIN_KEEPALIVE_ENABLED:-false}" != "true" ]; then
    exit 0
fi
cp -a /opt/lancache/origin-keepalive/etc/. /etc/
exec /usr/bin/python3 /scripts/refresh_cdn_upstreams.py --bootstrap
