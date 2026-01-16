#!/bin/bash
set -e
pageload1=`curl http://ping1.lancache.net/api/timezone/ETC/GMT --resolve ping1.lancache.net:80:127.0.0.1`
sleep 2
pageload2=`curl http://ping1.lancache.net/api/timezone/ETC/GMT --resolve ping1.lancache.net:80:127.0.0.1`
sleep 2
pageload3=`curl http://ping2.lancache.net/api/timezone/ETC/GMT --resolve ping2.lancache.net:80:127.0.0.1`
sleep 2
pageload4=`curl http://ping2.lancache.net/api/timezone/ETC/GMT --resolve ping2.lancache.net:80:127.0.0.1`

if [ "$pageload1" == "$pageload2" ]; then
	if [ "$pageload3" == "$pageload4" ]; then
		if [ "$pageload1" == "$pageload3" ]; then
			#In monolithic pages 1+3 should be different as there is no map for this test case
			echo "Error caching test page, pages 1+3 are identical"

			echo "pageload1:"
			echo $pageload1

			echo "pageload3:"
			echo $pageload3

			exit 3
		else
			echo "Succesfully Cached"
			exit 0
		fi

	else
		echo "Error caching test page, pages 3+4 differed"


		echo "pageload3:"
		echo $pageload3

		echo "pageload4:"
		echo $pageload4

		exit 2
	fi

else
	echo "Error caching test page, pages 1+2 differed"


	echo "pageload1:"
	echo $pageload1

	echo "pageload2:"
	echo $pageload2

	exit 1
fi
