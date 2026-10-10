#!/usr/bin/env bash
# Start local development from any working directory.
#
# Startup order:
#   1. Install backend dependencies from the uv lockfile.
#   2. Install frontend dependencies from the frozen Bun lockfile.
#   3. Export, regenerate, and verify the API contracts.
#   4. With --local-db only: start Docker Postgres, wait, migrate, and seed.
#   5. Start the API with reload, then the frontend dev server.
#
# Ordinary startup uses the database already configured in the environment.
# It does not migrate, seed, switch databases, or edit the shared environment file.
# ./run.sh --local-db prepares an isolated Docker Postgres instead.

# A host that invokes this file with sh still needs bash (process groups and traps).
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

# The script's directory is the repository root, so the command works from anywhere.
# Strip the file name in bash so this does not depend on the dirname program.
source_path="${BASH_SOURCE[0]}"
if [[ "$source_path" != */* ]]; then
  source_path="./${source_path}"
fi
ROOT="$(cd "${source_path%/*}" && pwd)"
cd "$ROOT"

# These match the Vite proxy (frontend/vite.config.ts) and the frontend dev port.
API_PORT=8000
WEB_PORT=5173

# Leaders of the two server process groups. Empty until that server is started.
API_PID=""
WEB_PID=""

# Monitor mode gives each background server its own process group.
# Notifications stay off so a stopped server does not print a job-control line.
set -m
set +b

# Signal only the process groups this script started, then reap their leaders.
# Unrelated processes are never selected, and the database volume is not touched.
stop_owned_trees() {
  local pid
  local tries
  set +e
  for pid in "$API_PID" "$WEB_PID"; do
    if [[ -n "$pid" ]]; then
      # Negative pid: the whole process group, including reload workers.
      kill -TERM -- "-${pid}" 2>/dev/null
    fi
  done
  for pid in "$API_PID" "$WEB_PID"; do
    if [[ -z "$pid" ]]; then
      continue
    fi
    tries=0
    while [[ "$tries" -lt 20 ]]; do
      if child_exited "$pid"; then
        break
      fi
      tries=$((tries + 1))
      read -r -t 0.1 -u 3 3</dev/null || true
    done
    # A child that ignored TERM would leave this script waiting forever.
    if ! child_exited "$pid"; then
      kill -KILL -- "-${pid}" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
  done
  set -e
}

# ps still lists a zombie. An empty line means the pid is already gone.
child_exited() {
  local pid="$1"
  local state
  state="$(ps -o state= -p "$pid" 2>/dev/null || true)"
  state="${state//[[:space:]]/}"
  [[ -z "$state" || "$state" == Z* ]]
}

# Cleanup runs on Ctrl+C, termination, a server exit, and any earlier failure.
# The status argument is preserved so a later wait cannot replace it with 0.
finish() {
  local status="$1"
  trap - EXIT INT TERM
  stop_owned_trees
  exit "$status"
}

trap 'finish 130' INT
trap 'finish 143' TERM
trap 'finish $?' EXIT

# --local-db is the only flag. Anything else stops before installs or servers.
USE_LOCAL_DB=0
case "${1:-}" in
  "")
    ;;
  --local-db)
    USE_LOCAL_DB=1
    ;;
  --help | -h)
    echo "Usage: ./run.sh [--local-db]"
    echo "  --local-db  start local Docker Postgres, migrate, and seed golden cases"
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    echo "Usage: ./run.sh [--local-db]" >&2
    exit 2
    ;;
esac
if [[ "$#" -gt 1 ]]; then
  echo "Unexpected extra argument: $2" >&2
  echo "Usage: ./run.sh [--local-db]" >&2
  exit 2
fi

# Fail with a next step. Do not print the environment; it may hold keys and database URLs.
require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "$hint" >&2
    exit 1
  fi
}

# ss is preferred. lsof covers hosts that do not ship ss.
require_port_tool() {
  if ! command -v ss >/dev/null 2>&1 && ! command -v lsof >/dev/null 2>&1; then
    echo "Cannot check whether a port is free. Install ss (iproute2) or lsof, then run ./run.sh again." >&2
    exit 1
  fi
}

# Text from the port tool. The caller decides whether the port number appears in it.
port_listeners() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null || true
    return
  fi
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

# Stop before launching a server that would fail, or that Vite would move to another port.
require_port_free() {
  local port="$1"
  local role="$2"
  local listeners
  listeners="$(port_listeners "$port")"
  # Match :8000 and *:8000, but not 8000 inside 18000.
  if [[ "$listeners" =~ (^|[^0-9])${port}([^0-9]|$) ]]; then
    echo "Port ${port} is already in use (${role}). Stop the other process using that port, then run ./run.sh again." >&2
    exit 1
  fi
}

require_dev_ports() {
  require_port_free "$API_PORT" "the API"
  require_port_free "$WEB_PORT" "the frontend"
}

require_command uv "uv is required to install backend dependencies. Install uv, then run ./run.sh again."
require_command bun "bun is required to install frontend dependencies and generate API contracts. Install bun, then run ./run.sh again."
require_port_tool
require_dev_ports

# Install the locked backend dependencies first. A lockfile failure stops here,
# before contracts are generated and before either server is launched.
(cd "$ROOT/backend" && uv sync --frozen)

# frontend/bun.lock is the frontend lockfile. --frozen-lockfile will not
# install a different set than the one that was committed.
(cd "$ROOT/frontend" && bun install --frozen-lockfile)

# Export and regenerate the committed contracts, then verify them.
# set -e means a failing bun command never reaches the servers below.
bun run api:generate
bun run api:check

# Host of a database URL, without printing the URL. Userinfo and the port are discarded.
database_host() {
  local rest="${1#*://}"
  rest="${rest#*@}"
  printf '%s\n' "${rest%%[:/]*}"
}

# Start the compose Postgres and point child processes at it.
# The configured DATABASE_URL is replaced only inside this process. The shared
# environment file is not edited, and a remote host is never used for migrate or seed.
prepare_local_database() {
  # Matches docker-compose.yml: user rounds, database rounds, published on port 5433.
  # The password is the local development password from that file, not a cloud secret.
  local local_url="postgresql+psycopg://rounds:rounds@127.0.0.1:5433/rounds"
  local host
  host="$(database_host "$local_url")"
  if [[ "$host" != "127.0.0.1" && "$host" != "localhost" ]]; then
    echo "Local database mode only uses 127.0.0.1. It will not migrate or seed a remote database." >&2
    exit 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for --local-db. Install Docker, then run ./run.sh --local-db again." >&2
    exit 1
  fi

  echo "Starting local Docker Postgres. The shared environment file is not changed."
  # Leaving the container up preserves the pgdata volume. This script never runs compose down.
  if ! docker compose up -d db; then
    echo "Docker did not start local Postgres. Start Docker, then run ./run.sh --local-db again. The database volume was left in place." >&2
    exit 1
  fi

  local attempt=0
  local ready=0
  while [[ "$attempt" -lt 30 ]]; do
    attempt=$((attempt + 1))
    if docker compose exec -T db pg_isready -U rounds >/dev/null 2>&1; then
      ready=1
      break
    fi
    read -r -t 1 -u 3 3</dev/null || true
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "Local Postgres did not become ready. The database volume was left in place." >&2
    exit 1
  fi

  # Export after the host check so migrate, seed, and both servers inherit only the local URL.
  export DATABASE_URL="$local_url"
  (cd "$ROOT/backend" && uv run --no-sync alembic upgrade head)
  (cd "$ROOT/backend" && uv run --no-sync python -m scripts.seed_golden_cases)
}

if [[ "$USE_LOCAL_DB" -eq 1 ]]; then
  prepare_local_database
fi

# Check again in case another process took a port during install or database setup.
require_dev_ports

echo "Starting the API on port ${API_PORT} and the frontend on port ${WEB_PORT}."

# The subshell is the process-group leader. Its children stay in that group,
# so stopping the leader's group stops the whole server tree.
(
  cd "$ROOT/backend"
  exec uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port "$API_PORT"
) &
API_PID=$!

(
  cd "$ROOT/frontend"
  exec bun run dev -- --host 127.0.0.1 --port "$WEB_PORT" --strictPort
) &
WEB_PID=$!

# Wait until one owned server exits. Signals are handled by the traps above.
status=0
while true; do
  if child_exited "$API_PID"; then
    set +e
    wait "$API_PID"
    status=$?
    set -e
    break
  fi
  if child_exited "$WEB_PID"; then
    set +e
    wait "$WEB_PID"
    status=$?
    set -e
    break
  fi
  # Pause without an external sleep, and without reading the user's keyboard.
  read -r -t 0.1 -u 3 3</dev/null || true
done

finish "$status"
