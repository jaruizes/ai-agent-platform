# Process Platform

Spring Boot service for deterministic process orchestration.

M9.1 implements only the canonical asynchronous boundary with Agent Platform.
Process definitions, instances, deterministic scheduling and process context are
intentionally deferred to M9.2+.

## Architecture

The service follows the same package organization used by the backend of
`proposal-app/feat/agent-platform-integration`:

```text
com.jaruizes.processplatform
├── business
├── domain
│   ├── model
│   └── ports
└── infrastructure
    ├── api.rest
    ├── events
    └── messaging.nats
```

The dependency direction is:

```text
infrastructure
     ↓
  business
     ↓
   domain
```

The domain does not know NATS.

## M9.1 integration boundary

```text
Process Platform
      |
      | ExecutionCommand
      v
     NATS
      |
      v
Agent Platform
      |
      | ExecutionEvent
      v
     NATS
      |
      v
Process Platform
      |
      v
AgentExecutionEventReceived
(Spring application event)
```

Process Platform knows only the public Agent Platform contracts:

- `execution.command`
- `execution.lifecycle`
- `execution.orchestration`
- `execution.result`

It does not call or reference:

- Planner
- LogicalPlan
- LangGraph
- Agent internals
- MCP
- Knowledge implementation
- Model providers

### Command subject

Default:

```text
platform.commands.execution
```

### Event subject

Default:

```text
platform.events.execution.>
```

The event consumer is durable:

```text
process-platform-agent-events
```

The first creation uses `DeliverNew`, so a new Process Platform deployment does
not replay historical Agent Platform events. Once created, the durable consumer
keeps its position across restarts.

## Canonical ExecutionCommand

Example:

```json
{
  "specVersion": "1.0",
  "messageId": "46c...",
  "messageType": "execution.command",
  "timestamp": "2026-09-23T13:00:00Z",
  "correlationId": "a10...",
  "causationId": null,
  "source": {
    "type": "process-platform",
    "name": "process-platform",
    "instance": null
  },
  "tenantId": null,
  "data": {
    "execution": {
      "executionId": "aa8...",
      "sessionId": null,
      "command": {
        "name": "security-analysis",
        "intent": "Analyse the security risks",
        "input": {},
        "context": {},
        "instructions": [],
        "metadata": {}
      }
    }
  }
}
```

Large/binary data must not be embedded in NATS commands. Store it externally and
send references/descriptors through the standard command.

## Event handling

The NATS adapter deserializes the common Agent Platform envelope and delegates to
`AgentPlatformIntegrationService.handle(...)`.

The business layer then publishes through `ExecutionEventPublisherPort`.
The current infrastructure implementation turns it into:

```text
AgentExecutionEventReceived
```

a Spring application event.

This is the extension point for M9.2:

```text
AgentExecutionEventReceived
      ↓
future Process Runtime
      ↓
correlate executionId
      ↓
complete/fail ProcessStep
```

The future Process Runtime therefore will not depend on NATS.

## Diagnostic API

M9.1 contains a small API only to test the integration boundary.

Submit:

```http
POST /v1/agent-executions
```

Example body:

```json
{
  "name": "architecture-analysis",
  "intent": "Analyse this architecture",
  "input": {
    "documentId": "123"
  },
  "context": {},
  "instructions": [
    "Return concise findings"
  ],
  "metadata": {}
}
```

The endpoint returns HTTP 202 after JetStream accepts the command. It does not
wait for Agent Platform.

Inspect events received by Process Platform:

```http
GET /v1/agent-executions/{executionId}/events
```

The event journal is intentionally bounded and in-memory. It is only diagnostic
state and must not be used for process semantics. Durable ProcessInstance state
belongs to M9.2.

## Run

From repository root:

```bash
docker compose build process-platform agent-platform
docker compose up -d
```

Process Platform:

```text
http://localhost:8090
```

Health:

```text
http://localhost:8090/actuator/health
```

## M9.1 smoke test

```bash
bash scripts/m9-process-platform-smoke.sh
```

The script verifies the full round trip:

```text
HTTP -> Process Platform
          |
          | ExecutionCommand
          v
        NATS
          |
          v
     Agent Platform
          |
          | lifecycle/orchestration/result
          v
        NATS
          |
          v
 Process Platform event consumer
          |
          v
 diagnostic event journal
```

A successful run must observe lifecycle, orchestration and result events through
the Process Platform itself.


---

# M9.2 — Process Domain & Durable State

M9.2 introduces the deterministic process domain without yet executing workflows.

## Domain model

```text
ProcessDefinition
  ├── definitionKey
  ├── version
  ├── status: DRAFT | ACTIVE | RETIRED
  ├── inputSchema
  ├── outputSchema
  └── ProcessStepDefinition[]

ProcessStepDefinition
  ├── stepKey
  ├── type
  ├── dependsOn[]
  ├── inputSchema
  ├── outputSchema
  └── configuration

ProcessInstance
  ├── exact definitionId + version
  ├── status
  ├── correlationId
  ├── input
  ├── ProcessContext
  └── ProcessStepInstance[]
```

Step types prepared for later milestones:

```text
SERVICE
TOOL
AGENTIC_EXECUTION
DECISION
HUMAN
WAIT_EVENT
SUBPROCESS
```

M9.2 does not execute these step types yet. M9.3 will provide deterministic scheduling and execution semantics.

## Versioning rules

A definition is editable only while it is `DRAFT`.

```text
DRAFT
  ↓ activate
ACTIVE
  ↓ retire
RETIRED
```

Once a definition is ACTIVE it is immutable. To change a process:

```text
v1 ACTIVE
   ↓ next-version
v2 DRAFT
   ↓ edit
v2 ACTIVE
```

Existing instances remain pinned to their original version.

Multiple published versions may remain ACTIVE. When an instance omits `version`,
the highest ACTIVE version is selected.

## DAG validation

Before a definition is stored/activated the business layer validates:

- unique `stepKey`;
- every dependency exists;
- no step depends on itself;
- no dependency cycles.

Parallelism is represented by dependencies rather than a special "parallel step".

Example:

```text
validate
   │
   ├──────────┐
   ▼          ▼
security     cost
   └────┬─────┘
        ▼
     compose
```

## Step I/O contracts

Each step carries explicit JSON-schema-like contracts:

```text
inputSchema
outputSchema
```

M9.2 stores and versions these contracts. Runtime enforcement of step input/output
belongs to M9.3, where actual step execution exists.

## Process Context

`ProcessContext` is durable state owned by the process instance.

It is not:

- Agent Platform Working Context;
- Persistent Memory;
- Knowledge;
- command metadata.

Example:

```json
{
  "proposal": {"id": "P-123"},
  "validation": {"valid": true},
  "securityAnalysis": {},
  "costAnalysis": {}
}
```

Each future process step will read/write explicit parts of this state.

## Persistence

Process Platform has its own PostgreSQL service and database.

Tables:

```text
process_definitions
process_step_definitions
process_instances
process_step_instances
```

It does not use Agent Platform PostgreSQL.

Local defaults:

```text
database: process_platform
user:     process
port:     5433
```

## API

Definitions:

```http
GET  /v1/process-definitions
GET  /v1/process-definitions/{id}
POST /v1/process-definitions
PUT  /v1/process-definitions/{id}
POST /v1/process-definitions/{id}/activate
POST /v1/process-definitions/{id}/retire
POST /v1/process-definitions/{id}/next-version
```

Instances:

```http
GET  /v1/process-instances
GET  /v1/process-instances/{id}
POST /v1/process-instances
PUT  /v1/process-instances/{id}/context
```

Creating an instance only materializes durable state. It does not start execution yet.

## Example definition

```json
{
  "definitionKey": "proposal-analysis",
  "name": "Proposal analysis",
  "version": 1,
  "inputSchema": {"type": "object"},
  "outputSchema": {"type": "object"},
  "steps": [
    {
      "stepKey": "validate",
      "name": "Validate input",
      "type": "SERVICE",
      "dependsOn": [],
      "inputSchema": {"type": "object"},
      "outputSchema": {"type": "object"},
      "configuration": {"handler": "validate-input"}
    },
    {
      "stepKey": "analyse",
      "name": "Analyse proposal",
      "type": "AGENTIC_EXECUTION",
      "dependsOn": ["validate"],
      "inputSchema": {"type": "object"},
      "outputSchema": {"type": "object"},
      "configuration": {
        "intent": "Analyse the validated proposal"
      }
    }
  ]
}
```

## Test M9.2

M9.2 can be tested without Agent Platform or any LLM provider:

```bash
docker compose up -d process-postgres nats otel-collector process-platform
bash scripts/m9-process-domain-smoke.sh
```

The smoke test verifies:

1. creation of a v1 draft;
2. DAG persistence;
3. activation;
4. immutability of ACTIVE versions;
5. creation of a v1 instance;
6. materialization of PENDING step instances;
7. durable ProcessContext updates;
8. cloning v2 as DRAFT;
9. latest-active resolution still selecting v1 while v2 is DRAFT;
10. latest-active resolution selecting v2 after activation;
11. the original instance remaining pinned to v1.


---

# M9.3 — Deterministic Process Runtime

M9.3 turns the durable M9.2 process model into an executable deterministic DAG.

## Runtime lifecycle

```text
ProcessInstance CREATED
        |
        | POST /v1/process-instances/{id}/start
        v
      RUNNING
        |
        +--> PENDING step
        |       |
        |       v
        |     READY
        |       |
        |       v
        |     RUNNING
        |       |
        |       +--> SERVICE -------------> COMPLETED
        |       |
        |       +--> AGENTIC_EXECUTION
        |               |
        |               v
        |             WAITING
        |               |
        |         ExecutionEvent
        |               |
        |               v
        |           COMPLETED
        |
        +--> WAITING  (no runnable local steps, delegated execution pending)
        |
        +--> COMPLETED
        |
        +--> FAILED
```

The runtime calculates readiness exclusively from persisted `dependsOn` state.
Independent READY steps are submitted concurrently using Java 21 virtual threads.

## Supported executable step types in M9.3

```text
SERVICE
AGENTIC_EXECUTION
```

The following remain modeled but intentionally fail with
`UNSUPPORTED_STEP_TYPE` if executed before their later milestone:

```text
TOOL
DECISION
HUMAN
WAIT_EVENT
SUBPROCESS
```

### SERVICE

A deterministic service step resolves:

```text
configuration.handler
        |
        v
ProcessServiceHandlerPort
```

Handlers are Spring adapters/plugins and must be idempotent because durable
recovery provides at-least-once execution semantics.

M9.3 includes only the generic `echo` handler used by smoke/integration tests.
Business-specific deterministic handlers must implement the same port.

### AGENTIC_EXECUTION

A step never identifies an Agent Platform agent.

```text
ProcessStep
  type = AGENTIC_EXECUTION
  configuration.intent = ...
          |
          v
canonical ExecutionCommand
          |
          v
transactional outbox
          |
          v
NATS
          |
          v
Agent Platform
```

The Process Platform stores the generated `delegatedExecutionId` on the
ProcessStepInstance and waits for the standard Agent Platform terminal event.

On `execution.result / COMPLETED` the result becomes the process step output.

On terminal failure/cancellation the process step and process instance become
FAILED.

## Transactional command outbox

Agent delegation does not publish directly from the runtime.

The following state is committed atomically:

```text
ProcessStepInstance.status = WAITING
ProcessStepInstance.delegatedExecutionId = ...
ExecutionCommand outbox row = pending
```

A scheduled `ExecutionCommandOutboxPublisher` publishes the canonical command
through `AgentPlatformCommandPort`.

This removes the crash window:

```text
publish command
<CRASH>
persist executionId
```

JetStream plus the command `messageId` and Agent Platform request idempotency
make outbox delivery safely at-least-once.

Table:

```text
process_execution_command_outbox
```

## Durable recovery

PostgreSQL is authoritative. Virtual threads are not workflow state.

Every recovery pass:

1. scans RUNNING/WAITING process instances;
2. resubmits persisted READY steps;
3. resets stale RUNNING `SERVICE` or pre-delegation
   `AGENTIC_EXECUTION` steps to READY;
4. recalculates dependency readiness;
5. leaves delegated WAITING agent steps untouched;
6. advances joins after dependencies complete.

Configuration:

```text
PROCESS_RUNTIME_RECOVERY_DELAY_MS=2000
PROCESS_RUNTIME_OUTBOX_POLL_MS=250
PROCESS_RUNTIME_STEP_STALE_SECONDS=60
```

A SERVICE handler that may run longer than the stale timeout must increase the
timeout or later use a dedicated lease/heartbeat policy.

## Step input

M9.3 builds one stable process-neutral input envelope:

```json
{
  "processInput": {},
  "context": {},
  "dependencies": {
    "previous-step": {}
  }
}
```

This is what `inputSchema` validates and what SERVICE/AGENTIC_EXECUTION receives.

Process-specific mapping expressions are intentionally not introduced yet.

## Step output and ProcessContext

Every completed step stores its output durably and merges it under its step key:

```text
ProcessContext[stepKey] = stepOutput
```

For parallel completions the ProcessInstance row is pessimistically locked before
the merge. Therefore two parallel branches cannot overwrite each other's context.

A fan-out/fan-in example:

```text
validate
   |
   +--------+
   v        v
security   cost
   |        |
   +----+---+
        v
      compose
```

`compose.dependencies` receives both persisted outputs.

## Contract validation

M9.3 enforces:

- ProcessDefinition `inputSchema` before start;
- every step `inputSchema` before execution;
- every step `outputSchema` before completion;
- ProcessDefinition `outputSchema` before process completion.

The current validator supports the JSON Schema subset needed by the platform
contracts:

```text
type
required
properties
items
```

Contract violation fails the corresponding step/process deterministically.

## API

Start an existing ProcessInstance:

```http
POST /v1/process-instances/{id}/start
```

The call returns `202 Accepted`. Runtime progression is asynchronous.

Read current state with the existing M9.2 query:

```http
GET /v1/process-instances/{id}
```

## M9.3 smoke tests

Deterministic runtime only; no LLM required:

```bash
docker compose up -d process-postgres nats otel-collector process-platform
bash scripts/m9-process-runtime-smoke.sh
```

This verifies a four-step fan-out/fan-in DAG and ProcessContext merging.

Full hybrid runtime:

```bash
docker compose up -d
bash scripts/m9-process-runtime-agentic-smoke.sh
```

This verifies:

```text
SERVICE
   |
AGENTIC_EXECUTION
   |
transactional outbox
   |
ExecutionCommand / NATS
   |
Agent Platform
   |
ExecutionEvent / NATS
   |
Process Runtime resumes
   |
SERVICE
   |
COMPLETED
```
