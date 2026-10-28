#!/usr/bin/env bash
set -eu
if [ "${ORIGIN_KEEPALIVE_ENABLED:-false}" != "true" ]; then
    exit 0
fi
exec /usr/bin/python3 /scripts/refresh_cdn_upstreams.py --watch
