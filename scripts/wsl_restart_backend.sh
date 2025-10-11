#!/usr/bin/env bash
set -euo pipefail

# Usage: bash scripts/wsl_restart_backend.sh [PORT]
# Default PORT=8002. The script stops 8001, then starts the dashboard on PORT.

PORT="${1:-8002}"

# Resolve repo root from this script's location
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# Activate venv if present (no creation here to keep it fast)
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[stop] closing ports: 8001 and ${PORT}"
fuser -k -n tcp 8001 2>/dev/null || true
pkill -f "serve_upload_dashboard.py.*--port 8001" 2>/dev/null || true

fuser -k -n tcp "${PORT}" 2>/dev/null || true
pkill -f "serve_upload_dashboard.py.*--port ${PORT}" 2>/dev/null || true

sleep 0.3

LOG=".server_${PORT}.log"
PIDFILE=".server_${PORT}.pid"
: >"${LOG}"

echo "[start] launching on :${PORT}"
python3 -u scripts/serve_upload_dashboard.py --host 0.0.0.0 --port "${PORT}" >>"${LOG}" 2>&1 &
PID=$!
echo "${PID}" > "${PIDFILE}"

# Health check
ok=0
for i in $(seq 1 40); do
  if curl -fsI "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then ok=1; break; fi
  sleep 0.25
done

if [[ "${ok}" -ne 1 ]]; then
  echo "[error] server on :${PORT} did not respond. Last logs:"
  tail -n 120 "${LOG}" || true
  exit 1
fi

IP="$(hostname -I | awk '{print $1}')"
echo "[ok] WSL     : http://127.0.0.1:${PORT}/"
echo "[ok] Windows : http://${IP}:${PORT}/"
echo "[info] PID=${PID}  LOG=${LOG}  stop: fuser -k -n tcp ${PORT}"

