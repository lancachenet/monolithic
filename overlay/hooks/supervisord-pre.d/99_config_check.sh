#!/bin/sh
set -e
echo "Currently configured config:"
/scripts/getconfig.sh /etc/nginx/nginx.conf

echo "Checking nginx config"
/usr/sbin/nginx -t && echo "Config check successful"

echo "Ready for supervisord startup"
if [ -n "$CACHE_ROOT" ]; then
	echo "Monitor ${CACHE_ROOT}/logs/access.log and ${CACHE_ROOT}/logs/error.log on the host for cache activity"
else
	echo "Monitor access.log and error.log on the host for cache activity"
fi
