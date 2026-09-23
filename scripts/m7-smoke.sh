#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
POLL_SECONDS="${POLL_SECONDS:-2}"
MAX_POLLS="${MAX_POLLS:-90}"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require curl
require jq

wait_execution() {
  local id="$1"
  local status=""
  for ((i=1; i<=MAX_POLLS; i++)); do
    status="$(curl -fsS "$BASE_URL/v1/executions/$id" | jq -r '.status')"
    printf '  poll %02d: %s\n' "$i" "$status"
    case "$status" in
      COMPLETED) return 0 ;;
      FAILED|CANCELLED)
        curl -fsS "$BASE_URL/v1/executions/$id" | jq .
        return 1
        ;;
    esac
    sleep "$POLL_SECONDS"
  done
  echo "Execution $id did not finish after $MAX_POLLS polls" >&2
  return 1
}

echo "== M7 smoke test against $BASE_URL =="

echo "[1/8] Create a TENANT session with ownerKey=m7-smoke"
SESSION_JSON="$(
  curl -fsS -X POST "$BASE_URL/v1/sessions"     -H 'Content-Type: application/json'     -d '{
      "name":"m7-smoke",
      "scope":"TENANT",
      "ownerKey":"m7-smoke",
      "metadata":{"test":"M7"}
    }'
)"
SESSION_ID="$(jq -r '.id' <<<"$SESSION_JSON")"
echo "  sessionId=$SESSION_ID"

cleanup() {
  curl -fsS -X POST "$BASE_URL/v1/sessions/$SESSION_ID/close" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[2/8] Persist deterministic TENANT and SESSION memories"
curl -fsS -X POST "$BASE_URL/v1/memories"   -H 'Content-Type: application/json'   -d '{
    "scopeType":"TENANT",
    "scopeId":"m7-smoke",
    "memoryType":"CONSTRAINT",
    "key":"primary-cloud",
    "content":"The primary cloud for project Mercury is AWS.",
    "importance":0.95
  }' | jq -e '.memory.status=="ACTIVE"' >/dev/null

curl -fsS -X POST "$BASE_URL/v1/memories"   -H 'Content-Type: application/json'   -d "{
    \"scopeType\":\"SESSION\",
    \"scopeId\":\"$SESSION_ID\",
    \"memoryType\":\"PREFERENCE\",
    \"key\":\"messaging\",
    \"content\":\"For project Mercury, prefer NATS for lightweight event messaging.\",
    \"importance\":0.90
  }" | jq -e '.memory.status=="ACTIVE"' >/dev/null

echo "[3/8] Verify hybrid memory retrieval"
RETRIEVAL="$(
  curl -fsS -X POST "$BASE_URL/v1/memories/retrieve"     -H 'Content-Type: application/json'     -d "{
      \"query\":\"What are the Mercury primary cloud AWS constraint and NATS messaging preference?\",
      \"scopes\":[
        {\"scopeType\":\"TENANT\",\"scopeId\":\"m7-smoke\"},
        {\"scopeType\":\"SESSION\",\"scopeId\":\"$SESSION_ID\"}
      ],
      \"topK\":8
    }"
)"
jq . <<<"$RETRIEVAL"
jq -e 'length >= 2' <<<"$RETRIEVAL" >/dev/null

echo "[4/8] Run a model execution that receives only sessionId, not memory content"
EXECUTION_JSON="$(
  curl -fsS -X POST "$BASE_URL/v1/executions"     -H 'Content-Type: application/json'     -d "{
      \"correlationId\":\"m7-smoke-$(date +%s)\",
      \"sessionId\":\"$SESSION_ID\",
      \"command\":{
        \"name\":\"m7-memory-recall\",
        \"intent\":\"For project Mercury, state the primary cloud constraint and the preferred lightweight event messaging technology. Use retained project context; do not invent values.\",
        \"input\":{},
        \"context\":{},
        \"instructions\":[\"Answer in one concise sentence.\"]
      }
    }"
)"
EXECUTION_ID="$(jq -r '.executionId' <<<"$EXECUTION_JSON")"
echo "  executionId=$EXECUTION_ID"
wait_execution "$EXECUTION_ID"

echo "[5/8] Inspect final result"
curl -fsS "$BASE_URL/v1/executions/$EXECUTION_ID" | jq '.status,.result'

echo "[6/8] Assert Context Engine selected Memory and created snapshots"
SNAPSHOTS="$(curl -fsS "$BASE_URL/v1/executions/$EXECUTION_ID/context-snapshots")"
jq . <<<"$SNAPSHOTS"
jq -e 'length > 0' <<<"$SNAPSHOTS" >/dev/null
jq -e 'any(.[]; any(.components[]; .type=="MEMORY" and .selected==true))' <<<"$SNAPSHOTS" >/dev/null

echo "[7/8] Inspect Working Context and session continuity"
curl -fsS "$BASE_URL/v1/executions/$EXECUTION_ID/context" | jq .
curl -fsS "$BASE_URL/v1/sessions/$SESSION_ID/executions" | jq .
curl -fsS "$BASE_URL/v1/sessions/$SESSION_ID/context" | jq '.[-12:]'

echo "[8/8] Show memory policy and automatically inferred SESSION memories"
curl -fsS "$BASE_URL/v1/memory-policy" | jq .
curl -fsS "$BASE_URL/v1/memories?scopeType=SESSION&scopeId=$SESSION_ID" | jq .

echo
echo "M7 smoke test PASSED."
echo "Open Control Plane: http://localhost:${CONTROL_PLANE_PORT:-8081}"
echo "Inspect execution: $EXECUTION_ID"
echo "Inspect session:   $SESSION_ID"
