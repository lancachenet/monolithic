#!/bin/bash
set -e

if [[ -n "${1}" ]]; then
	BEATTIME="${1}"
	[[ "${BEATTIME}" == 0 ]] && exit 0
else
	# shellcheck disable=SC2153
	BEATTIME="${BEAT_TIME}"
fi

if [[ -z "${BEATTIME}" || ! "${BEATTIME}" =~ ^[0-9]+$ || "${BEATTIME}" -le 0 ]]; then
	echo "Error: BEATTIME must be a positive integer." >&2
	exit 1
fi

while true; do
	sleep "${BEATTIME}"
	wget http://127.0.0.1/lancache-heartbeat -S -O - >/dev/null 2>&1
done
