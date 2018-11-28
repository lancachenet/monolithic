#!/bin/bash

IFS=' '
 cd /data/cachedomains
export GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
if [[ ! -d .git ]]; then
	git clone ${CACHE_DOMAIN_REPO} .
fi
git fetch origin
git reset --hard origin/master
 path=$(mktemp -d)
outputfile=${path}/outfile.conf
 echo "map \$http_host \$cacheidentifier {" >> $outputfile
echo "    hostnames;" >> $outputfile
echo "    default \$http_host;" >> $outputfile
 jq -r '.cache_domains | to_entries[] | .key' cache_domains.json | while read entry; do 
	key=$(jq -r ".cache_domains[$entry].name" cache_domains.json)
	jq -r ".cache_domains[$entry].domain_files | to_entries[] | .key" cache_domains.json | while read fileid; do
		jq -r ".cache_domains[$entry].domain_files[$fileid]" cache_domains.json | while read filename; do
			echo "" >> $outputfile
			cat ${filename} | while read fileentry; do
				# Ignore comments
				case "$var" in
				    \#*) continue ;;
				esac
				if grep -q "$fileentry" $outputfile; then
					continue
				fi
				echo "    ${fileentry} ${key};" >> $outputfile
			done
		done
	done
done
echo "}" >> $outputfile
cat $outputfile
cp $outputfile /etc/nginx/conf.d/20_maps.conf
rm -rf $path
