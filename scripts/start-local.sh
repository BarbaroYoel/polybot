#!/usr/bin/env bash
# Start both existing development servers without installing packages or changing user data.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for command in uv npm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Falta $command. Consulta los requisitos de README.md." >&2
    exit 1
  fi
done
if [[ ! -d "$ROOT/backend/.venv" || ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Instala primero las dependencias siguiendo README.md (uv sync y npm install)." >&2
  exit 1
fi

# Refuse occupied ports rather than silently selecting another frontend port or stopping a process.
python_check="$ROOT/backend/.venv/bin/python"
"$python_check" - <<'PY'
import socket
import sys

for port in (8000, 5173):
    with socket.socket() as probe:
        # Like the servers, allow a recently closed socket's TIME_WAIT entries on restart.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            print(f"El puerto {port} está ocupado. Cierra el servidor anterior antes de iniciar.", file=sys.stderr)
            sys.exit(1)
PY

backend_pid=""
frontend_pid=""
cleanup() {
  trap - EXIT INT TERM
  for pid in "$frontend_pid" "$backend_pid"; do
    if [[ -n "$pid" ]]; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(
  cd "$ROOT/backend"
  exec uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
backend_pid=$!
# Do not expose the UI until its API can answer; avoid a false connection error on first load.
"$python_check" - <<'PY'
import json
import sys
import time
from urllib.request import urlopen

deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    try:
        with urlopen("http://127.0.0.1:8000/api/v1/health", timeout=1) as response:
            if json.load(response).get("status") == "ok":
                break
    except (OSError, ValueError):
        pass
    time.sleep(0.2)
else:
    print("La API no pudo iniciar. Revisa el error del backend que aparece arriba.", file=sys.stderr)
    sys.exit(1)
PY
(
  cd "$ROOT/frontend"
  # The same-origin proxy works on localhost and through a private Codespaces forwarded port.
  export VITE_API_BASE_URL=/api/v1
  exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort
) &
frontend_pid=$!

echo "Polybot: http://localhost:5173"
echo "En Codespaces, abre el puerto 5173 con visibilidad privada. Ctrl+C detiene ambos servidores."
wait -n "$backend_pid" "$frontend_pid"
