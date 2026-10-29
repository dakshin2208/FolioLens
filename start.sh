#!/usr/bin/env bash
# FolioLens: one command to build, start and open the whole app on a Mac.
#   ./start.sh            build and start everything
#   ./start.sh stop       stop everything (data is kept)
set -euo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$1"; }
fail() { printf "\n\033[1;31mERROR: %s\033[0m\n" "$1"; exit 1; }
trap 'printf "\n\033[1;31mERROR: the step above failed (line %s). Copy the output above and share it.\033[0m\n" "$LINENO"' ERR

if [ "${1:-}" = "stop" ]; then
  docker compose down
  exit 0
fi

step "Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
  fail "Docker Desktop is not installed. Install it from https://www.docker.com/products/docker-desktop/ and run ./start.sh again."
fi
if ! docker info >/dev/null 2>&1; then
  echo "Starting Docker Desktop..."
  open -a Docker 2>/dev/null || true
  for _ in $(seq 1 90); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
  docker info >/dev/null 2>&1 || fail "Docker Desktop did not start. Open it manually, wait for 'Engine running', then run ./start.sh again."
fi
echo "Docker is running."

step "Checking configuration (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
python3 - <<'PY'
import secrets
lines = open(".env").read().splitlines()
out = []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "JWT_SECRET" and (not v or v.startswith("replace-with")):
            v = secrets.token_urlsafe(48)
            print("Generated a new JWT_SECRET")
        line = f"{k}={v}"
    out.append(line)
open(".env", "w").write("\n".join(out) + "\n")
PY

step "Building and starting containers (first time takes a few minutes)"
docker compose up --build -d --wait || {
  docker compose ps
  docker compose logs api --tail 40
  fail "A container did not start. The log above shows why."
}
docker compose ps

step "Loading the synthetic demo market data"
docker compose exec -T api python -m app.market_data.cli seed-demo

step "Creating the demo login with an analysed client portfolio (the AI can take up to a minute)"
docker compose exec -T api python -m app.market_data.cli seed-demo-account

step "Checking AI explanations"
docker compose exec -T api python -m app.insights.check_llm || \
  echo "AI check did not pass; the app still works and uses template explanations."

step "FolioLens is running"
cat <<'MSG'
  Open:      http://localhost:8080
  Demo:      http://localhost:8080/demo        (no login)
  Sign in:   demo@foliolens.app  /  foliolens-demo-2026
  Health:    http://localhost:8080/api/v1/health

  Stop with: ./start.sh stop
MSG
open http://localhost:8080/login 2>/dev/null || true
