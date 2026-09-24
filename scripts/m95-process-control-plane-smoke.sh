#!/usr/bin/env bash
set -euo pipefail

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://localhost:8081}"

command -v curl >/dev/null
command -v jq >/dev/null

echo "== M9.5 Process Control Plane smoke test =="

INDEX=$(curl -fsS "$CONTROL_PLANE_URL/")
grep -q "app-root" <<<"$INDEX"
echo "Control Plane SPA reachable"

SERVICES=$(curl -fsS "$CONTROL_PLANE_URL/process-api/v1/process-services?activeOnly=true")
jq -e 'type=="array"' <<<"$SERVICES" >/dev/null
echo "Process Platform proxy reachable"

DEFINITIONS=$(curl -fsS "$CONTROL_PLANE_URL/process-api/v1/process-definitions")
jq -e 'type=="array"' <<<"$DEFINITIONS" >/dev/null

INSTANCES=$(curl -fsS "$CONTROL_PLANE_URL/process-api/v1/process-instances")
jq -e 'type=="array"' <<<"$INSTANCES" >/dev/null

TASKS=$(curl -fsS "$CONTROL_PLANE_URL/process-api/v1/human-tasks?pendingOnly=true")
jq -e 'type=="array"' <<<"$TASKS" >/dev/null

AGENT_OVERVIEW=$(curl -fsS "$CONTROL_PLANE_URL/api/v1/admin/overview")
jq -e 'type=="object"' <<<"$AGENT_OVERVIEW" >/dev/null

echo "Agent Platform and Process Platform are both reachable through one Control Plane"
echo
echo "M9.5 Process Control Plane smoke test PASSED."
