#!/bin/sh -e

cmdname="$(basename "$0")"

usage() {
  cat << USAGE >&2
Usage:
  $cmdname [-h] PORT FLASK_APP

  -h
        Show this help message

  PORT: port to expose
  FLASK_APP: environment variable value, points to flask entry point

  Commands to run within docker container.  Script exists to launch
  more than a single as generally desired by docker.

USAGE
  exit 1
}

if [ "$1" = "-h" ]; then
  usage
fi

PORT=$1
FLASK_APP=$2

echo "initiate cron"
cron -f &
echo "launch gunicorn with $PORT and $FLASK_APP" 
gunicorn --bind "0.0.0.0:${PORT}" ${FLASK_APP}
