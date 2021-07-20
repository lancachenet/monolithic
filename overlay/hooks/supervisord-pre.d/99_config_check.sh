#!/bin/sh
set -e
echo "Currently configured config:"
/scripts/getconfig.sh /etc/nginx/nginx.conf

echo "Checking nginx config"
/usr/sbin/nginx -t

 [ $? -ne 0 ] || echo "Config check successful"
