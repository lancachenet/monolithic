#!/bin/bash

cd /data/cache

find /data/cache -type f -exec awk 'FNR>2 {nextfile} "$1" {print FILENAME ; nextfile }' '{}' +