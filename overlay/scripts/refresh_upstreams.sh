#!/bin/bash
set -e

REFRESH_INTERVAL=${UPSTREAM_REFRESH_INTERVAL:-1h}

if [[ "$REFRESH_INTERVAL" == "0" ]]; then
    echo "Upstream refresh disabled (UPSTREAM_REFRESH_INTERVAL=0)"
    exit 0
fi

echo "Starting upstream refresh loop (interval: $REFRESH_INTERVAL)"

while true; do
    sleep $REFRESH_INTERVAL

    echo "[$(date)] Refreshing upstream pools..."

    if /hooks/entrypoint-pre.d/16_generate_upstream_keepalive.sh > /dev/null 2>&1; then
        nginx -s reload
        echo "[$(date)] Upstream pools refreshed and nginx reloaded"
    else
        echo "[$(date)] Upstream generation failed, skipping reload"
    fi
done
