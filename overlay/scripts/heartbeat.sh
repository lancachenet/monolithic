#!/bin/bash
set -e
if [[ "$1" == "" ]]; then
	BEATTIME=${BEAT_TIME}
else
	BEATTIME=$1
	if [[ "$1" == 0 ]]; then 
		exit 0;
	fi
fi


while [ 1 ]; do
    sleep $BEATTIME;
	wget http://127.0.0.1/lancache-heartbeat -S -O - > /dev/null 2>&1
done
