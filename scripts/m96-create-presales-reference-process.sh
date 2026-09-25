#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PROCESS_PLATFORM_URL:-http://localhost:8090}"
CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://localhost:8081}"
SOURCE_MODE="${PROPOSAL_SOURCE_MODE:-mock}"
DRIVE_FOLDER_ID="${GOOGLE_DRIVE_FOLDER_ID:-mock-drive-folder}"
OPPORTUNITY_ID="${OPPORTUNITY_ID:-OPP-DEMO-001}"
CUSTOMER_NAME="${CUSTOMER_NAME:-Acme Demo}"
OUTPUT_FOLDER_ID="${GOOGLE_DRIVE_OUTPUT_FOLDER_ID:-}"
OUTPUT_LANGUAGE="${OUTPUT_LANGUAGE:-auto}"
KEY="presales-reference-$(date +%s)"
SERVICE_KEY="$KEY.source"

command -v curl >/dev/null
command -v jq >/dev/null

if [[ "$SOURCE_MODE" != "mock" && "$SOURCE_MODE" != "drive" ]]; then
  echo "PROPOSAL_SOURCE_MODE must be mock or drive" >&2
  exit 1
fi

echo "== Presales qualification reference process =="
echo "source mode: $SOURCE_MODE"

if [[ "$SOURCE_MODE" == "drive" ]]; then
  SERVICE_BODY=$(cat <<JSON
{
  "serviceKey":"$SERVICE_KEY",
  "name":"Google Drive proposal source",
  "description":"Lists the input files for a presales opportunity from Google Drive.",
  "version":1,
  "implementationKey":"google-drive-folder",
  "configuration":{
    "folderIdPath":"processInput.driveFolderId"
  },
  "inputSchema":{"type":"object"},
  "outputSchema":{"type":"object","required":["folderId","documents"]}
}
JSON
)
else
  SERVICE_BODY=$(cat <<JSON
{
  "serviceKey":"$SERVICE_KEY",
  "name":"Mock proposal source",
  "description":"Smoke/demo source. Echoes process input so the agent can analyse embedded sample documents.",
  "version":1,
  "implementationKey":"echo",
  "configuration":{},
  "inputSchema":{"type":"object"},
  "outputSchema":{"type":"object"}
}
JSON
)
fi

SERVICE=$(curl -fsS -X POST "$BASE_URL/v1/process-services" \
  -H 'Content-Type: application/json' \
  -d "$SERVICE_BODY")
SERVICE_ID=$(jq -r '.id' <<<"$SERVICE")
curl -fsS -X POST "$BASE_URL/v1/process-services/$SERVICE_ID/activate" >/dev/null

echo "source service ACTIVE: $SERVICE_KEY"

DEF_BODY=$(cat <<JSON
{
  "definitionKey":"$KEY",
  "name":"Presales qualification, solution design and RFP response",
  "description":"Reference process: source documents -> business qualification -> human review loop -> solution design with specialists -> human review loop -> final RFP/RFI response.",
  "version":1,
  "inputSchema":{
    "type":"object",
    "required":["opportunityId","customerName","driveFolderId"]
  },
  "outputSchema":{"type":"object"},
  "steps":[
    {
      "stepKey":"load-input-documents",
      "name":"Load input documents",
      "description":"Discover the documents that form the customer proposal input.",
      "type":"SERVICE",
      "dependsOn":[],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "serviceKey":"$SERVICE_KEY",
        "serviceVersion":1,
        "retry":{"maxAttempts":2,"backoffMs":1000},
        "timeoutSeconds":30
      }
    },
    {
      "stepKey":"business-analysis",
      "name":"Analyse and qualify customer need",
      "description":"Produce an understanding and qualification report for presales.",
      "type":"AGENTIC_EXECUTION",
      "dependsOn":["load-input-documents"],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "name":"presales-business-analysis",
        "intent":"Act as a senior business analyst / presales consultant. Analyse the customer proposal documents and produce a structured understanding and qualification report. Determine what the customer wants, why they want it, desired timeline, business drivers, constraints, assumptions, missing information, what we can contribute, execution risks and mitigations. If dependencies.load-input-documents contains Google Drive document ids, use google-drive-read-file for each relevant file ID to read the actual document contents. If only a Drive folder ID is available, use google-drive-list-folder first. If this is a mock run, analyse processInput.documents. IMPORTANT: inspect context._reviewHistory.business-analysis-review. If previous human feedback exists, revise the previous report accordingly instead of starting from scratch. Return a concise but complete structured result suitable for the next human review.",
        "instructions":[
          "Ground the report in the supplied customer material.",
          "Separate facts, assumptions, risks and open questions.",
          "Use previous human review feedback when present.",
          "Do not design the technical solution yet."
        ],
        "retry":{"maxAttempts":2,"backoffMs":2000},
        "timeoutSeconds":180
      }
    },
    {
      "stepKey":"business-analysis-review",
      "name":"Validate understanding and qualification",
      "description":"A business analyst or presales owner validates the qualification report or requests another iteration.",
      "type":"HUMAN",
      "dependsOn":["business-analysis"],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "title":"Validate customer understanding and qualification",
        "description":"Review the generated qualification report. APPROVE to continue or REQUEST_CHANGES with concrete feedback.",
        "review":{
          "repeatStep":"business-analysis",
          "approveDecision":"APPROVE",
          "repeatDecision":"REQUEST_CHANGES",
          "maxIterations":5
        }
      }
    },
    {
      "stepKey":"solution-design",
      "name":"Design technical solution",
      "description":"Produce the detailed technical solution for the approved customer understanding.",
      "type":"AGENTIC_EXECUTION",
      "dependsOn":["business-analysis-review"],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "name":"solution-architecture",
        "intent":"Act as a senior solution architect. Using the approved customer understanding and qualification, design a detailed technical solution. Cover architecture, components, integrations, APIs/events, data, security, observability, deployment, cloud/infrastructure, NFRs, scalability, resilience, migration, implementation phases, assumptions, risks and key technical decisions. IMPORTANT: inspect context._reviewHistory.solution-review. If previous architecture-review feedback exists, revise the previous solution accordingly instead of starting from scratch. Produce a structured technical solution document/result.",
        "instructions":[
          "Base the design on the approved business-analysis result.",
          "Make assumptions explicit.",
          "Explain major architecture decisions and trade-offs.",
          "Incorporate all previous human review feedback."
        ],
        "retry":{"maxAttempts":2,"backoffMs":2000},
        "timeoutSeconds":240
      }
    },
    {
      "stepKey":"solution-review",
      "name":"Validate technical solution",
      "description":"A human validates the architecture or requests another solution iteration.",
      "type":"HUMAN",
      "dependsOn":["solution-design"],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "title":"Validate technical solution",
        "description":"Review the proposed technical solution. APPROVE to continue to the final RFP/RFI response or REQUEST_CHANGES with specific architecture feedback.",
        "review":{
          "repeatStep":"solution-design",
          "approveDecision":"APPROVE",
          "repeatDecision":"REQUEST_CHANGES",
          "maxIterations":5
        }
      }
    },
    {
      "stepKey":"compose-rfp-response",
      "name":"Compose final RFP/RFI response",
      "description":"Build the customer-facing response using the original documents, approved qualification, approved solution and corporate presales knowledge.",
      "type":"AGENTIC_EXECUTION",
      "dependsOn":["solution-review"],
      "inputSchema":{"type":"object"},
      "outputSchema":{"type":"object"},
      "configuration":{
        "name":"rfp-response-authoring",
        "intent":"Act as the final RFP/RFI response owner. Use the original customer documents, the approved business-analysis result and the approved solution-design result as authoritative inputs. Determine first whether the customer explicitly requires a response structure, template, section numbering, questionnaire or compliance matrix. If it does, follow that structure exactly and answer every requested section. If it does not, use the presales-corporate Knowledge Base standard RFP response template. Never invent company capabilities, references, certifications, SLAs, commercial commitments or dates. Use corporate Knowledge only when it contains validated evidence. Produce a complete customer-facing response. If processInput.outputFolderId is non-empty, materialize the final response as a Google Doc using google-docs-create-with-text with a descriptive title and that destination folder. Otherwise return the final response as structured content without creating an external document.",
        "instructions":[
          "Prefer the customer-required response structure over the corporate template.",
          "Use only approved qualification and approved technical solution content.",
          "Use presales-corporate Knowledge for the default template and validated corporate guidance.",
          "Keep assumptions, dependencies and open questions explicit.",
          "If outputFolderId is present, use google-docs-create-with-text; this write action requires platform approval.",
          "Write in processInput.outputLanguage when explicitly set, otherwise use the main language of the customer documents."
        ],
        "retry":{"maxAttempts":2,"backoffMs":2000},
        "timeoutSeconds":240
      }
    }
  ]
}
JSON
)

DEF=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions" \
  -H 'Content-Type: application/json' \
  -d "$DEF_BODY")
DEF_ID=$(jq -r '.id' <<<"$DEF")
ACTIVE=$(curl -fsS -X POST "$BASE_URL/v1/process-definitions/$DEF_ID/activate")
jq -e '.status=="ACTIVE"' <<<"$ACTIVE" >/dev/null

echo "process definition ACTIVE: $KEY"

if [[ "$SOURCE_MODE" == "mock" ]]; then
  INPUT=$(cat <<JSON
{
  "opportunityId":"$OPPORTUNITY_ID",
  "customerName":"$CUSTOMER_NAME",
  "driveFolderId":"$DRIVE_FOLDER_ID",
  "outputFolderId":"$OUTPUT_FOLDER_ID",
  "outputLanguage":"$OUTPUT_LANGUAGE",
  "documents":[
    {
      "name":"RFP.md",
      "content":"The customer wants to modernize a legacy order platform, reduce release lead time, support 3x peak traffic and complete the first production migration in six months. Current pain points include manual deployments, fragile point-to-point integrations and limited observability."
    },
    {
      "name":"constraints.md",
      "content":"The solution must run on AWS, integrate with the existing ERP, preserve customer identifiers, support zero-downtime releases and provide an auditable migration path. Security review is mandatory before production."
    }
  ]
}
JSON
)
else
  INPUT=$(cat <<JSON
{
  "opportunityId":"$OPPORTUNITY_ID",
  "customerName":"$CUSTOMER_NAME",
  "driveFolderId":"$DRIVE_FOLDER_ID",
  "outputFolderId":"$OUTPUT_FOLDER_ID",
  "outputLanguage":"$OUTPUT_LANGUAGE"
}
JSON
)
fi

INSTANCE=$(curl -fsS -X POST "$BASE_URL/v1/process-instances" \
  -H 'Content-Type: application/json' \
  -d "{
    \"definitionKey\":\"$KEY\",
    \"version\":1,
    \"correlationId\":\"$OPPORTUNITY_ID\",
    \"input\":$INPUT,
    \"context\":{}
  }")
INSTANCE_ID=$(jq -r '.id' <<<"$INSTANCE")
curl -fsS -X POST "$BASE_URL/v1/process-instances/$INSTANCE_ID/start" >/dev/null

echo
echo "Process started"
echo "  definition: $KEY v1"
echo "  instance:   $INSTANCE_ID"
echo "  correlation:$OPPORTUNITY_ID"
echo
echo "Open the Control Plane:"
echo "  $CONTROL_PLANE_URL"
echo "  Processes -> Instances -> $INSTANCE_ID"
echo
echo "The first HUMAN task will appear after business-analysis completes."
echo "Choose REQUEST_CHANGES and add JSON feedback, for example:"
echo '  {"comment":"Clarify the deadline and reassess migration risk."}'
echo
echo "The business-analysis AGENTIC_EXECUTION will run again with:"
echo "  - previous output still visible in process context"
echo "  - context._reviewHistory.business-analysis-review"
echo
echo "Then APPROVE it to continue to solution-design."
echo "Repeat the same REQUEST_CHANGES -> APPROVE cycle for solution-review."
echo "After solution approval, compose-rfp-response will build the final customer response."
echo "If GOOGLE_DRIVE_OUTPUT_FOLDER_ID is set, the agent will request approval to create the final Google Doc."
echo
echo "For a real Drive run:"
echo "  export PROPOSAL_SOURCE_MODE=drive"
echo "  export GOOGLE_DRIVE_FOLDER_ID=<folder-id>"
echo "  export GOOGLE_DRIVE_OUTPUT_FOLDER_ID=<output-folder-id>   # optional"
echo "  export OUTPUT_LANGUAGE=es                                  # optional"
echo "  # Both platforms reuse .secrets/google-token.json generated by:"
echo "  # npm --prefix mcp/google-workspace run auth"
echo "  # Validate Agent Platform Drive access first: bash scripts/google-workspace-mcp-smoke.sh"
echo "  docker compose up -d --force-recreate process-platform"
echo "  bash scripts/m96-create-presales-reference-process.sh"
