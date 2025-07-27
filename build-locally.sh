#!/bin/bash
#This script build the monolithic image locally, for cases like the raspberry pi, which operates on arm64 architecture, which isn't officially supported.

PURPLEBOLD="$(tput setf 5 bold)"

printf "%sBuilding temporary modified Ubuntu image:\n" "${PURPLEBOLD}"
docker build -t lancachenet/ubuntu:latest --progress tty https://github.com/lancachenet/ubuntu.git

printf "%sBuilding temporary Ubuntu-Nginx image:\n" "${PURPLEBOLD}"
docker build -t lancachenet/ubuntu-nginx:latest --progress tty https://github.com/lancachenet/ubuntu-nginx.git

printf "%sBuilding Monolithic image:\n" "${PURPLEBOLD}"
docker build -t lancachenet/monolithic:latest --progress tty .

printf "%sRemoving temporary Ubuntu image:\n" "${PURPLEBOLD}"
docker rmi lancachenet/ubuntu

printf "%sRemoving temporary Ubuntu-Nginx image:\n" "${PURPLEBOLD}"
docker rmi lancachenet/ubuntu-nginx

printf "%sCompleted local build. Image now available as lancachenet/monolithic:latest\n" "${PURPLEBOLD}"
docker image ls lancachenet/monolithic:latest
