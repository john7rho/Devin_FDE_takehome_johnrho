#!/usr/bin/env bash
# Keep this Mac (and its display) awake so long-running local servers / demos
# don't get suspended. macOS `caffeinate` does the work.
#
#   ./scripts/keep_awake.sh         # stay awake until you press Ctrl-C
#   ./scripts/keep_awake.sh 7200    # stay awake for 7200 seconds, then exit
#
# Flags: -d display, -i idle system, -m disk, -s system (on AC power), -u user-active.
set -euo pipefail

if [[ -n "${1:-}" ]]; then
  echo "☕ Keeping this Mac awake for ${1}s (Ctrl-C to stop early)..."
  exec caffeinate -dimsu -t "$1"
fi

echo "☕ Keeping this Mac awake (display + system) until you press Ctrl-C..."
exec caffeinate -dimsu
