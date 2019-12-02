#!/bin/bash

if [[ ! -z "${CACHE_DOMAIN_REPO}" ]]; then

	echo "ERROR: CACHE_DOMAIN_REPO environment variable has be deprecated in favour of CACHE_DOMAINS_REPO. Please update your config"
	exit 1

fi

