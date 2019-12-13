#!/bin/bash

if [[ HEALTHCHECK_ENABLE == false ]]; then
	exit 0
fi


IFS=' '
mkdir -p /data/cachedomains
cd /data/cachedomains

if [ ! -f /etc/nginx/sites-enabled/20_healthcheck.conf ]; then
	ln -s /etc/nginx/sites-available/20_healthcheck.conf /etc/nginx/sites-enabled/20_healthcheck.conf
fi
sed -i "s/HEALTHCHECK_HOSTNAME/${HEALTHCHECK_HOSTNAME}/" /etc/nginx/sites-available/healthcheck.conf.d/10_healthcheck.conf

TEMP_PATH=$(mktemp -d)
OUTPUTFILE=${TEMP_PATH}/outfile.conf
echo "var cachedomains = {" >> $OUTPUTFILE
jq -r '.cache_domains | to_entries[] | .key' cache_domains.json | while read CACHE_ENTRY; do 
	# for each cache entry, find the cache indentifier
	CACHE_IDENTIFIER=$(jq -r ".cache_domains[$CACHE_ENTRY].name" cache_domains.json)
	jq -r ".cache_domains[$CACHE_ENTRY].domain_files | to_entries[] | .key" cache_domains.json | while read CACHEHOSTS_FILEID; do
		# Get the key for each domain files
		echo "	\"${CACHE_IDENTIFIER}\": [" >> $OUTPUTFILE
		jq -r ".cache_domains[$CACHE_ENTRY].domain_files[$CACHEHOSTS_FILEID]" cache_domains.json | while read CACHEHOSTS_FILENAME; do
			# Get the actual file name
			cat ${CACHEHOSTS_FILENAME} | while read CACHE_HOST; do
				# for each file in the hosts file
				# remove all whitespace (mangles comments but ensures valid config files)
				CACHE_HOST=${CACHE_HOST// /}
				if [[ ${CACHE_HOST:0:1} == '#' ]]; then
					continue;
				fi
				if [ ! "x${CACHE_HOST}" == "x" ]; then
					echo "		\"${CACHE_HOST}\"," >> $OUTPUTFILE
				fi
			done
		done
		echo "	]," >> $OUTPUTFILE
	done
done
echo "};" >> $OUTPUTFILE
if [[ -d .git ]]; then
	giturl=$(git config --get remote.origin.url)
	echo "var urltext='Running with hostlist from <a target=\"_blank\" href=\"${giturl}\">${giturl}</a>';" >> $OUTPUTFILE;
else
	echo "var urltext='Running with an external hostlist that is not git controlled';" >> $OUTPUTFILE;
fi
cat $OUTPUTFILE
cp $OUTPUTFILE /var/www/healthcheck/sites.js
rm -rf $TEMP_PATH
