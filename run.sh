#!/usr/bin/env bash
# Roblox UI Forge — local runner.
set -e
cd "$(dirname "$0")"

PY="${PY:-python3}"
if ! "$PY" -c "import fastapi, PIL, uvicorn" 2>/dev/null; then
  echo "[forge] installing dependencies…"
  "$PY" -m pip install -r requirements.txt
fi

echo "[forge] starting web UI on http://0.0.0.0:${FORGE_PORT:-8000}"
exec "$PY" app.py --host 0.0.0.0 --port "${FORGE_PORT:-8000}"
