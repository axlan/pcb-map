#!/usr/bin/env bash
set -e
set -o pipefail

PIO_ENV_BIN="$HOME/.platformio/penv/bin"
if [ ! -d "$PIO_ENV_BIN" ]; then
  echo "Error: PlatformIO Python environment bin directory not found at $PIO_ENV_BIN" >&2
  echo "Please ensure PlatformIO Core is installed and configured correctly." >&2
  exit 1
fi
export PATH="$HOME/.platformio/penv/bin:$PATH"

SCRIPT_DIR="$(dirname "$0")"
FIRMWARE_DIR="$SCRIPT_DIR/../firmware"
cd "$FIRMWARE_DIR"

pio run -t upload --upload-port pcb-map.local
