#!/usr/bin/env bash
# plane-export-state.sh — Export current Plane state
# Calls the Python script which handles the actual export logic
# (avoids bash string escaping issues with Python f-strings)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
python3 "$SCRIPT_DIR/plane_export.py"
echo "[export] Done"