#!/bin/sh
set -e

SOURCE_KEY="/run/secrets/workplayvpn_backend"
SAFE_DIR="/root/.ssh"
SAFE_KEY="$SAFE_DIR/workplayvpn_backend"

mkdir -p "$SAFE_DIR"

if [ -f "$SOURCE_KEY" ]; then
    cp "$SOURCE_KEY" "$SAFE_KEY"
    chmod 600 "$SAFE_KEY"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000