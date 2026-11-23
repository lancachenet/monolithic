#!/bin/bash
set -eo pipefail

MAP_FILE="/etc/nginx/maps.d/30_maps.conf"

echo "Validating generated nginx maps"

if [[ ! -s "${MAP_FILE}" ]]; then
	echo "ERROR: Expected generated maps file '${MAP_FILE}' is missing or empty"
	exit 1
fi

if ! grep -Eq '^[[:space:]]*map[[:space:]].*\$cacheidentifier[[:space:]]*\{' "${MAP_FILE}"; then
	echo "ERROR: Missing \$cacheidentifier map definition in ${MAP_FILE}"
	exit 1
fi

if ! grep -Eq '^[[:space:]]*map[[:space:]].*\$noslice_host[[:space:]]*\{' "${MAP_FILE}"; then
	echo "ERROR: Missing \$noslice_host map definition in ${MAP_FILE}"
	exit 1
fi

echo "Generated maps validation passed"
