#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${AGENT_PLATFORM_URL:-http://localhost:8080}"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== Presales bootstrap smoke test =="

AGENTS=$(curl -fsS "$BASE_URL/v1/agents")
SKILLS=$(curl -fsS "$BASE_URL/v1/skills")
TOOLS=$(curl -fsS "$BASE_URL/v1/tools")
KBS=$(curl -fsS "$BASE_URL/v1/knowledge-bases")

required_agents=(
  business-analyst
  solution-architect
  security-architect
  cloud-architect
  data-architect
  integration-architect
  technology-specialist
  rfp-response-writer
)

required_skills=(
  proposal-understanding
  proposal-qualification
  proposal-risk-analysis
  solution-architecture
  security-assessment
  cloud-architecture
  data-architecture
  integration-architecture
  technology-assessment
  rfp-response-authoring
  technical-writing
  specialist-consultation
)

required_tools=(
  google-drive-list-folder
  google-drive-read-file
  google-docs-create-with-text
  google-docs-create-document
  google-docs-batch-update
  google-drive-create-folder
  google-drive-move-file
  google-drive-copy-file
)

required_kbs=(
  presales-corporate
  architecture-standards
)

for name in "${required_agents[@]}"; do
  jq -e --arg name "$name" 'any(.[]; .name==$name and .enabled==true and .source=="BOOTSTRAP")' <<<"$AGENTS" >/dev/null
done
echo "agents OK (${#required_agents[@]})"

for name in "${required_skills[@]}"; do
  jq -e --arg name "$name" 'any(.[]; .name==$name and .enabled==true and .source=="BOOTSTRAP")' <<<"$SKILLS" >/dev/null
done
echo "skills OK (${#required_skills[@]})"

for name in "${required_tools[@]}"; do
  jq -e --arg name "$name" 'any(.[]; .name==$name and .enabled==true and .source=="BOOTSTRAP")' <<<"$TOOLS" >/dev/null
done

jq -e '
  any(.[]; .name=="google-docs-create-with-text"
      and .sideEffect=="WRITE"
      and .approvalPolicy=="REQUIRED")
' <<<"$TOOLS" >/dev/null
echo "read/write Google Workspace tools OK"

for name in "${required_kbs[@]}"; do
  KB_ID=$(jq -r --arg name "$name" '.[] | select(.name==$name and .enabled==true) | .id' <<<"$KBS" | head -1)
  [[ -n "$KB_ID" && "$KB_ID" != "null" ]]
  DOCS=$(curl -fsS "$BASE_URL/v1/knowledge-bases/$KB_ID/documents")
  jq -e 'length > 0' <<<"$DOCS" >/dev/null
  echo "knowledge base $name OK ($(jq 'length' <<<"$DOCS") documents)"
done

for agent_name in business-analyst solution-architect rfp-response-writer; do
  AGENT_ID=$(jq -r --arg name "$agent_name" '.[] | select(.name==$name) | .id' <<<"$AGENTS" | head -1)
  ASSIGNMENTS=$(curl -fsS "$BASE_URL/v1/agents/$AGENT_ID/knowledge-bases")
  jq -e 'length > 0' <<<"$ASSIGNMENTS" >/dev/null
  echo "$agent_name knowledge assignments OK"
done

echo
echo "Presales bootstrap smoke test PASSED."
