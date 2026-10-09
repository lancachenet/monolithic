#!/bin/bash
# Reset the noslice blocklist and failure counts

set -e

echo "Resetting noslice blocklist..."

# Reset failure counts
echo '{}' > /data/cache/noslice-state.json

# Keep header lines, remove host entries
head -5 /data/cache/noslice-hosts.map > /tmp/noslice-map.tmp
mv /tmp/noslice-map.tmp /data/cache/noslice-hosts.map

# Reload nginx to pick up changes
nginx -s reload

echo "Done. Blocklist cleared and nginx reloaded."
