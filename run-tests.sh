#!/bin/bash

SD_LOGLEVEL=(-- -e SUPERVISORD_LOGLEVEL=INFO)

for arg in "$@"; do
	[[ "${arg}" == "--" ]] && SD_LOGLEVEL=(-e SUPERVISORD_LOGLEVEL=INFO) && break
done

curl -fsSL https://raw.githubusercontent.com/lancachenet/test-suite/master/dgoss-tests.sh | bash -s -- --imagename="lancachenet/monolithic:goss-test" "$@" "${SD_LOGLEVEL[@]}" -e GOSS_LOGLEVEL="DEBUG"
