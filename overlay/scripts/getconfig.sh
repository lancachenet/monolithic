#!/bin/bash

get_file_contents() {
	FILES=$1
	local FILE;
	for FILE in $FILES; do
		echo "# Including $FILE"
		local LINE
		while read LINE; do
			CLEANLINE=`echo $LINE | sed -e 's/^[[:space:]]*//g' -e 's/[[:space:]]*\$//g'`
			if [[ "$CLEANLINE" =~ ^include ]]; then
				local CL_LEN
				local INCUDE
				CL_LEN=${#CLEANLINE}-9;
				INCLUDE=${CLEANLINE:8:$CL_LEN}
				get_file_contents "$INCLUDE"
			else
				echo $LINE
			fi
		done < $FILE
		echo "# Finished including $FILE"

	done
}


main() {

	echo "NGINX CONFIG DUMP FOR $1"

	cd `dirname $1`

	get_file_contents $1

}



main `readlink -f $1`
