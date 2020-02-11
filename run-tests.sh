#!/bin/bash
which goss

if [ $? -ne 0 ]; then
	echo "Please install goss from https://goss.rocks/install"
	echo "For a quick auto install run the following"
	echo "curl -fsSL https://goss.rocks/install | sh"
	exit $?
fi

GOSS_WAIT_OPS="-r 60s -s 1s"

docker build --tag lancachenet/monolithic:goss-test .
case $1 in
  circleci)
	shift;
	mkdir -p ./reports/goss
	if [[ "$1" == "keepimage" ]]; then
		KEEPIMAGE=true
		shift
	fi
	export GOSS_OPTS="$GOSS_OPTS --format junit"
	export CONTAINER_LOG_OUTPUT="reports/goss/docker.log"
	dgoss run $@ lancachenet/monolithic:goss-test > reports/goss/report.xml
	#store result for exit code
	RESULT=$?
	#Ensure non blank docker.log
	echo \
"Container Output:
$(cat reports/goss/docker.log)" \
	> reports/goss/docker.log
	#delete the junk that goss currently outputs :(
	sed -i '0,/^</d' reports/goss/report.xml
	#remove invalid system-err outputs from junit output so circleci can read it
	sed -i '/<system-err>.*<\/system-err>/d' reports/goss/report.xml
    ;;
  docker)
	shift;
	if [[ "$1" == "keepimage" ]]; then
		KEEPIMAGE=true
		shift
	fi
	docker run --name monolithic-goss-test $@ lancachenet/monolithic:goss-test
	docker stop monolithic-goss-test
	docker rm monolithic-goss-test
	RESULT=$?
	;;
  edit)
	shift;
	if [[ "$1" == "keepimage" ]]; then
		KEEPIMAGE=true
		shift
	fi
	dgoss edit $@ lancachenet/monolithic:goss-test
	RESULT=$?
    ;;
  *)
	if [[ "$1" == "keepimage" ]]; then
		KEEPIMAGE=true
		shift
	fi
	dgoss run $@ lancachenet/monolithic:goss-test
	RESULT=$?
    ;;
esac
[[ "$KEEPIMAGE" == "true" ]] || docker rmi lancachenet/monolithic:goss-test

exit $RESULT
