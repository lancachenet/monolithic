#!/bin/bash

CACHE_DIR="/data/cache/cache"

if [ -d "${CACHE_DIR}" ]; then
	echo "Running fast permissions check"

	if [[ "${FORCE_PERMS_CHECK}" == "true" ]]; then
		echo "FORCE_PERMS_CHECK is set, proceeding with full permissions fix"
	elif ! find "${CACHE_DIR}" -mindepth 1 ! -user "${WEBUSER}" | read -r; then
		echo "Fast permissions check successful, if you have any permissions error try running with -e FORCE_PERMS_CHECK=true"
		exit 0
	else
		echo "Some files are not owned by ${WEBUSER}"
	fi

	echo "Doing full checking of permissions (This WILL take a long time on large caches)..."
	find /data \! -user "${WEBUSER}" -exec chown "${WEBUSER}:" '{}' +
	echo "Permissions ok"
fi
