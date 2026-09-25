# AI Agent Platform

Intent-driven AI execution platform with declarative Agents, Skills, Tools/MCP, managed Knowledge/RAG, LangGraph orchestration, durable execution, Context/Memory, deterministic Governance and an Angular Control Plane.

## Local stack

```bash
docker compose build
docker compose up -d
```

Main entry points:

| Component | URL |
| --- | --- |
| Control Plane (Angular) | http://localhost:8081 |
| Agent Platform API | http://localhost:8080 |
| OpenAPI | http://localhost:8080/docs |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |
| NATS Monitor | http://localhost:8222 |

Architecture and ADRs are documented in `docs/architecture.md`. Runtime details and milestone examples are in `agent-platform/README.md`.

## Milestones

```text
M0  Walking Skeleton / Execution       ✅
M1  Agents / Skills / Prompts          ✅
M2  Tools / MCP                        ✅
M3  Managed Knowledge / RAG            ✅
M4  Agentic Orchestration / LangGraph  ✅
M5  Durable Execution                  ✅
M6  Angular Control Plane              ✅
M7  Context & Memory                  ✅
    M7.1 Sessions + Working Context    ✅
    M7.2 Persistent Memory + Policies  ✅
    M7.3 Context Engine + Budgets      ✅
    M7.4 Context snapshots + UI        ✅
M8  Governance & Evals
    M8.1 Policy Engine + Authorization  ✅
    M8.2 Budget / Cost Governance       ✅
    M8.3 Eval Framework                 next
    M8.4 Regression Datasets + UI
M9  Semantic Layer
```


---

## M9.1 — Process Platform

The repository now also contains an independent Spring Boot service:

```text
process-platform/
```

Its responsibility in M9.1 is only the standard asynchronous integration with
Agent Platform:

```text
Process Platform
  -> ExecutionCommand
  -> NATS
  -> Agent Platform
  -> ExecutionEvent
  -> NATS
  -> Process Platform
```

It uses Java 21 / Spring Boot 3.5 and the package structure:

```text
com.jaruizes.processplatform.business
com.jaruizes.processplatform.domain
com.jaruizes.processplatform.infrastructure
```

See `process-platform/README.md` and run:

```bash
bash scripts/m9-process-platform-smoke.sh
```


### M9.2 — Process Domain

Process Platform now owns durable deterministic process state:

```text
ProcessDefinition -> versioned DAG + step I/O contracts
ProcessInstance   -> exact definition version + ProcessContext
ProcessStepInstance -> materialized durable step state
```

Definitions are editable only in `DRAFT`; ACTIVE versions are immutable and
changes are made by cloning a new version.

Process Platform uses its own PostgreSQL database and can be started independently
from Agent Platform.

Validate M9.2 with:

```bash
docker compose up -d process-postgres nats otel-collector process-platform
bash scripts/m9-process-domain-smoke.sh
```


### M9.3 — Deterministic Process Runtime

Process Platform can now execute the persisted deterministic DAG.

Implemented runtime semantics:

```text
PENDING -> READY -> RUNNING
SERVICE -> COMPLETED
AGENTIC_EXECUTION -> WAITING -> ExecutionEvent -> COMPLETED
```

Ready branches execute concurrently, ProcessContext merges are serialized,
agent delegation uses a transactional command outbox, and persisted runtime state
is recovered after restart.

Validate locally with:

```bash
bash scripts/m9-process-runtime-smoke.sh
bash scripts/m9-process-runtime-agentic-smoke.sh
```


### M9.4 — Process Capabilities & Long-running Workflow

Process Platform now adds the primitives required before the visual designer:

```text
Service Registry       -> discoverable/versioned deterministic capabilities
DECISION               -> deterministic branching
HUMAN                  -> durable human tasks
WAIT_EVENT             -> durable correlated external waits
PAUSE/RESUME/CANCEL    -> runtime controls
RETRY/TIMEOUT          -> persisted execution policies
```

SERVICE references are pinned to an exact catalog version when a
ProcessDefinition is activated. Agent Tools/MCP remain exclusively inside Agent
Platform.

Validate locally with:

```bash
bash scripts/m9-process-long-running-smoke.sh
```


### M9.5 — Process Control Plane

The Angular Control Plane now manages both bounded contexts without merging
their APIs.

Process Platform UI includes:

```text
Visual ProcessDefinition designer
Process Service catalog/version lifecycle
Process Instance runtime explorer
Human Task inbox
External event signaling
Agentic execution drill-down
```

Nginx routes `/api/*` to Agent Platform and `/process-api/*` to Process
Platform.

Validate:

```bash
cd control-plane-ui && npm run build
docker compose up -d --build
bash scripts/m95-process-control-plane-smoke.sh
```


### M9.6 — Controlled Human Review Loops

Process Platform now supports review-driven iteration without allowing arbitrary
dependency cycles.

A HUMAN step can request that its direct SERVICE/AGENTIC producer run again,
with previous output and append-only review feedback available in
`context._reviewHistory`.

Reference process:

```bash
bash scripts/m96-create-presales-reference-process.sh
```

Deterministic review-loop smoke:

```bash
bash scripts/m96-review-loop-smoke.sh
```

An optional `google-drive-folder` Process SERVICE discovers proposal files from
Google Drive. Agents still read/analyse document content through Agent Platform
Tools/MCP.


### Google Workspace MCP / Drive Reader

Agent Platform includes a Google Workspace MCP plus bootstrap Tools for Drive,
Docs, Sheets and Slides.

For document reasoning the preferred Tool is:

```text
google-drive-read-file
```

It accepts a Drive `fileId` and automatically returns semantic text from:

```text
Google Docs
Google Sheets
Google Slides
PDF
DOCX / DOC
PPTX / PPT
XLSX / XLS
CSV / TXT / MD / JSON
ODT / ODP / ODS
```

Google-native files use native Workspace APIs. Binary/legacy files are
downloaded to scratch storage and parsed with Agent Platform's existing
`DocumentParser`.

Setup OAuth:

```bash
npm --prefix mcp/google-workspace install
npm --prefix mcp/google-workspace run auth
```

Then rebuild and validate:

```bash
docker compose up -d --build agent-platform

bash scripts/google-workspace-mcp-smoke.sh
```

Optionally test a real file end to end:

```bash
GOOGLE_DRIVE_TEST_FILE_ID=<file-id> \
  bash scripts/google-workspace-mcp-smoke.sh
```

The proposal reference process uses this Tool from its AGENTIC_EXECUTION steps;
Process Platform never invokes the MCP directly.


### Presales / RFP complex-use-case bootstrap

Agent Platform now starts with a complete reusable presales catalog.

#### Agents

```text
business-analyst
solution-architect
security-architect
cloud-architect
data-architect
integration-architect
technology-specialist
rfp-response-writer
```

Agent keys remain technical English identifiers. Descriptions and operating
instructions are written in Spanish.

Agents describe stable roles and working principles. Concrete procedures live
in Skills.

#### Skills

```text
proposal-understanding
proposal-qualification
proposal-risk-analysis
solution-architecture
security-assessment
cloud-architecture
data-architecture
integration-architecture
technology-assessment
specialist-consultation
rfp-response-authoring
technical-writing
```

This allows the planner to compose different agents and skills depending on the
opportunity instead of hard-coding specialists in Process Platform.

#### Default Knowledge Bases

Two persistent TENANT Knowledge Bases are bootstrapped as code:

```text
presales-corporate
  ├── standard-rfp-response-template.md
  ├── proposal-qualification-checklist.md
  ├── proposal-writing-guidelines.md
  └── company-capabilities-PLACEHOLDER.md

architecture-standards
  ├── architecture-principles.md
  └── solution-review-checklist.md
```

Bootstrap documents are checksum-versioned. Restarting does not duplicate them;
changing a Markdown source replaces/reindexes the existing bootstrap document.

The company-capabilities document is deliberately a placeholder and explicitly
forbids agents from inventing company capabilities, references, certifications
or differentiators. Replace it with validated company content before relying on
those sections in real proposals.

Knowledge assignments are also bootstrapped:

```text
business-analyst      -> presales-corporate
rfp-response-writer   -> presales-corporate

solution-architect    -> architecture-standards + presales-corporate
security-architect    -> architecture-standards
cloud-architect       -> architecture-standards
data-architect        -> architecture-standards
integration-architect -> architecture-standards
technology-specialist -> architecture-standards
```

Existing user-added Knowledge assignments are preserved and merged with required
bootstrap assignments.

#### Google Workspace read/write Tools

Read:

```text
google-drive-list-folder
google-drive-get-file
google-drive-read-file
google-docs-get-text
google-sheets-get-text
google-slides-get-text
```

Governed write:

```text
google-docs-create-with-text
google-docs-create-document
google-docs-batch-update
google-drive-create-folder
google-drive-move-file
google-drive-copy-file
```

All write Tools use:

```text
sideEffect     = WRITE
approvalPolicy = REQUIRED
```

The preferred way to materialize a generated proposal/report is
`google-docs-create-with-text`. It can create the document, write the generated
content and place it in an opportunity Drive folder in one governed operation.

#### Validation

After rebuilding Agent Platform:

```bash
docker compose up -d --build agent-platform

bash scripts/presales-bootstrap-smoke.sh
bash scripts/google-workspace-mcp-smoke.sh
```

Then open the Control Plane and inspect Agents, Skills, Tools and Knowledge.

The full reference workflow is:

```bash
bash scripts/m96-create-presales-reference-process.sh
```

For a real Drive opportunity:

```bash
export PROPOSAL_SOURCE_MODE=drive
export GOOGLE_DRIVE_FOLDER_ID=<input-folder-id>
export GOOGLE_DRIVE_OUTPUT_FOLDER_ID=<output-folder-id>
export OUTPUT_LANGUAGE=es

bash scripts/m96-create-presales-reference-process.sh
```
