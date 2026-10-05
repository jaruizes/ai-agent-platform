#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
POLL_SECONDS="${POLL_SECONDS:-2}"
MAX_POLLS="${MAX_POLLS:-90}"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.1 Process Platform / Agent Platform async integration =="

SUBMISSION=$(curl -fsS -X POST "$BASE_URL/v1/agent-executions" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"m9-process-platform-smoke",
    "intent":"Return exactly one short sentence confirming that the M9.1 asynchronous integration is working.",
    "input":{"test":"M9.1"},
    "context":{},
    "instructions":["Keep the response very short."],
    "metadata":{"purpose":"integration-smoke"}
  }')

EXECUTION_ID=$(jq -r '.executionId' <<<"$SUBMISSION")
CORRELATION_ID=$(jq -r '.correlationId' <<<"$SUBMISSION")

[[ -n "$EXECUTION_ID" && "$EXECUTION_ID" != "null" ]]
[[ -n "$CORRELATION_ID" && "$CORRELATION_ID" != "null" ]]

echo "submitted execution=$EXECUTION_ID correlation=$CORRELATION_ID"

for ((i=1;i<=MAX_POLLS;i++)); do
  EVENTS=$(curl -fsS "$BASE_URL/v1/agent-executions/$EXECUTION_ID/events")
  COUNT=$(jq 'length' <<<"$EVENTS")
  TYPES=$(jq -r '[.[].messageType] | unique | join(",")' <<<"$EVENTS")
  echo "poll $i: events=$COUNT types=$TYPES"

  if jq -e 'any(.[]; .messageType=="execution.result" and .data.execution.status=="COMPLETED")' <<<"$EVENTS" >/dev/null; then
    jq . <<<"$EVENTS"
    jq -e 'any(.[]; .messageType=="execution.lifecycle")' <<<"$EVENTS" >/dev/null
    jq -e 'any(.[]; .messageType=="execution.orchestration")' <<<"$EVENTS" >/dev/null
    echo
    echo "M9.1 smoke test PASSED."
    echo "Execution:   $EXECUTION_ID"
    echo "Correlation: $CORRELATION_ID"
    exit 0
  fi

  if jq -e 'any(.[]; .messageType=="execution.lifecycle" and (.data.execution.status=="FAILED" or .data.execution.status=="CANCELLED"))' <<<"$EVENTS" >/dev/null; then
    jq . <<<"$EVENTS"
    echo "Agent Platform execution terminated unsuccessfully" >&2
    exit 1
  fi

  sleep "$POLL_SECONDS"
done

echo "Timed out waiting for execution.result on Process Platform event inbox" >&2
exit 1
