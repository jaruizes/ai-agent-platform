#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
POLL_SECONDS="${POLL_SECONDS:-2}"
MAX_POLLS="${MAX_POLLS:-120}"
KEY="m9-agentic-$(date +%s)"
SERVICE_KEY="$KEY.echo"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.3 hybrid Process Platform / Agent Platform smoke test =="

SERVICE=$(curl -fsS -X POST "$BASE_URL/v1/process-services" \
  -H 'Content-Type: application/json' \
  -d "{
    \"serviceKey\":\"$SERVICE_KEY\",
    \"name\":\"Smoke echo service\",
    \"version\":1,
    \"implementationKey\":\"echo\",
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"}
  }")
SERVICE_ID=$(jq -r '.id' <<<"$SERVICE")
curl -fsS -X POST "$BASE_URL/v1/process-services/$SERVICE_ID/activate" >/dev/null

DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions"   -H 'Content-Type: application/json'   -d "{
    \"definitionKey\":\"$KEY\",
    \"name\":\"M9.3 hybrid runtime\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\",\"required\":[\"prepare\",\"analyse\",\"finish\"]},
    \"steps\":[
      {\"stepKey\":\"prepare\",\"name\":\"Prepare\",\"type\":\"SERVICE\",\"dependsOn\":[],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}},
      {\"stepKey\":\"analyse\",\"name\":\"Agentic analysis\",\"type\":\"AGENTIC_EXECUTION\",\"dependsOn\":[\"prepare\"],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"intent\":\"Return a very short confirmation that this delegated process step was resolved by the Agent Platform.\",\"instructions\":[\"Be concise.\"]}},
      {\"stepKey\":\"finish\",\"name\":\"Finish\",\"type\":\"SERVICE\",\"dependsOn\":[\"analyse\"],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}}
    ]
  }")
DEF_ID=$(jq -r '.id' <<<"$DEF")
curl -fsS -X POST "$BASE_URL/v1/process-definitions/$DEF_ID/activate" >/dev/null

INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances"   -H 'Content-Type: application/json'   -d "{\"definitionKey\":\"$KEY\",\"input\":{\"case\":\"M9.3\"},\"context\":{}}")
INSTANCE_ID=$(jq -r '.id' <<<"$INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/start" >/dev/null

for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  AGENT_STATUS=$(jq -r '.steps[] | select(.stepKey=="analyse") | .status' <<<"$CURRENT")
  EXECUTION_ID=$(jq -r '.steps[] | select(.stepKey=="analyse") | .delegatedExecutionId // ""' <<<"$CURRENT")
  echo "poll $i: process=$STATUS agentStep=$AGENT_STATUS execution=$EXECUTION_ID"

  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq -e '
      all(.steps[]; .status=="COMPLETED")
      and (.context|has("analyse"))
      and ((.steps[] | select(.stepKey=="analyse") | .delegatedExecutionId) != null)
    ' <<<"$CURRENT" >/dev/null
    jq . <<<"$CURRENT"
    echo
    echo "M9.3 hybrid agentic runtime smoke test PASSED."
    exit 0
  fi

  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
    jq . <<<"$CURRENT"
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

echo "Timed out waiting for hybrid process completion" >&2
exit 1
