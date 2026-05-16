#!/usr/bin/env bash
set -e
set -o pipefail

usage() {
  echo "Usage: $0 --output <file> [options]"
  echo ""
  echo "Options:"
  echo "  -o, --output   Output file path (Required)"
  echo "  -p, --profile  Firefox profile directory name to load from (Optional)"
  echo "  -r, --remote   Remote host to scp files to (Optional)"
  echo "  -h, --help     Show help"
  exit 1
}

OUTPUT=""
PROFILE_NAME=""
REMOTE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -o|--output)
      OUTPUT="$2"
      shift 2
      ;;
    -p|--profile)
      PROFILE_NAME="$2"
      shift 2
      ;;
    -r|--remote)
      REMOTE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: Unknown argument $1" >&2
      usage
      ;;
  esac
done

if [ -z "$OUTPUT" ]; then
  echo "Error: --output argument is required." >&2
  usage
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

COOKIE_PATH="$TMP_DIR/cookie.txt"

if [ -z "$PROFILE_NAME" ]; then
    echo "Loading cookies from firefox default profile..."
else
    echo "Loading cookies from firefox $PROFILE_NAME profile..."
fi

uvx --from "git+https://github.com/axlan/pycookiecheat@firefox-profile" pycookiecheat \
    -b firefox ${PROFILE_NAME:+--firefox-profile="$PROFILE_NAME"} -o "$COOKIE_PATH" maps.google.com

if [ -z "$REMOTE" ]; then
    mv "$COOKIE_PATH" "$OUTPUT"
else
    echo "Sending cookies to $REMOTE..."
    scp "$COOKIE_PATH" "$REMOTE:$OUTPUT"
fi
