#!/usr/bin/env bash
# BashBrowse — fully inside the Termux terminal. No Chrome, browser app, or local server.

set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python is required. Install it with: pkg install python"
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/bashbrowse.py" ]]; then
    echo "Could not find $SCRIPT_DIR/bashbrowse.py"
    echo "Update the repository with: git pull origin main"
    exit 1
fi

exec python3 "$SCRIPT_DIR/bashbrowse.py"
