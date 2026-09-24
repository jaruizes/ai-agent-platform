#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
POLL_SECONDS="${POLL_SECONDS:-1}"
MAX_POLLS="${MAX_POLLS:-60}"
KEY="m94-$(date +%s)"
SERVICE_KEY="$KEY.echo"
CORRELATION_ID="$KEY-correlation"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.4 Process Capabilities & Long-running Workflow smoke test =="

SERVICE=$(curl -fsS -X POST "$BASE_URL/v1/process-services" \
  -H 'Content-Type: application/json' \
  -d "{
    \"serviceKey\":\"$SERVICE_KEY\",
    \"name\":\"M9.4 echo service\",
    \"description\":\"Deterministic service catalog smoke capability\",
    \"version\":1,
    \"implementationKey\":\"echo\",
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"}
  }")
SERVICE_ID=$(jq -r '.id' <<<"$SERVICE")
curl -fsS -X POST "$BASE_URL/v1/process-services/$SERVICE_ID/activate" >/dev/null

ACTIVE_SERVICES=$(curl -fsS "$BASE_URL/v1/process-services?activeOnly=true")
jq -e --arg key "$SERVICE_KEY" 'any(.[]; .serviceKey==$key and .status=="ACTIVE")' <<<"$ACTIVE_SERVICES" >/dev/null
echo "service registry discovery OK"

DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"name\":\"M9.4 long-running process\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\",\"required\":[\"requiresApproval\"]},
    \"outputSchema\":{\"type\":\"object\",\"required\":[\"prepare\",\"route\",\"confirmed\",\"finish\"]},
    \"steps\":[
      {
        \"stepKey\":\"prepare\",
        \"name\":\"Prepare\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}
      },
      {
        \"stepKey\":\"route\",
        \"name\":\"Route approval\",
        \"type\":\"DECISION\",
        \"dependsOn\":[\"prepare\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\",\"required\":[\"outcome\"]},
        \"configuration\":{
          \"path\":\"processInput.requiresApproval\",
          \"operator\":\"EQ\",
          \"value\":true,
          \"onTrue\":\"HUMAN\",
          \"onFalse\":\"AUTO\"
        }
      },
      {
        \"stepKey\":\"approval\",
        \"name\":\"Human approval\",
        \"type\":\"HUMAN\",
        \"dependsOn\":[\"route\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\",\"required\":[\"decision\"]},
        \"configuration\":{
          \"title\":\"Approve M9.4 smoke process\",
          \"when\":{\"decisionStep\":\"route\",\"equals\":\"HUMAN\"}
        }
      },
      {
        \"stepKey\":\"auto\",
        \"name\":\"Automatic branch\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[\"route\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{
          \"serviceKey\":\"$SERVICE_KEY\",
          \"when\":{\"decisionStep\":\"route\",\"equals\":\"AUTO\"}
        }
      },
      {
        \"stepKey\":\"confirmed\",
        \"name\":\"Wait external confirmation\",
        \"type\":\"WAIT_EVENT\",
        \"dependsOn\":[\"approval\",\"auto\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\",\"required\":[\"payload\"]},
        \"configuration\":{\"eventType\":\"m94.confirmed\"}
      },
      {
        \"stepKey\":\"finish\",
        \"name\":\"Finish\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[\"confirmed\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}
      }
    ]
  }")
DEF_ID=$(jq -r '.id' <<<"$DEF")
ACTIVE_DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions/$DEF_ID/activate")
jq -e --arg key "$SERVICE_KEY" '
  .status=="ACTIVE"
  and all(.steps[] | select(.type=="SERVICE"); .configuration.serviceKey==$key and .configuration.serviceVersion==1)
' <<<"$ACTIVE_DEF" >/dev/null
echo "process activation pinned service version"

INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"correlationId\":\"$CORRELATION_ID\",
    \"input\":{\"requiresApproval\":true},
    \"context\":{}
  }")
INSTANCE_ID=$(jq -r '.id' <<<"$INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/start" >/dev/null

TASK_ID=""
for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  APPROVAL_STATUS=$(jq -r '.steps[] | select(.stepKey=="approval") | .status' <<<"$CURRENT")
  AUTO_STATUS=$(jq -r '.steps[] | select(.stepKey=="auto") | .status' <<<"$CURRENT")
  if [[ "$APPROVAL_STATUS" == "WAITING" && "$AUTO_STATUS" == "SKIPPED" ]]; then
    TASKS=$(curl -fsS "$BASE_URL/v1/human-tasks?pendingOnly=true")
    TASK_ID=$(jq -r --arg iid "$INSTANCE_ID" '.[] | select(.processInstanceId==$iid) | .id' <<<"$TASKS" | head -1)
    [[ -n "$TASK_ID" && "$TASK_ID" != "null" ]]
    break
  fi
  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then jq . <<<"$CURRENT"; exit 1; fi
  sleep "$POLL_SECONDS"
done
[[ -n "$TASK_ID" ]]
echo "decision routing + human task creation OK"

PAUSED=$(curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/pause")
jq -e '.status=="PAUSED"' <<<"$PAUSED" >/dev/null

curl -fsS -X POST "$BASE_URL/v1/human-tasks/$TASK_ID/complete" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"APPROVED","result":{"reviewer":"smoke"}}' >/dev/null

STILL_PAUSED=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
jq -e '.status=="PAUSED" and (.context.approval.decision=="APPROVED")' <<<"$STILL_PAUSED" >/dev/null
echo "pause keeps process frozen while durable human result is stored"

curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/resume" >/dev/null

for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  WAIT_STATUS=$(jq -r '.steps[] | select(.stepKey=="confirmed") | .status' <<<"$CURRENT")
  [[ "$WAIT_STATUS" == "WAITING" ]] && break
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then jq . <<<"$CURRENT"; exit 1; fi
  sleep "$POLL_SECONDS"
done

MATCH=$(curl -fsS -X POST "$BASE_URL/v1/process-events" \
  -H 'Content-Type: application/json' \
  -d "{
    \"eventType\":\"m94.confirmed\",
    \"correlationId\":\"$CORRELATION_ID\",
    \"payload\":{\"externalId\":\"EXT-1\"}
  }")
jq -e '.matchedWaits==1' <<<"$MATCH" >/dev/null
echo "durable correlated WAIT_EVENT resumed"

COMPLETED_OK=false
for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  echo "poll $i: $STATUS"
  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq -e '
      (.steps[] | select(.stepKey=="prepare") | .status)=="COMPLETED"
      and (.steps[] | select(.stepKey=="route") | .status)=="COMPLETED"
      and (.steps[] | select(.stepKey=="approval") | .status)=="COMPLETED"
      and (.steps[] | select(.stepKey=="auto") | .status)=="SKIPPED"
      and (.steps[] | select(.stepKey=="confirmed") | .status)=="COMPLETED"
      and (.steps[] | select(.stepKey=="finish") | .status)=="COMPLETED"
      and .context.confirmed.payload.externalId=="EXT-1"
    ' <<<"$CURRENT" >/dev/null
    COMPLETED_OK=true
    break
  fi
  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then jq . <<<"$CURRENT"; exit 1; fi
  sleep "$POLL_SECONDS"
done
[[ "$COMPLETED_OK" == "true" ]]
echo "long-running happy path COMPLETED"

# Cancel a second instance while it is waiting for a human.
CANCEL_INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"correlationId\":\"$KEY-cancel\",
    \"input\":{\"requiresApproval\":true},
    \"context\":{}
  }")
CANCEL_ID=$(jq -r '.id' <<<"$CANCEL_INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$CANCEL_ID/start" >/dev/null

for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$CANCEL_ID")
  APPROVAL_STATUS=$(jq -r '.steps[] | select(.stepKey=="approval") | .status' <<<"$CURRENT")
  [[ "$APPROVAL_STATUS" == "WAITING" ]] && break
  sleep "$POLL_SECONDS"
done

CANCELLED=$(curl -fsS -X POST "$BASE_URL/v1/process-instances/$CANCEL_ID/cancel")
jq -e '.status=="CANCELLED" and all(.steps[]; (.status=="COMPLETED" or .status=="SKIPPED" or .status=="CANCELLED"))' <<<"$CANCELLED" >/dev/null
PENDING_AFTER_CANCEL=$(curl -fsS "$BASE_URL/v1/human-tasks?pendingOnly=true")
jq -e --arg iid "$CANCEL_ID" 'all(.[]; .processInstanceId != $iid)' <<<"$PENDING_AFTER_CANCEL" >/dev/null
echo "cancel terminates process and pending human work"

# Validate durable WAIT_EVENT timeout.
TIMEOUT_KEY="$KEY-timeout"
TIMEOUT_DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$TIMEOUT_KEY\",
    \"name\":\"M9.4 timeout process\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"},
    \"steps\":[{
      \"stepKey\":\"wait\",
      \"name\":\"Timed wait\",
      \"type\":\"WAIT_EVENT\",
      \"dependsOn\":[],
      \"inputSchema\":{\"type\":\"object\"},
      \"outputSchema\":{\"type\":\"object\"},
      \"configuration\":{\"eventType\":\"never.arrives\",\"timeoutSeconds\":1}
    }]
  }")
TIMEOUT_DEF_ID=$(jq -r '.id' <<<"$TIMEOUT_DEF")
curl -fsS -X POST "$BASE_URL/v1/process-definitions/$TIMEOUT_DEF_ID/activate" >/dev/null
TIMEOUT_INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances" \
  -H 'Content-Type: application/json' \
  -d "{\"definitionKey\":\"$TIMEOUT_KEY\",\"correlationId\":\"$KEY-timeout-corr\",\"input\":{},\"context\":{}}")
TIMEOUT_ID=$(jq -r '.id' <<<"$TIMEOUT_INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$TIMEOUT_ID/start" >/dev/null

TIMEOUT_OK=false
for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$TIMEOUT_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  if [[ "$STATUS" == "FAILED" ]]; then
    jq -e '(.steps[] | select(.stepKey=="wait") | .error.code)=="STEP_TIMEOUT"' <<<"$CURRENT" >/dev/null
    TIMEOUT_OK=true
    break
  fi
  sleep "$POLL_SECONDS"
done
[[ "$TIMEOUT_OK" == "true" ]]
echo "WAIT_EVENT timeout fails durably"

echo
echo "M9.4 long-running workflow smoke test PASSED."
