#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
POLL_SECONDS="${POLL_SECONDS:-1}"
MAX_POLLS="${MAX_POLLS:-60}"
KEY="m96-review-$(date +%s)"
SERVICE_KEY="$KEY.echo"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.6 controlled human review-loop smoke test =="

SERVICE=$(curl -fsS -X POST "$BASE_URL/v1/process-services" \
  -H 'Content-Type: application/json' \
  -d "{
    \"serviceKey\":\"$SERVICE_KEY\",
    \"name\":\"Review-loop echo producer\",
    \"version\":1,
    \"implementationKey\":\"echo\",
    \"configuration\":{},
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"}
  }")
SERVICE_ID=$(jq -r '.id' <<<"$SERVICE")
curl -fsS -X POST "$BASE_URL/v1/process-services/$SERVICE_ID/activate" >/dev/null

DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"name\":\"M9.6 review loop smoke\",
    \"version\":1,
    \"inputSchema\":{\"type\":\"object\"},
    \"outputSchema\":{\"type\":\"object\"},
    \"steps\":[
      {
        \"stepKey\":\"producer\",
        \"name\":\"Producer\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}
      },
      {
        \"stepKey\":\"review\",
        \"name\":\"Human review\",
        \"type\":\"HUMAN\",
        \"dependsOn\":[\"producer\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{
          \"title\":\"Review producer output\",
          \"review\":{
            \"repeatStep\":\"producer\",
            \"approveDecision\":\"APPROVE\",
            \"repeatDecision\":\"REQUEST_CHANGES\",
            \"maxIterations\":3
          }
        }
      },
      {
        \"stepKey\":\"finish\",
        \"name\":\"Finish\",
        \"type\":\"SERVICE\",
        \"dependsOn\":[\"review\"],
        \"inputSchema\":{\"type\":\"object\"},
        \"outputSchema\":{\"type\":\"object\"},
        \"configuration\":{\"serviceKey\":\"$SERVICE_KEY\"}
      }
    ]
  }")
DEF_ID=$(jq -r '.id' <<<"$DEF")
curl -fsS -X POST "$BASE_URL/v1/process-definitions/$DEF_ID/activate" >/dev/null

INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"version\":1,
    \"correlationId\":\"$KEY-corr\",
    \"input\":{\"value\":\"initial\"},
    \"context\":{}
  }")
INSTANCE_ID=$(jq -r '.id' <<<"$INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/start" >/dev/null

wait_for_task() {
  local iteration="$1"
  for ((i=1;i<=MAX_POLLS;i++)); do
    TASKS=$(curl -fsS "$BASE_URL/v1/human-tasks?pendingOnly=true")
    TASK_ID=$(jq -r --arg iid "$INSTANCE_ID" --argjson iteration "$iteration" '
      .[] | select(.processInstanceId==$iid and .stepKey=="review" and .iteration==$iteration) | .id
    ' <<<"$TASKS" | head -1)
    if [[ -n "$TASK_ID" && "$TASK_ID" != "null" ]]; then
      echo "$TASK_ID"
      return 0
    fi
    sleep "$POLL_SECONDS"
  done
  return 1
}

TASK1=$(wait_for_task 1)
echo "review iteration 1 pending: $TASK1"

curl -fsS -X POST "$BASE_URL/v1/human-tasks/$TASK1/complete" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"REQUEST_CHANGES","result":{"comment":"Please revise the producer output."}}' >/dev/null

TASK2=$(wait_for_task 2)
echo "review iteration 2 pending: $TASK2"

CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
jq -e '
  (.steps[] | select(.stepKey=="producer") | .attemptCount) == 2
  and (.steps[] | select(.stepKey=="review") | .attemptCount) == 2
  and (.context._reviewHistory.review | length) == 1
  and .context._reviewHistory.review[0].iteration == 1
  and .context._reviewHistory.review[0].feedback.decision == "REQUEST_CHANGES"
  and .context._reviewHistory.review[0].feedback.result.comment == "Please revise the producer output."
' <<<"$CURRENT" >/dev/null

echo "producer repeated and review feedback persisted"

curl -fsS -X POST "$BASE_URL/v1/human-tasks/$TASK2/complete" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"APPROVE","result":{"comment":"Approved after revision."}}' >/dev/null

COMPLETED=false
for ((i=1;i<=MAX_POLLS;i++)); do
  CURRENT=$(curl -fsS "$BASE_URL/v1/process-instances/$INSTANCE_ID")
  STATUS=$(jq -r '.status' <<<"$CURRENT")
  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq -e '
      (.steps[] | select(.stepKey=="producer") | .attemptCount) == 2
      and (.steps[] | select(.stepKey=="review") | .status) == "COMPLETED"
      and (.steps[] | select(.stepKey=="finish") | .status) == "COMPLETED"
      and .context.review.decision == "APPROVE"
      and .context.review.iteration == 2
    ' <<<"$CURRENT" >/dev/null
    COMPLETED=true
    break
  fi
  if [[ "$STATUS" == "FAILED" || "$STATUS" == "CANCELLED" ]]; then
    jq . <<<"$CURRENT"
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

[[ "$COMPLETED" == "true" ]]

echo
echo "M9.6 controlled human review-loop smoke test PASSED."
