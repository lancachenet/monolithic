#!/bin/bash
set -e
pageload1=`curl http://www.worldtimeapi.org/api/timezone/ETC/GMT --resolve www.worldtimeapi.org:80:127.0.0.1`
sleep 5
pageload2=`curl http://www.worldtimeapi.org/api/timezone/ETC/GMT --resolve www.worldtimeapi.org:80:127.0.0.1`
sleep 5
pageload3=`curl http://worldtimeapi.org/api/timezone/ETC/GMT --resolve worldtimeapi.org:80:127.0.0.1`
sleep 5
pageload4=`curl http://worldtimeapi.org/api/timezone/ETC/GMT --resolve worldtimeapi.org:80:127.0.0.1`
if [ "$pageload1" == "$pageload2" ]; then
	if [ "$pageload3" == "$pageload4" ]; then
		if [ "$pageload1" == "$pageload4" ]; then
			#In monolithic pages 1+3 should be different as there is no map for this test case
			echo "Error caching test page, pages 1+3 are identical"
			exit -3
		else
			echo "Succesfully Cached"
			exit 0
		fi

	else
		echo "Error caching test page, pages 3+4 differed"
		exit -2
	fi

else
	echo "Error caching test page, pages 1+2 differed"
	exit -1
fi
