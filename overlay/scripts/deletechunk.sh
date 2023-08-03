#!/bin/bash
cd /data/cache

if [[ "x$1" == "x" ]]; then
    echo "Usage: docker exec <container_name> /scripts/deletechunk.sh <chunk path>"
    echo ""
    echo "container is usually lancache_monolithic_1"
    return
else
    find /data/cache -type f -exec awk 'FNR>2 {nextfile} "$1" {rm FILENAME ; nextfile }' '{}' +
fi

