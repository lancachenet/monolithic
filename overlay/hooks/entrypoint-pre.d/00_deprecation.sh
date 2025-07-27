#!/bin/bash

if [[ -n "${CACHE_DOMAIN_REPO}" ]]; then

	echo "ERROR: CACHE_DOMAIN_REPO environment variable has be deprecated in favour of CACHE_DOMAINS_REPO. Please update your config"
	exit 1

fi

if [[ -n "${CACHE_MEM_SIZE}" ]]; then
	echo " *** CACHE_MEM_SIZE has been deprecated in place of CACHE_INDEX_SIZE"
	echo " *** Using CACHE_MEM_SIZE as the value"
	echo " *** Please update your configuration at your earliest convenience"
fi
