#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
POLL_SECONDS="${POLL_SECONDS:-1}"
MAX_POLLS="${MAX_POLLS:-60}"
KEY="m9-runtime-$(date +%s)"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.3 deterministic runtime smoke test =="

DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions"   -H 'Content-Type: application/json'   -d "{
    \"definitionKey\":\"$KEY\",
    \"name\":\"M9.3 deterministic runtime\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\",\"required\":[\"id\"]},
    \"outputSchema\":{\"type\":\"object\",\"required\":[\"validate\",\"security\",\"cost\",\"compose\"]},
    \"steps\":[
      {\"stepKey\":\"validate\",\"name\":\"Validate\",\"type\":\"SERVICE\",\"dependsOn\":[],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"handler\":\"echo\"}},
      {\"stepKey\":\"security\",\"name\":\"Security\",\"type\":\"SERVICE\",\"dependsOn\":[\"validate\"],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"handler\":\"echo\"}},
      {\"stepKey\":\"cost\",\"name\":\"Cost\",\"type\":\"SERVICE\",\"dependsOn\":[\"validate\"],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"handler\":\"echo\"}},
      {\"stepKey\":\"compose\",\"name\":\"Compose\",\"type\":\"SERVICE\",\"dependsOn\":[\"security\",\"cost\"],\"inputSchema\":{\"type\":\"object\"},\"outputSchema\":{\"type\":\"object\"},\"configuration\":{\"handler\":\"echo\"}}
    ]
  }")
DEF_ID=$(jq -r '.id' <<<"$DEF")
curl -fsS -X POST "$BASE_URL/v1/process-definitions/$DEF_ID/activate" >/dev/null

INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances"   -H 'Content-Type: application/json'   -d "{\"definitionKey\":\"$KEY\",\"input\":{\"id\":\"P-1\"},\"context\":{}}")
INSTANCE_ID=$(jq -r '.id' <<<"$INSTANCE")

curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/start" >/dev/null

for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  echo "poll $i: $STATUS"

  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq -e '
      (.steps|length)==4
      and all(.steps[]; .status=="COMPLETED")
      and (.context|has("validate"))
      and (.context|has("security"))
      and (.context|has("cost"))
      and (.context|has("compose"))
      and (.context.compose.dependencies|has("security"))
      and (.context.compose.dependencies|has("cost"))
    ' <<<"$CURRENT" >/dev/null
    jq . <<<"$CURRENT"
    echo
    echo "M9.3 deterministic runtime smoke test PASSED."
    exit 0
  fi

  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
    jq . <<<"$CURRENT"
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

echo "Timed out waiting for deterministic process completion" >&2
exit 1
