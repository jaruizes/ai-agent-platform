#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"

command -v curl >/dev/null
command -v jq >/dev/null

KEY="m9-process-$(date +%s)"
SERVICE_KEY="$KEY.echo"

echo "== M9.2 Process Domain smoke test =="

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


V1=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions"   -H 'Content-Type: application/json'   -d "{
    \"definitionKey\":\"$KEY\",
    \"name\":\"M9.2 smoke process\",
    \"description\":\"Deterministic process definition\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"},
    \"steps\":[
      {
        \"stepKey\":\"validate\",
        \"name\":\"Validate input\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"handler\":\"validate-input\"}
      },
      {
        \"stepKey\":\"analyse\",
        \"name\":\"Agentic analysis\",
        \"type\":\"AGENTIC_EXECUTION\",
        \"dependsOn\":[\"validate\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"intent\":\"Analyse the validated input\"}
      }
    ]
  }")

V1_ID=$(jq -r '.id' <<<"$V1")
jq -e '.status=="DRAFT" and .version==1 and (.steps|length)==2' <<<"$V1" >/dev/null
echo "draft v1=$V1_ID"

ACTIVE=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions/$V1_ID/activate")
jq -e '.status=="ACTIVE"' <<<"$ACTIVE" >/dev/null
echo "activated v1"

HTTP_CODE=$(curl -sS -o /tmp/m9-active-update.json -w '%{http_code}'   -X PUT "$BASE_URL/v1/process-definitions/$V1_ID"   -H 'Content-Type: application/json'   -d '{"name":"must-not-change","steps":[]}')
[[ "$HTTP_CODE" == "409" ]]
echo "active definition is immutable"

INSTANCE1=$(curl -fsS -X POST "$BASE_URL/v1/process-instances"   -H 'Content-Type: application/json'   -d "{
    \"definitionKey\":\"$KEY\",
    \"correlationId\":\"m9-smoke-1\",
    \"input\":{\"proposalId\":\"P-1\"},
    \"context\":{\"locale\":\"es\"}
  }")
INSTANCE1_ID=$(jq -r '.id' <<<"$INSTANCE1")
jq -e '.definitionVersion==1 and .status=="CREATED" and (.steps|length)==2 and all(.steps[]; .status=="PENDING")' <<<"$INSTANCE1" >/dev/null
echo "instance v1=$INSTANCE1_ID"

CONTEXT=$(curl -fsS -X PUT "$BASE_URL/v1/process-instances/$INSTANCE1_ID/context"   -H 'Content-Type: application/json'   -d '{"context":{"locale":"es","validated":true}}')
jq -e '.context.validated==true' <<<"$CONTEXT" >/dev/null
echo "durable process context updated"

V2=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions/$V1_ID/next-version")
V2_ID=$(jq -r '.id' <<<"$V2")
jq -e '.version==2 and .status=="DRAFT" and (.steps|length)==2' <<<"$V2" >/dev/null
echo "cloned v2=$V2_ID"

INSTANCE_BEFORE_V2=$(curl -fsS -X POST "$BASE_URL/v1/process-instances"   -H 'Content-Type: application/json'   -d "{\"definitionKey\":\"$KEY\",\"input\":{},\"context\":{}}")
jq -e '.definitionVersion==1' <<<"$INSTANCE_BEFORE_V2" >/dev/null
echo "draft v2 does not affect latest active resolution"

curl -fsS -X POST "$BASE_URL/v1/process-definitions/$V2_ID/activate" >/dev/null

INSTANCE2=$(curl -fsS -X POST "$BASE_URL/v1/process-instances"   -H 'Content-Type: application/json'   -d "{\"definitionKey\":\"$KEY\",\"input\":{},\"context\":{}}")
jq -e '.definitionVersion==2' <<<"$INSTANCE2" >/dev/null
echo "latest active now resolves v2"

ORIGINAL=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE1_ID")
jq -e '.definitionVersion==1 and .context.validated==true' <<<"$ORIGINAL" >/dev/null
echo "existing v1 instance remains pinned to v1"

echo
echo "M9.2 smoke test PASSED."
echo "Definition v1: $V1_ID"
echo "Definition v2: $V2_ID"
echo "Instance v1:   $INSTANCE1_ID"
