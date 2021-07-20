#!/bin/bash

echo "Checking cache configuration"


print_confighash_warning () {
	echo ""
	echo "ABORTING STARTUP TO AVOID POTENTIALLY INVALIDATING THE CACHE"
	echo ""
	echo "If you are happy that this cache is valid with the current config changes"
	echo "please delete \`/<cache_mount>/CONFIGHASH\`"
	echo ""
	echo "See: https://lancache.net/docs/advanced/config-hash/ for more details"

}

DETECTED_CACHE_KEY=`grep proxy_cache_key /etc/nginx/sites-available/cache.conf.d/root/30_cache_key.conf | awk '{print $2}'`
NEWHASH="GENERICCACHE_VERSION=${GENERICCACHE_VERSION};CACHE_MODE=${CACHE_MODE};CACHE_SLICE_SIZE=${CACHE_SLICE_SIZE};CACHE_KEY=${DETECTED_CACHE_KEY}"

if [ -d /data/cache/cache ]; then
	echo " Detected existing cache data, checking config hash for consistency"
	if [ -f /data/cache/CONFIGHASH ]; then
		OLDHASH=`cat /data/cache/CONFIGHASH`
		if [ ${OLDHASH} != ${NEWHASH} ]; then
			echo "ERROR: Detected CONFIGHASH does not match current CONFIGHASH"
			echo " Detected: ${OLDHASH}"
			echo " Current:  ${NEWHASH}"
			print_confighash_warning ${NEWHASH}
			exit -1;
		else
			echo " CONFIGHASH matches current configuration"
		fi
	else
		echo " Could not find CONFIGHASH for existing cachedata"
		echo "  This is either an upgrade from an older instance of Lancache"
		echo "  or CONFIGHASH has been deleted intentionally"
		echo ""
		echo " Creating CONFIGHASH from current live configuration"
		echo "   Current:  ${NEWHASH}"
		echo ""
		echo "  See: https://lancache.net/docs/advanced/config-hash/ for more details"
	fi
fi

mkdir -p /data/cache/cache
echo ${NEWHASH} > /data/cache/CONFIGHASH
