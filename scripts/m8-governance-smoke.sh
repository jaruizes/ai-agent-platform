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

wait_terminal() {
  local id="$1"
  local expected="${2:-}"
  local status=""
  for ((i=1; i<=MAX_POLLS; i++)); do
    status="$(curl -fsS "$BASE_URL/v1/executions/$id" | jq -r '.status')"
    printf '  poll %02d: %s\n' "$i" "$status"
    case "$status" in
      COMPLETED|FAILED|CANCELLED)
        if [[ -n "$expected" && "$status" != "$expected" ]]; then
          echo "Expected $expected but got $status" >&2
          curl -fsS "$BASE_URL/v1/executions/$id" | jq .
          return 1
        fi
        return 0
        ;;
    esac
    sleep "$POLL_SECONDS"
  done
  echo "Execution $id did not reach terminal state" >&2
  return 1
}

submit() {
  local correlation="$1"
  curl -fsS -X POST "$BASE_URL/v1/executions"     -H 'Content-Type: application/json'     -d "{
      \"sessionId\":\"$SESSION_ID\",
      \"correlationId\":\"$correlation\",
      \"command\":{
        \"name\":\"m8-governance-smoke\",
        \"intent\":\"Return a concise confirmation that governance smoke testing is active.\",
        \"input\":{},
        \"context\":{},
        \"instructions\":[\"Keep the answer very short.\"],
        \"metadata\":{\"tenantId\":\"m8-smoke\"}
      }
    }"
}

echo "== M8.1 / M8.2 governance smoke test =="

SESSION_JSON="$(
  curl -fsS -X POST "$BASE_URL/v1/sessions"     -H 'Content-Type: application/json'     -d '{
      "name":"m8-governance-smoke",
      "scope":"TENANT",
      "ownerKey":"m8-smoke",
      "metadata":{"test":"M8"}
    }'
)"
SESSION_ID="$(jq -r '.id' <<<"$SESSION_JSON")"
POLICY_DENY_ID=""
POLICY_ALLOW_ID=""
BUDGET_ID=""

cleanup() {
  [[ -z "$POLICY_ALLOW_ID" ]] || curl -fsS -X DELETE "$BASE_URL/v1/governance/policies/$POLICY_ALLOW_ID" >/dev/null 2>&1 || true
  [[ -z "$POLICY_DENY_ID" ]] || curl -fsS -X DELETE "$BASE_URL/v1/governance/policies/$POLICY_DENY_ID" >/dev/null 2>&1 || true
  [[ -z "$BUDGET_ID" ]] || curl -fsS -X DELETE "$BASE_URL/v1/governance/budgets/$BUDGET_ID" >/dev/null 2>&1 || true
  curl -fsS -X POST "$BASE_URL/v1/sessions/$SESSION_ID/close" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[1/7] Baseline execution"
BASELINE="$(submit "m8-baseline-$(date +%s)")"
BASELINE_ID="$(jq -r '.executionId' <<<"$BASELINE")"
echo "  executionId=$BASELINE_ID"
wait_terminal "$BASELINE_ID" "COMPLETED"

echo "[2/7] Create broad DENY and higher-priority specific ALLOW"
DENY="$(
  curl -fsS -X POST "$BASE_URL/v1/governance/policies"     -H 'Content-Type: application/json'     -d '{
      "name":"m8-smoke-deny-planner",
      "description":"Broad planner deny used by smoke test",
      "policyType":"MODEL_ACCESS",
      "effect":"DENY",
      "resourceType":"MODEL",
      "resourcePattern":"planner-*",
      "subjectType":"TENANT",
      "subjectPattern":"m8-smoke",
      "conditions":{},
      "priority":100,
      "enabled":true
    }'
)"
POLICY_DENY_ID="$(jq -r '.id' <<<"$DENY")"

ALLOW="$(
  curl -fsS -X POST "$BASE_URL/v1/governance/policies"     -H 'Content-Type: application/json'     -d '{
      "name":"m8-smoke-allow-planner-default",
      "description":"Priority override used by smoke test",
      "policyType":"MODEL_ACCESS",
      "effect":"ALLOW",
      "resourceType":"MODEL",
      "resourcePattern":"planner-default",
      "subjectType":"TENANT",
      "subjectPattern":"m8-smoke",
      "conditions":{},
      "priority":200,
      "enabled":true
    }'
)"
POLICY_ALLOW_ID="$(jq -r '.id' <<<"$ALLOW")"

SIM="$(
  curl -fsS -X POST "$BASE_URL/v1/governance/policies/evaluate"     -H 'Content-Type: application/json'     -d "{
      \"executionId\":\"$BASELINE_ID\",
      \"policyType\":\"MODEL_ACCESS\",
      \"resourceType\":\"MODEL\",
      \"resourceName\":\"planner-default\",
      \"context\":{}
    }"
)"
jq . <<<"$SIM"
jq -e '.effect=="ALLOW" and .policyName=="m8-smoke-allow-planner-default"' <<<"$SIM" >/dev/null

echo "[3/7] Remove override and verify deterministic DENY"
curl -fsS -X DELETE "$BASE_URL/v1/governance/policies/$POLICY_ALLOW_ID" >/dev/null
POLICY_ALLOW_ID=""
SIM_DENY="$(
  curl -fsS -X POST "$BASE_URL/v1/governance/policies/evaluate"     -H 'Content-Type: application/json'     -d "{
      \"executionId\":\"$BASELINE_ID\",
      \"policyType\":\"MODEL_ACCESS\",
      \"resourceType\":\"MODEL\",
      \"resourceName\":\"planner-default\",
      \"context\":{}
    }"
)"
jq . <<<"$SIM_DENY"
jq -e '.effect=="DENY"' <<<"$SIM_DENY" >/dev/null

echo "[4/7] Verify runtime enforcement blocks Planner"
BLOCKED="$(submit "m8-policy-deny-$(date +%s)")"
BLOCKED_ID="$(jq -r '.executionId' <<<"$BLOCKED")"
wait_terminal "$BLOCKED_ID" "FAILED"
curl -fsS "$BASE_URL/v1/governance/decisions?executionId=$BLOCKED_ID"   | jq -e 'any(.[]; .effect=="DENY" and .resourceName=="planner-default")' >/dev/null

curl -fsS -X DELETE "$BASE_URL/v1/governance/policies/$POLICY_DENY_ID" >/dev/null
POLICY_DENY_ID=""

echo "[5/7] Create impossible token budget"
BUDGET="$(
  curl -fsS -X POST "$BASE_URL/v1/governance/budgets"     -H 'Content-Type: application/json'     -d '{
      "name":"m8-smoke-one-token",
      "scopeType":"TENANT",
      "scopeId":"m8-smoke",
      "period":"EXECUTION",
      "maxTotalTokens":1,
      "action":"DENY",
      "enabled":true
    }'
)"
BUDGET_ID="$(jq -r '.id' <<<"$BUDGET")"

echo "[6/7] Verify budget blocks model before provider invocation"
BUDGET_BLOCKED="$(submit "m8-budget-deny-$(date +%s)")"
BUDGET_EXEC_ID="$(jq -r '.executionId' <<<"$BUDGET_BLOCKED")"
wait_terminal "$BUDGET_EXEC_ID" "FAILED"
curl -fsS "$BASE_URL/v1/governance/budget-decisions?executionId=$BUDGET_EXEC_ID"   | tee /tmp/m8-budget-decisions.json   | jq .
jq -e 'any(.[]; .action=="DENY" and .budgetName=="m8-smoke-one-token")'   /tmp/m8-budget-decisions.json >/dev/null

curl -fsS -X DELETE "$BASE_URL/v1/governance/budgets/$BUDGET_ID" >/dev/null
BUDGET_ID=""

echo "[7/7] Inspect metered baseline usage"
USAGE="$(curl -fsS "$BASE_URL/v1/governance/executions/$BASELINE_ID/usage")"
jq . <<<"$USAGE"
jq -e '.total.total_tokens > 0' <<<"$USAGE" >/dev/null

echo
echo "M8.1 / M8.2 smoke test PASSED."
echo "Baseline execution: $BASELINE_ID"
echo "Policy-blocked:     $BLOCKED_ID"
echo "Budget-blocked:     $BUDGET_EXEC_ID"
