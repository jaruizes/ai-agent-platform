#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
POLL_SECONDS="${POLL_SECONDS:-2}"
MAX_POLLS="${MAX_POLLS:-120}"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M8.3 / M8.4 eval smoke test =="

DATASET_NAME="m8-eval-smoke-$(date +%s)"
DEFINITION_NAME="m8-eval-definition-$(date +%s)"

DATASET=$(curl -fsS -X POST "$BASE_URL/v1/evals/datasets"   -H 'Content-Type: application/json'   -d "{
    \"name\":\"$DATASET_NAME\",
    \"description\":\"Deterministic M8 eval smoke dataset\",
    \"version\":1,
    \"enabled\":true,
    \"items\":[{
      \"name\":\"api-gateway-case\",
      \"command\":{
        \"name\":\"m8-eval-smoke\",
        \"intent\":\"Explain in one short sentence what an API Gateway is.\",
        \"input\":{},
        \"context\":{},
        \"instructions\":[\"Return a non-empty answer.\"]
      },
      \"expectedOutput\":\"A short explanation of API Gateway\",
      \"assertions\":[{\"type\":\"MIN_LENGTH\",\"value\":10}],
      \"tags\":[\"smoke\",\"m8\"]
    }]
  }")
DATASET_ID=$(jq -r '.id' <<<"$DATASET")
echo "dataset=$DATASET_ID"

DEFINITION=$(curl -fsS -X POST "$BASE_URL/v1/evals/definitions"   -H 'Content-Type: application/json'   -d "{
    \"name\":\"$DEFINITION_NAME\",
    \"description\":\"Assertions-only eval smoke test\",
    \"datasetId\":\"$DATASET_ID\",
    \"metrics\":[],
    \"thresholds\":{\"passRate\":1.0},
    \"judgeModelProfile\":null,
    \"enabled\":true
  }")
DEFINITION_ID=$(jq -r '.id' <<<"$DEFINITION")
echo "definition=$DEFINITION_ID"

RUN=$(curl -fsS -X POST "$BASE_URL/v1/evals/definitions/$DEFINITION_ID/runs"   -H 'Content-Type: application/json' -d '{}')
RUN_ID=$(jq -r '.id' <<<"$RUN")
echo "run=$RUN_ID"

for ((i=1;i<=MAX_POLLS;i++)); do
  DETAIL=$(curl -fsS "$BASE_URL/v1/evals/runs/$RUN_ID")
  STATUS=$(jq -r '.status' <<<"$DETAIL")
  echo "poll $i: $STATUS"
  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq . <<<"$DETAIL"
    jq -e '.aggregateScores.passRate == 1 and .passedCases == 1 and .results[0].passed == true' <<<"$DETAIL" >/dev/null
    break
  fi
  if [[ "$STATUS" == "FAILED" ]]; then
    jq . <<<"$DETAIL"
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

BASELINE_ID="$RUN_ID"
SECOND=$(curl -fsS -X POST "$BASE_URL/v1/evals/definitions/$DEFINITION_ID/runs"   -H 'Content-Type: application/json'   -d "{\"baselineRunId\":\"$BASELINE_ID\"}")
SECOND_ID=$(jq -r '.id' <<<"$SECOND")

for ((i=1;i<=MAX_POLLS;i++)); do
  DETAIL=$(curl -fsS "$BASE_URL/v1/evals/runs/$SECOND_ID")
  STATUS=$(jq -r '.status' <<<"$DETAIL")
  if [[ "$STATUS" == "COMPLETED" ]]; then
    jq -e '.regression.baselineRunId != null and .aggregateScores.passRate == 1' <<<"$DETAIL" >/dev/null
    echo "baseline comparison OK"
    break
  fi
  [[ "$STATUS" != "FAILED" ]] || { jq . <<<"$DETAIL"; exit 1; }
  sleep "$POLL_SECONDS"
done

echo
echo "M8.3 / M8.4 eval smoke test PASSED."
echo "Dataset:    $DATASET_ID"
echo "Definition: $DEFINITION_ID"
echo "Run:        $RUN_ID"
echo "Comparison: $SECOND_ID"
echo "Open http://localhost:8081 and inspect Governance + Evals."
