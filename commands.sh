#!/bin/sh -e

cmdname="$(basename "$0")"

usage() {
  cat << USAGE >&2
Usage:
  $cmdname [-h][-p PORT][-f FLASK_APP]

  -h
        Show this help message
  -p
	port to expose
  -f
	FLASK_APP environment variable value, points to flask entry point

  Commands to run within docker container.  Script exists to launch
  more than a single as generally desired by docker.

USAGE
  exit 1
}

if [ "$1" = "-h" ]; then
  usage
fi

while getopts "hpb:" option; do
  case "${option}" in
    h)
      usage
      ;;
    p)
      PORT=${OPTARG}
      ;;
    f)
      FLASK_APP="${OPTARG}"
      ;;
  esac
done

echo "initiate cron"
cron -f &
echo "launch gunicorn with $PORT and $FLASK_APP" 
gunicorn --bind "0.0.0.0:${PORT}" ${FLASK_APP}
