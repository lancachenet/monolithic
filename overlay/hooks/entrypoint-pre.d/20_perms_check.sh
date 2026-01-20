#!/bin/bash
if [ -d "/data/cache/cache" ]; then
	echo "Running fast permissions check - listing files that fail permission check:"
	su - ${WEBUSER} -c 'find /data/cache/cache -maxdepth 1 ! -readable -o ! -writable | grep . && exit 1 || exit 0'
	if [[ $? -eq 0 || "$FORCE_PERMS_CHECK" == "true" ]]; then
		echo "Doing full checking of permissions (This WILL take a long time on large caches)..."
		find /data \! -user ${WEBUSER} -exec chown ${WEBUSER}:${WEBUSER} '{}' +
		echo "Permissions ok"
	else
		echo "Fast permissions check successful, if you have any permissions error try running with -e FORCE_PERMS_CHECK = true"
	fi
fi
