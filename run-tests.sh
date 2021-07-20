#!/bin/bash

if [[ "$@" == *" -- "* ]]; then
	SD_LOGLEVEL="-e SUPERVISORD_LOGLEVEL=INFO"
else
	SD_LOGLEVEL="-- -e SUPERVISORD_LOGLEVEL=INFO"
fi

curl -fsSL https://raw.githubusercontent.com/lancachenet/test-suite/master/dgoss-tests.sh | bash -s -- --imagename="lancachenet/monolithic:goss-test" $@ $SD_LOGLEVEL
