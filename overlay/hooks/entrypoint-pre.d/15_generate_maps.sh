#!/bin/bash

IFS=' '
mkdir -p /data/cachedomains
echo "Bootstrapping Monolithic from ${CACHE_DOMAINS_REPO}"

export GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
cd /data/cachedomains
if [[ ! -d .git ]]; then
	git clone ${CACHE_DOMAINS_REPO} .
fi

if [[ "${NOFETCH:-false}" != "true" ]]; then
	# Disable error checking whilst we attempt to get latest
	set +e
	git remote set-url origin ${CACHE_DOMAINS_REPO}
	git fetch origin || echo "Failed to update from remote, using local copy of cache_domains"
	git reset --hard origin/${CACHE_DOMAINS_BRANCH}
	# Reenable error checking
	set -e
fi

TEMP_PATH=$(mktemp -d)
OUTPUTFILE=${TEMP_PATH}/outfile.conf
echo "map \"\$http_user_agent£££\$http_host\" \$cacheidentifier {" >> $OUTPUTFILE
echo "    default \$http_host;" >> $OUTPUTFILE
echo "    ~Valve\\/Steam\\ HTTP\\ Client\\ 1\.0£££.* steam;" >> $OUTPUTFILE
#Next line probably no longer needed as we are now regexing to victory
#echo "    hostnames;" >> $OUTPUTFILE
jq -r '.cache_domains | to_entries[] | .key' cache_domains.json | while read CACHE_ENTRY; do 
	#for each cache entry, find the cache indentifier
	CACHE_IDENTIFIER=$(jq -r ".cache_domains[$CACHE_ENTRY].name" cache_domains.json)
	jq -r ".cache_domains[$CACHE_ENTRY].domain_files | to_entries[] | .key" cache_domains.json | while read CACHEHOSTS_FILEID; do
		#Get the key for each domain files
		jq -r ".cache_domains[$CACHE_ENTRY].domain_files[$CACHEHOSTS_FILEID]" cache_domains.json | while read CACHEHOSTS_FILENAME; do
			#Get the actual file name
			echo Reading cache ${CACHE_IDENTIFIER} from ${CACHEHOSTS_FILENAME}
			cat ${CACHEHOSTS_FILENAME} | while read CACHE_HOST; do
				#for each file in the hosts file
				#remove all whitespace (mangles comments but ensures valid config files)
				echo "host: $CACHE_HOST"
				CACHE_HOST=${CACHE_HOST// /}
				echo "new host: $CACHE_HOST"
				if [ ! "x${CACHE_HOST}" == "x" ]; then
					#Use sed to replace . with \. and * with .*
					REGEX_CACHE_HOST=$(sed -e "s#\.#\\\.#g" -e "s#\*#\.\*#g" <<< ${CACHE_HOST})
					echo "    ~.*£££.*?${REGEX_CACHE_HOST} ${CACHE_IDENTIFIER};" >> $OUTPUTFILE
				fi
			done
		done
	done
done
echo "}" >> $OUTPUTFILE
cat $OUTPUTFILE
cp $OUTPUTFILE /etc/nginx/conf.d/30_maps.conf
rm -rf $TEMP_PATH
