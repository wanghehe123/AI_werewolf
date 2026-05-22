#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:8000"
BOARD_ID=""
SEED=""
MAX_STEPS="80"
OUTPUT_ROOT="docs/evaluations"
BACKEND_CMD="python -m uvicorn ai_werewolf.main:app --reload --port 8000"
NO_START="0"

usage() {
  cat <<'USAGE'
Usage:
  run_eval.sh --board-id <id> [--base-url http://localhost:8000] [--seed 123] [--max-steps 80]
              [--output-root docs/evaluations] [--backend-cmd "..."] [--no-start]
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --board-id) BOARD_ID="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --max-steps) MAX_STEPS="$2"; shift 2 ;;
    --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
    --backend-cmd) BACKEND_CMD="$2"; shift 2 ;;
    --no-start) NO_START="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [ -z "$BOARD_ID" ]; then
  echo "--board-id is required" >&2
  usage
  exit 2
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)-ai-werewolf-eval"
RUN_DIR="$OUTPUT_ROOT/$RUN_ID"
mkdir -p "$RUN_DIR"

health_ok() {
  curl -fsS "$BASE_URL/health" >/dev/null 2>&1
}

BACKEND_PID=""
if ! health_ok; then
  if [ "$NO_START" = "1" ]; then
    echo "Backend is not healthy and --no-start was set." >&2
    exit 1
  fi
  echo "Starting backend: $BACKEND_CMD"
  ( eval "$BACKEND_CMD" ) >"$RUN_DIR/backend.log" 2>&1 &
  BACKEND_PID="$!"
  echo "$BACKEND_PID" >"$RUN_DIR/backend.pid"
  for _ in $(seq 1 60); do
    if health_ok; then
      break
    fi
    sleep 1
  done
  if ! health_ok; then
    echo "Backend did not become healthy. See $RUN_DIR/backend.log" >&2
    exit 1
  fi
else
  : >"$RUN_DIR/backend.log"
fi

PAYLOAD="$RUN_DIR/request.json"
python3 - "$BOARD_ID" "$SEED" "$MAX_STEPS" >"$PAYLOAD" <<'PY'
import json
import sys

board_id, seed, max_steps = sys.argv[1], sys.argv[2], int(sys.argv[3])
payload = {"board_id": board_id, "max_steps": max_steps}
if seed:
    payload["seed"] = int(seed)
print(json.dumps(payload, ensure_ascii=False))
PY

curl -sS -X POST "$BASE_URL/evaluations/ai-games/run" \
  -H "Content-Type: application/json" \
  --data @"$PAYLOAD" \
  | tee "$RUN_DIR/response.json" >/dev/null

python3 - "$RUN_DIR/response.json" "$RUN_DIR/events.jsonl" "$RUN_DIR/run.env" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
events_path = Path(sys.argv[2])
env_path = Path(sys.argv[3])
body = json.loads(response_path.read_text(encoding="utf-8"))
data = body.get("data") or body
events = data.get("events") or []
with events_path.open("w", encoding="utf-8") as f:
    for event in events:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
with env_path.open("w", encoding="utf-8") as f:
    f.write(f"RUN_DIR={events_path.parent}\n")
    f.write(f"GAME_ID={data.get('game_id', '')}\n")
    f.write(f"EVALUATION_ID={data.get('evaluation_id', '')}\n")
    f.write(f"STATUS={data.get('status', '')}\n")
    f.write(f"WINNER={data.get('winner', '')}\n")
PY

echo "Run directory: $RUN_DIR"
if [ -n "$BACKEND_PID" ]; then
  echo "Backend PID: $BACKEND_PID"
fi
