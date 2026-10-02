#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${AGENT_PLATFORM_URL:-http://localhost:8080}"
EXECUTION_ID="${ARTIFACT_EXECUTION_ID:-}"
PROCESS_INSTANCE_ID="${PROCESS_INSTANCE_ID:-}"
PROCESS_STEP_KEY="${PROCESS_STEP_KEY:-}"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== Artifact & Handoff Layer smoke test =="

if [[ -n "$EXECUTION_ID" ]]; then
  ARTIFACTS=$(curl -fsS "$BASE_URL/v1/executions/$EXECUTION_ID/artifacts")
elif [[ -n "$PROCESS_INSTANCE_ID" && -n "$PROCESS_STEP_KEY" ]]; then
  SCOPE="process:$PROCESS_INSTANCE_ID:step:$PROCESS_STEP_KEY"
  ARTIFACTS=$(curl -fsS --get "$BASE_URL/v1/artifacts" \
    --data-urlencode "scopeKey=$SCOPE" \
    --data-urlencode "latestOnly=true")
else
  cat >&2 <<'EOF'
Set either:

  ARTIFACT_EXECUTION_ID=<agent-execution-id>

or:

  PROCESS_INSTANCE_ID=<process-instance-id>
  PROCESS_STEP_KEY=<agentic-step-key>
EOF
  exit 2
fi

COUNT=$(jq 'length' <<<"$ARTIFACTS")
[[ "$COUNT" -gt 0 ]]

echo "artifacts: $COUNT"
jq -r '.[] | "  - (.type) · v(.version) · (.schema) · (.sizeBytes) bytes · (.title)"' <<<"$ARTIFACTS"

for type in HUMAN_DOCUMENT MACHINE_DATA AGENT_HANDOFF; do
  jq -e --arg type "$type" 'any(.[]; .type==$type)' <<<"$ARTIFACTS" >/dev/null
done

# List endpoints must remain metadata-only.
jq -e 'all(.[]; has("content")|not)' <<<"$ARTIFACTS" >/dev/null
echo "metadata-only list contract OK"

HUMAN_ID=$(jq -r '[.[] | select(.type=="HUMAN_DOCUMENT" or .type=="FINAL_DELIVERABLE")][0].id // empty' <<<"$ARTIFACTS")
[[ -n "$HUMAN_ID" ]]
HUMAN=$(curl -fsS "$BASE_URL/v1/artifacts/$HUMAN_ID")

jq -e '
  (.content.markdown // "") | type=="string" and length>0
' <<<"$HUMAN" >/dev/null

echo "human review artifact content OK"

MACHINE_ID=$(jq -r '[.[] | select(.type=="MACHINE_DATA")][0].id // empty' <<<"$ARTIFACTS")
HANDOFF_ID=$(jq -r '[.[] | select(.type=="AGENT_HANDOFF")][0].id // empty' <<<"$ARTIFACTS")
[[ -n "$MACHINE_ID" && -n "$HANDOFF_ID" ]]

MACHINE=$(curl -fsS "$BASE_URL/v1/artifacts/$MACHINE_ID")
HANDOFF=$(curl -fsS "$BASE_URL/v1/artifacts/$HANDOFF_ID")

jq -e '.content | type=="object"' <<<"$MACHINE" >/dev/null
jq -e '.content | type=="object"' <<<"$HANDOFF" >/dev/null

echo "machine artifact OK"
echo "agent handoff OK"

echo
echo "Artifact & Handoff Layer smoke test PASSED."
