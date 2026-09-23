# Agent Platform — M0

M0 implements the first end-to-end vertical slice of the platform:

```text
REST / NATS command
        |
        v
ExecutionCommand
        |
        v
Command Gateway / Execution Service
        |
        v
Intent Resolver
        |
        v
DIRECT_LLM execution plan
        |
        v
Model Gateway (LiteLLM)
        |
        v
Anthropic
        |
        v
PostgreSQL + Transactional Outbox
        |
        v
NATS JetStream events
```

The Intent Resolver boundary is already explicit, but M0 deliberately supports only one strategy: `DIRECT_LLM`. It does **not** map business command names to handlers or agents. Future milestones can make the resolver/planner choose tools, agents, skills, RAG or multi-step execution while keeping the same external contract.

## Why LiteLLM

LiteLLM is used as the initial **Model / AI Gateway**. The platform talks to an OpenAI-compatible gateway endpoint and does not hold the Anthropic API key directly. Provider/model changes therefore remain outside the runtime code.

In M0:

- agent-platform -> LiteLLM
- LiteLLM -> Anthropic

The alias seen by the platform is always `platform-default`.

## Start

```bash
cd agent-platform
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
docker compose up --build
```

Services:

| Service | URL |
|---|---|
| Agent Platform | http://localhost:8080 |
| OpenAPI | http://localhost:8080/docs |
| LiteLLM | http://localhost:4000 |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| NATS monitoring | http://localhost:8222 |

Grafana local credentials are `admin/admin`.

## REST example

```bash
curl -i -X POST http://localhost:8080/v1/executions \
  -H 'Content-Type: application/json' \
  -d '{
    "correlationId": "demo-001",
    "command": {
      "name": "analyse-text",
      "intent": "Analyse the supplied text and identify the main architectural risk.",
      "input": {
        "text": "The service writes to PostgreSQL and then publishes an event to NATS in a separate operation."
      },
      "context": {
        "systemType": "distributed-system"
      },
      "instructions": [
        "Focus on consistency problems."
      ]
    }
  }'
```

The HTTP response is only an acceptance:

```json
{
  "executionId": "...",
  "correlationId": "demo-001",
  "status": "ACCEPTED"
}
```

The functional result is published through NATS on:

```text
platform.events.execution.result
```

Lifecycle events are published on:

```text
platform.events.execution.lifecycle
```

The current state can also be queried:

```bash
curl http://localhost:8080/v1/executions/<executionId>
```

## NATS input example

Publish a canonical `ExecutionCommand` to:

```text
platform.commands.execution
```

Example payload:

```json
{
  "specVersion": "1.0",
  "messageId": "6e9fd4a9-f0f4-420d-bf2c-0dcb48b0671c",
  "messageType": "execution.command",
  "timestamp": "2026-09-22T10:00:00Z",
  "correlationId": "demo-nats-001",
  "causationId": null,
  "source": {
    "type": "application",
    "name": "demo-client"
  },
  "data": {
    "execution": {
      "command": {
        "name": "summarise",
        "intent": "Summarise the supplied content.",
        "input": {
          "content": "..."
        },
        "context": {},
        "instructions": []
      }
    }
  }
}
```

## Persistence and Outbox

Creation of an execution and its `EXECUTION_ACCEPTED` event are persisted in the same PostgreSQL transaction. Completion/failure and their corresponding events follow the same rule.

The outbox publisher later sends pending records to NATS JetStream. This provides eventual publication without pretending to provide end-to-end exactly-once delivery. Consumers must remain idempotent.

## M0 intentionally does not include

- intelligent strategy selection;
- agents;
- skills;
- tools or MCP;
- RAG / knowledge bases;
- memory;
- multi-agent planning;
- human approval;
- artifact storage.

Those are later vertical slices. M0 establishes the generic contracts, durable execution record, model gateway boundary and event-driven output.


---

# M1 — Configurable Agents & Skills

M1 adds a persistent catalog of agents and skills without introducing business-specific routing in code.

## Runtime flow

```text
ExecutionCommand
      |
      v
Intent Resolver
      |
      +---- DIRECT_LLM --------------------> LiteLLM
      |
      +---- AGENT
              |
              v
       Agent from database
              +
       assigned Skills
              |
              v
           LiteLLM
```

The Intent Resolver asks the model to decide whether a specialized registered agent materially improves the execution. There is no mapping such as:

```text
analyse-proposal -> ProposalAgent
```

Agents are selected from the catalog based on their descriptions and skills. If no agent is a clear match, execution remains `DIRECT_LLM`.

## Persistence

M1 creates:

- `skills`
- `agents`
- `agent_skills`

Agents and skills are normal database records and can be created, updated or deleted through REST without modifying platform code.

## Bootstrap from Markdown

On startup, the platform reads:

```text
bootstrap/
├── skills/
└── agents/
```

Bootstrap entries are inserted only when an item with the same name does not already exist. Existing database records are not overwritten, so user modifications survive restarts.

A skill is a Markdown file with YAML front matter:

```markdown
---
name: technical-risk-analysis
description: Identify technical architecture risks.
enabled: true
---

Identify concrete technical risks and explain their impact.
```

An agent references skills by name:

```markdown
---
name: technical-reviewer
description: Specialist software architecture reviewer.
skills:
  - technical-risk-analysis
  - summarization
enabled: true
---

Act as a senior software architecture reviewer.
```

M1 includes two bootstrap skills and two bootstrap agents:

- `summarization`
- `technical-risk-analysis`
- `document-analyst`
- `technical-reviewer`

## Catalog API

List:

```bash
curl http://localhost:8080/v1/skills
curl http://localhost:8080/v1/agents
```

Create a skill dynamically:

```bash
curl -X POST http://localhost:8080/v1/skills \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "plain-language",
    "description": "Explain complex ideas in simple language.",
    "instructions": "Use simple language and concrete examples.",
    "enabled": true
  }'
```

Create an agent dynamically using existing skills:

```bash
curl -X POST http://localhost:8080/v1/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "explainer",
    "description": "Specialist agent for explaining complex material to non-specialists.",
    "instructions": "Be precise but accessible.",
    "skills": ["plain-language", "summarization"],
    "enabled": true
  }'
```

`PUT /v1/skills/{id}`, `DELETE /v1/skills/{id}`, `PUT /v1/agents/{id}` and `DELETE /v1/agents/{id}` complete the basic CRUD.

## E2E test 1 — no agent required

This request should normally be resolved as `DIRECT_LLM`:

```bash
curl -X POST http://localhost:8080/v1/executions \
  -H 'Content-Type: application/json' \
  -d '{
    "correlationId": "m1-direct-001",
    "command": {
      "name": "simple-task",
      "intent": "Translate this sentence to Spanish.",
      "input": {
        "text": "The platform is ready."
      },
      "context": {},
      "instructions": []
    }
  }'
```

Query the returned execution ID:

```bash
curl http://localhost:8080/v1/executions/<executionId>
```

The completed result contains:

```json
{
  "data": {
    "strategy": "DIRECT_LLM"
  }
}
```

## E2E test 2 — agent selected dynamically

This request is designed to match the bootstrap `technical-reviewer` agent:

```bash
curl -X POST http://localhost:8080/v1/executions \
  -H 'Content-Type: application/json' \
  -d '{
    "correlationId": "m1-agent-001",
    "command": {
      "name": "review-system",
      "intent": "Review this software architecture and identify its main technical risks.",
      "input": {
        "architecture": "The service updates PostgreSQL and then publishes an event to NATS as a separate operation. There is no retry policy and all services share the same database."
      },
      "context": {
        "systemType": "distributed-system"
      },
      "instructions": [
        "Explain the impact of each risk and suggest practical mitigations."
      ]
    }
  }'
```

The resolver receives the currently enabled agents from the database. A successful specialized route will produce:

```json
{
  "data": {
    "strategy": "AGENT",
    "agent": "technical-reviewer"
  }
}
```

The functional result and lifecycle continue to be emitted through the same generic NATS contracts used in M0.


## M1.1 — Prompt Registry and Model Profiles

Platform prompts are no longer hardcoded in Python. They are persisted in PostgreSQL and bootstrapped from:

```text
bootstrap/prompts/
├── intent-router.md
├── direct-executor.md
└── agent-executor.md
```

The database is the source of truth at runtime. Bootstrap is **insert-if-missing** for skills, agents and prompts:

```text
Markdown exists + DB does not exist -> insert Markdown definition
Markdown exists + DB already exists   -> keep DB definition unchanged
```

Therefore an agent, skill or prompt edited through the API is never overwritten by a restart.

Prompt management API:

```text
GET    /v1/prompts
POST   /v1/prompts
PUT    /v1/prompts/{id}
DELETE /v1/prompts/{id}
```

The resolver and execution use different LiteLLM aliases:

```text
router-fast       -> cheap/fast model used only for intent routing
reasoning-default -> normal model used for DIRECT_LLM and AGENT execution
```

Configure the actual Anthropic models in `.env`:

```env
ANTHROPIC_ROUTER_MODEL=anthropic/claude-haiku-4-5-20251001
ANTHROPIC_EXECUTION_MODEL=anthropic/claude-sonnet-4-5-20250929
```

The platform code only knows the profile names `router-fast` and `reasoning-default`, not the provider model IDs.


---

# M2 — Declarative Tools & MCP

M2 adds tools as first-class platform resources. A tool is declarative and persisted in PostgreSQL; MCP is one implementation mechanism, not a business abstraction.

The resolver can now select:

```text
DIRECT_LLM
AGENT
TOOL
TOOL_LLM
AGENT_TOOL_LLM
```

There is still no business mapping in code. The resolver receives the enabled agents and tools, their descriptions and tool input schemas, and chooses the smallest valid execution strategy.

## Persistent registries

M2 adds:

```text
tools
mcp_servers
```

and bootstrap folders:

```text
bootstrap/
├── tools/
└── mcp-servers/
```

The same precedence rule applies to skills, agents, prompts, tools and MCP servers:

```text
Markdown exists + DB missing       -> insert bootstrap definition
Markdown exists + DB already exists -> keep DB definition unchanged
```

PostgreSQL remains the runtime source of truth.

## Google Workspace MCP

The Google Workspace MCP from `jaruizes/proposal-app` is included under:

```text
mcp/google-workspace/
```

The agent-platform image builds and packages this MCP server and launches it through stdio only when an MCP-backed tool is invoked.

M2 bootstraps:

```text
MCP server:
  google-workspace

Tools:
  google-docs-get-document
  google-drive-search-files
```

The tool definition points to a logical MCP server and remote tool:

```yaml
configuration:
  server: google-workspace
  tool: docs_get_document
```

No Google-specific code exists in the business layer.

## Google OAuth setup

The compose mounts:

```text
./.secrets:/run/secrets/google:ro
```

For the Google Workspace MCP place these files in the repository root:

```text
.secrets/
├── google-oauth-credentials.json
└── google-token.json
```

If you already authenticated the MCP in `proposal-app`, the simplest local setup is to copy/reuse those two files.

Do not commit this directory; `.secrets/` is ignored by git.

## Tool and MCP APIs

```text
GET    /v1/tools
POST   /v1/tools
PUT    /v1/tools/{id}
DELETE /v1/tools/{id}

GET    /v1/mcp-servers
POST   /v1/mcp-servers
PUT    /v1/mcp-servers/{id}
DELETE /v1/mcp-servers/{id}
```

## E2E: summarize a Google Doc

Rebuild because M2 adds Node/MCP assets to the agent-platform image:

```bash
docker compose build --no-cache agent-platform
docker compose up -d
```

Validate bootstrap:

```bash
curl http://localhost:8080/v1/mcp-servers
curl http://localhost:8080/v1/tools
```

Take a Google Docs URL such as:

```text
https://docs.google.com/document/d/<DOCUMENT_ID>/edit
```

and submit:

```bash
curl -X POST http://localhost:8080/v1/executions \
  -H 'Content-Type: application/json' \
  -d '{
    "correlationId": "m2-drive-summary-001",
    "command": {
      "name": "summarize-drive-document",
      "intent": "Read this Google Docs document and give me a concise summary in Spanish with the main conclusions.",
      "input": {
        "documentId": "<DOCUMENT_ID>"
      },
      "context": {},
      "instructions": [
        "Do not invent information that is not present in the document."
      ]
    }
  }'
```

Query the returned execution:

```bash
curl http://localhost:8080/v1/executions/<executionId>
```

The resolver should choose a tool-based route. Depending on whether the specialized `drive-document-analyst` materially helps, either of these is valid:

```json
{
  "strategy": "TOOL_LLM",
  "tool": "google-docs-get-document"
}
```

or:

```json
{
  "strategy": "AGENT_TOOL_LLM",
  "agent": "drive-document-analyst",
  "tool": "google-docs-get-document"
}
```

The important M2 invariant is that the platform discovers/selects the declarative tool, invokes the Google Workspace MCP, obtains the Docs content and then uses the configured execution model to satisfy the intent.


---

# M4 — Agentic Orchestration with LangGraph

M4 introduces an LLM Planner and a typed multi-step `LogicalPlan`.

Runtime flow:

```text
ExecutionCommand
      |
      v
LLM Planner (planner-default)
      |
      v
LogicalPlan
      |
      v
Deterministic PlanValidator
      |
      v
OrchestrationEnginePort
      |
      v
LangGraphOrchestrationEngine
      |
      v
StepExecutor
      |
      +--> AGENT
      +--> TOOL
      +--> KNOWLEDGE
      +--> VALIDATE
      +--> MODEL
```

LangGraph is an implementation detail. The platform domain knows `LogicalPlan`, not LangGraph nodes or channels.

The planner can create sequential or parallel DAGs. Steps without dependencies can run concurrently; steps with multiple dependencies wait for the dependency join.

M4 persists plan and step state in PostgreSQL:

```text
execution_plans
execution_plan_steps
```

The state is explicitly UI-ready:

```text
PENDING -> RUNNING -> COMPLETED
                   -> FAILED
```

Each step exposes:

- type and description;
- assigned agent/tool/knowledge;
- dependencies;
- current status;
- start/end timestamps;
- output/error;
- model token usage.

The planner model usage is tracked separately and included in total execution usage.

Inspect a running execution:

```bash
curl http://localhost:8080/v1/executions/<EXECUTION_ID>/orchestration | jq
```

The response contains:

```json
{
  "status": "RUNNING",
  "plan": {
    "objective": "...",
    "finalStepId": "...",
    "logicalPlan": {},
    "validation": {},
    "planner": {
      "model": "...",
      "usage": {}
    }
  },
  "steps": [
    {
      "id": "design",
      "type": "AGENT",
      "description": "Design the solution architecture",
      "agent": "solution-architect",
      "status": "RUNNING",
      "usage": {}
    }
  ],
  "activeAgents": [
    {
      "stepId": "design",
      "agent": "solution-architect",
      "activity": "Design the solution architecture"
    }
  ],
  "usage": {
    "promptTokens": 0,
    "completionTokens": 0,
    "totalTokens": 0
  }
}
```

Orchestration progress is also emitted through:

```text
platform.events.execution.orchestration
```

with `PLAN_CREATED`, `PLAN_STARTED`, `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`, `PLAN_COMPLETED` and `PLAN_FAILED`.

The model profile is:

```text
planner-default
```

and defaults to `ANTHROPIC_PLANNER_MODEL`.

M4 intentionally does not add LangGraph durable checkpointing yet. Durable recovery, resume, human approval, configurable retries and cancellation remain M5.


---

# M5 — Durable Execution

M5 adds durable, recoverable execution on top of the M4 LangGraph runtime.

Implemented capabilities:

- worker leases and heartbeats;
- recovery after worker/pod failure;
- persisted per-step checkpoints;
- retry with exponential backoff;
- per-attempt timeout;
- pause/resume;
- cancellation;
- human approval gates;
- stable step idempotency keys.

Operational endpoints:

```text
POST /v1/executions/{id}/pause
POST /v1/executions/{id}/resume
POST /v1/executions/{id}/cancel
POST /v1/executions/{id}/retry
POST /v1/executions/{id}/steps/{stepId}/approval
GET  /v1/executions/{id}/orchestration
```

The orchestration view includes `waitingApprovals`, `retryingSteps`, attempts, retry timing, approval state, stable idempotency keys and token usage.

Recovery does not call the Planner again. The stored `LogicalPlan` is loaded, LangGraph is reconstructed, completed steps return persisted outputs and incomplete work continues.

Default runtime settings:

```env
EXECUTION_LEASE_SECONDS=30
EXECUTION_HEARTBEAT_SECONDS=10
EXECUTION_CONTROL_POLL_SECONDS=0.5
```

M5 uses at-least-once semantics for external side effects. Completed steps are not re-executed after recovery, but a process failure between an external side effect and checkpoint persistence can repeat that side effect. Side-effecting tools should therefore use the stable `executionId:stepId` idempotency key when the external system supports it.


## Deterministic human approval for Tools

Human approval is not trusted to the LLM alone. Each Tool now declares:

```text
sideEffect:
  NONE
  READ
  WRITE
  EXTERNAL_ACTION

approvalPolicy:
  NEVER
  OPTIONAL
  REQUIRED
```

The Planner sees this metadata, but the platform is authoritative:

```text
Planner
  -> LogicalPlan
  -> PlanPolicyEnricher
  -> PlanValidator
  -> persist effective plan
  -> LangGraph
  -> StepExecutor rechecks current Tool policy
  -> WAITING_APPROVAL when REQUIRED
```

`REQUIRED` forces `requiresApproval=true` even when the Planner returned false. `NEVER` suppresses a Tool-level approval proposed by the Planner. `OPTIONAL` preserves the Planner decision.

The runtime rechecks the current Tool policy immediately before execution. If a Tool changes to `REQUIRED` after the plan was created, the step is promoted to an approval gate and `STEP_APPROVAL_POLICY_ENFORCED` is emitted.

The orchestration API exposes:

```text
steps[].requiresApproval
steps[].approvalSource
steps[].toolPolicy.sideEffect
steps[].toolPolicy.approvalPolicy
steps[].approval
```

All current Google bootstrap tools are read-only and default to:

```text
sideEffect = READ
approvalPolicy = NEVER
```

To test the deterministic gate with an existing read Tool, temporarily update that Tool through `PUT /v1/tools/{toolId}` and set `approvalPolicy` to `REQUIRED`. The next plan that uses that Tool must enter `WAITING_APPROVAL` before the Tool call, regardless of what the Planner proposed.


---

# M6 — Angular Control Plane

M6 adds a separate Angular 20 administration and operations UI under:

```text
control-plane-ui/
```

Start it with the complete stack:

```bash
docker compose build control-plane-ui agent-platform
docker compose up -d
```

Open:

```text
http://localhost:8081
```

The UI follows the visual language of `proposal-app/feat/agent-platform-integration` and contains:

- platform dashboard;
- execution explorer with logical-plan visualization;
- active agents, step status, tokens, attempts and errors;
- pause/resume/retry/cancel controls;
- global human-approval inbox;
- Agent/Skill/Prompt CRUD;
- Tool CRUD including side-effect and approval policy;
- MCP Server CRUD;
- Knowledge Base and document management;
- upload, Google document ingestion and reindex;
- RAG retrieval playground;
- Agent-to-Knowledge assignment management;
- runtime/model/durability information;
- links to Grafana, Prometheus, Jaeger and NATS Monitor.

M6 also adds Control Plane read models:

```text
GET /v1/admin/overview
GET /v1/admin/executions
GET /v1/admin/approvals
GET /v1/admin/runtime
```

The Angular container is independent from the execution runtime. Nginx serves the SPA and proxies `/api/*` to `agent-platform:8080`. If the UI is unavailable, runtime command processing continues normally.


---

# M7 — Context & Memory

M7 is complete in this branch. The first half introduces Sessions, Working Context and Persistent Memory; M7.3/M7.4 add runtime context composition, budgeting, retrieval and inspection.

Implemented:

```text
M7.1 Sessions + Working Context       ✅
M7.2 Persistent Memory + Policies     ✅
M7.3 Context Engine + Budget Manager  ✅
M7.4 Context snapshots + UI           ✅
```

## Sessions

Create a session:

```bash
curl -X POST http://localhost:8080/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "architecture-refinement",
    "scope": "TENANT",
    "metadata": {"project": "demo"}
  }'
```

Use its id in an execution:

```json
{
  "sessionId": "<SESSION_ID>",
  "command": {
    "name": "architecture-review",
    "intent": "Review this architecture.",
    "input": {},
    "context": {},
    "instructions": []
  }
}
```

REST and NATS use the same optional `sessionId`.

Inspect continuity:

```text
GET /v1/sessions/{sessionId}/executions
GET /v1/sessions/{sessionId}/context
GET /v1/executions/{executionId}/context
```

Working Context is written transactionally with execution state. Command, instructions, plan, completed step output and final result become context entries with provenance and token estimates.

## Persistent Memory

Create explicit memory:

```bash
curl -X POST http://localhost:8080/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{
    "scopeType": "TENANT",
    "scopeId": "demo",
    "memoryType": "CONSTRAINT",
    "key": "primary-cloud",
    "content": "The primary cloud for this programme is AWS.",
    "importance": 0.9
  }'
```

Evaluate an inferred candidate:

```bash
curl -X POST http://localhost:8080/v1/memory-candidates/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "scopeType": "TENANT",
    "scopeId": "demo",
    "memoryType": "PREFERENCE",
    "key": "messaging",
    "content": "Prefer NATS for lightweight event messaging.",
    "confidence": 0.91,
    "importance": 0.7,
    "explicit": false
  }'
```

Every write is evaluated by deterministic Memory Policy.

Current defaults:

```env
MEMORY_ALLOW_INFERRED_PERSISTENCE=true
MEMORY_MIN_INFERRED_CONFIDENCE=0.80
MEMORY_MAX_CONTENT_CHARS=8000
MEMORY_CLEANUP_POLL_SECONDS=60
MEMORY_AUTO_EXTRACT_SESSION=true
MEMORY_EXTRACTOR_MODEL_PROFILE=router-fast
MEMORY_EXTRACTOR_MAX_CANDIDATES=8
MEMORY_EXTRACTOR_MAX_INPUT_CHARS=50000
```

Policy and audit:

```text
GET /v1/memory-policy
GET /v1/memory-policy/audit
```

The audit intentionally does not persist rejected candidate content. It stores content length + SHA-256 and metadata keys.

Memory lifecycle:

```text
ACTIVE
  +--> SUPERSEDED  same scope + key replaced
  +--> REVOKED     explicit revoke
  +--> EXPIRED     TTL/session lifecycle
```

Session-scoped memory is expired automatically when its Session closes or expires.

At the M7.2 boundary memory is persisted and queryable without being blindly appended to prompts. M7.3 then introduces scoped retrieval, selection and budgeting through ContextEngine.


## Automatic session-memory extraction

When an execution has a `sessionId` and finishes successfully, M7.2 can invoke a lightweight model profile to propose reusable session-memory candidates.

```text
Execution COMPLETED
  -> MemoryCandidateExtractor
  -> MemoryCandidate[]
  -> deterministic MemoryPolicyEngine
  -> persist/reject
```

The extractor is configured with:

```env
MEMORY_AUTO_EXTRACT_SESSION=true
MEMORY_EXTRACTOR_MODEL_PROFILE=router-fast
MEMORY_EXTRACTOR_MAX_CANDIDATES=8
```

Automatic candidates are always `scopeType=SESSION`. Cross-session scopes such as USER, TEAM, TENANT and AGENT require explicit memory creation at this milestone.

Extraction is best-effort and runs after the execution result is already durable. An extraction/model failure never changes a successful execution into FAILED.

Automatic extraction only proposes/persists memory. M7.3 independently decides whether a memory is relevant enough and fits the effective context budget.


> If inferred persistence is disabled, automatic extraction is skipped entirely, avoiding an unnecessary model call.


---

# M7.3 / M7.4 — Context Engine, Budgets and Context Inspector

M7 is now complete.

Model-backed AGENT, MODEL and VALIDATE steps route their model input through a platform-owned Context Engine:

```text
Command
+ current PlanStep
+ dependency results
+ previous Session Working Context
+ relevant Persistent Memory
+ managed Knowledge
+ system prompt
        |
        v
Context Engine
        |
        v
Budget Manager
        |
        +-- INCLUDE
        +-- COMPRESS_TRUNCATE
        +-- DROP_BUDGET
        |
        v
EffectiveContext
        |
        v
Model Gateway
```

The budget applies to the effective system prompt too. The Model Gateway receives the budgeted system and user prompts, so the snapshot and the actual provider input cannot diverge.

Default budget:

```env
CONTEXT_MODEL_WINDOW_TOKENS=200000
CONTEXT_RESERVED_OUTPUT_TOKENS=16000
CONTEXT_SAFETY_MARGIN_TOKENS=10000
CONTEXT_SESSION_MAX_ENTRIES=24
CONTEXT_MEMORY_TOP_K=8
CONTEXT_MEMORY_MIN_SCORE=0.12
CONTEXT_MIN_COMPRESSION_TOKENS=128
```

Persistent Memory now supports hybrid retrieval with pgvector + full-text search. Relevance (vector + lexical) is gated first; confidence, importance and freshness then affect ranking. A Session exposes its own SESSION memory and, when it has an `ownerKey`, the declared USER/TEAM/TENANT scope. AGENT steps additionally expose deterministic AGENT:<name> and AGENT:<id> scopes from the Agent Registry.

Memory retrieval playground:

```text
POST /v1/memories/retrieve
```

Example:

```json
{
  "query": "Which cloud constraints apply?",
  "scopes": [
    {"scopeType": "TENANT", "scopeId": "demo"}
  ],
  "topK": 8
}
```

Every AGENT/MODEL/VALIDATE step model call persists a logical Context Snapshot before the provider invocation:

```text
GET /v1/executions/{executionId}/context-snapshots
GET /v1/executions/{executionId}/context-snapshots?stepId=<stepId>
```

A snapshot contains the model budget, component types, token estimates, selected/compressed/dropped decisions and provenance. It intentionally does not duplicate the complete final prompt.

The Angular Control Plane now contains:

- Sessions management and Working Context inspection;
- Persistent Memory browser and explicit memory creation/revoke;
- Memory Policy and audit;
- hybrid Memory retrieval playground;
- Context Engine runtime settings;
- per-execution Context Snapshots showing composition, budget, compression and provenance;
- Session selector when starting an execution from the UI.

This completes the M7 boundary:

```text
Execution State != Working Context != Persistent Memory != Knowledge
```

M8 can now build Governance/Evals on top of persisted plan state, model usage, memory policy audit and context provenance.


## M7 end-to-end smoke test

After rebuilding the branch, a deterministic smoke test is available:

```bash
bash scripts/m7-smoke.sh
```

It creates a Session, persists TENANT + SESSION memory, exercises hybrid retrieval, launches a session-aware execution, waits for completion, verifies that at least one MEMORY component was selected by ContextEngine, and prints Working Context, snapshots and policy state.

The script intentionally uses explicit memories for its hard assertions so the test does not depend on whether the LLM extractor chooses a specific inferred candidate. Automatically inferred SESSION memories are printed separately for inspection.


---

# M8.1 / M8.2 — Governance and Budget / Cost Control

M8.1 introduces a deterministic platform Policy Engine. Planner and Agents can request resources, but the runtime remains authoritative.

```text
Planner / Agent
      |
      v
Governance Policy Engine
      |
      +--> ALLOW
      +--> DENY
      +--> REQUIRE_APPROVAL
```

Governed resources:

```text
AGENT
TOOL
KNOWLEDGE
MODEL
MEMORY_SCOPE
```

Policy APIs:

```text
GET    /v1/governance/policies
POST   /v1/governance/policies
PUT    /v1/governance/policies/{id}
DELETE /v1/governance/policies/{id}
POST   /v1/governance/policies/evaluate
GET    /v1/governance/decisions
```

Policies are checked after planning and again immediately before step execution. Model access is additionally checked at `GovernedModelGateway`, and Memory scopes are authorized before ContextEngine retrieves them.

Example policy requiring approval for externally visible tools:

```json
{
  "name": "external-actions-require-approval",
  "policyType": "SIDE_EFFECT",
  "effect": "REQUIRE_APPROVAL",
  "resourceType": "TOOL",
  "resourcePattern": "*",
  "subjectType": "GLOBAL",
  "subjectPattern": "*",
  "conditions": {
    "sideEffect": "EXTERNAL_ACTION"
  },
  "priority": 100,
  "enabled": true
}
```

Policy resolution is priority-first. At equal priority:

```text
DENY > REQUIRE_APPROVAL > ALLOW
```

M8.2 adds model token/cost budgets:

```text
GLOBAL | EXECUTION | TENANT | TEAM | USER | AGENT

EXECUTION | DAILY | MONTHLY
```

Budget APIs:

```text
GET    /v1/governance/budgets
POST   /v1/governance/budgets
PUT    /v1/governance/budgets/{id}
DELETE /v1/governance/budgets/{id}
POST   /v1/governance/budgets/evaluate
GET    /v1/governance/budget-decisions
GET    /v1/governance/executions/{executionId}/usage
```

Example hard token budget:

```json
{
  "name": "global-dev-token-limit",
  "scopeType": "GLOBAL",
  "scopeId": "*",
  "period": "EXECUTION",
  "maxTotalTokens": 50000,
  "action": "DENY",
  "enabled": true
}
```

Cost budgets require explicit pricing configuration. No provider price is guessed.

```env
GOVERNANCE_DEFAULT_PROJECTED_COMPLETION_TOKENS=4096
GOVERNANCE_PROMPT_ESTIMATE_MULTIPLIER=1.25

GOVERNANCE_ROUTER_INPUT_USD_PER_MILLION=0
GOVERNANCE_ROUTER_OUTPUT_USD_PER_MILLION=0
GOVERNANCE_EXECUTION_INPUT_USD_PER_MILLION=0
GOVERNANCE_EXECUTION_OUTPUT_USD_PER_MILLION=0
GOVERNANCE_PLANNER_INPUT_USD_PER_MILLION=0
GOVERNANCE_PLANNER_OUTPUT_USD_PER_MILLION=0
```

`DEGRADE` is intentionally restricted to cost-only budgets. It changes to `degradeModelProfile` only when the cheaper profile satisfies the budget, and the target model is then re-authorized by MODEL_ACCESS.

Provider usage is persisted after each model call in `governance_usage`; policy and budget decisions are persisted separately for audit.

Full Governance Control Plane screens are intentionally deferred to M8.4. M8.1/M8.2 deliver the runtime enforcement, APIs, audit state and admin runtime diagnostics first.


## M8.1 / M8.2 end-to-end smoke test

After rebuilding the branch:

```bash
bash scripts/m8-governance-smoke.sh
```

The script verifies:

1. a normal baseline execution;
2. policy priority override (broad DENY + higher-priority specific ALLOW);
3. deterministic MODEL_ACCESS denial at runtime;
4. a token budget that blocks the Planner before provider invocation;
5. persisted policy/budget decision audit;
6. actual model usage metering.

The script uses a temporary TENANT Session with `ownerKey=m8-smoke` and cleans up the test policies/budget/session.
