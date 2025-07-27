#!/bin/bash

get_file_contents() {
	local FILE
	for FILE in "$@"; do
		echo "# Including ${FILE}"
		while IFS= read -r LINE; do
			CLEANLINE=$(echo "${LINE}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
			if [[ "${CLEANLINE}" =~ ^include[[:space:]]+(.+) ]]; then
				local INCLUDE_EXPR="${BASH_REMATCH[1]}"
				INCLUDE_EXPR="${INCLUDE_EXPR%;}"
				eval "get_file_contents ${INCLUDE_EXPR}"
			else
				echo "${LINE}"
			fi
		done <"${FILE}"
		echo "# Finished including ${FILE}"
	done
}

main() {
	local ABS_PATH
	ABS_PATH=$(readlink -f "${1}") || {
		echo "Failed to resolve path: ${1}" >&2
		exit 1
	}

	echo "NGINX CONFIG DUMP FOR ${ABS_PATH}"

	cd "$(dirname "${ABS_PATH}")" || exit 1

	get_file_contents "${ABS_PATH}"
}

main "${1}"
