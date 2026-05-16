#!/usr/bin/env bash

ENV_PATH=$1

SCRIPT_DIR="$(dirname "$0")"
CACHE_DIR="$SCRIPT_DIR/../.cache"

cd "$SCRIPT_DIR/.."

docker build -t pcb_map .
docker rm pcb_map_locations
docker run -d --restart=always --env-file $ENV_PATH -v "$CACHE_DIR:/app/.cache" --name pcb_map_locations pcb_map
