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
AGENTIC_EXECUTION
DECISION
HUMAN
WAIT_EVENT
SUBPROCESS
```

`TOOL` is intentionally not a Process Platform step type. Tool/MCP vocabulary
belongs exclusively to Agent Platform.

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
      "configuration": {"serviceKey": "proposal.validate"}
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
DECISION
HUMAN
WAIT_EVENT
SUBPROCESS
```

### SERVICE

A SERVICE step represents an explicit deterministic capability selected by the
process definition.

```text
ProcessDefinition
      |
      | type = SERVICE
      | configuration.serviceKey
      | (serviceVersion pinned on activation)
      v
Process Service Registry
      |
      v
ProcessServiceHandlerPort
      |
      +--> local deterministic logic
      |
      +--> HTTP / gRPC / database / external service adapter
```

The important boundary is ownership: Process Platform explicitly knows that this
service/capability must be called. A SERVICE handler may internally call an external
system, but it is still deterministic process orchestration.

The Service Registry resolves the public capability to an internal
ProcessServiceHandlerPort adapter. Handlers must be idempotent because durable
recovery provides at-least-once execution semantics.

The repository includes the generic `echo` implementation for smoke/integration
tests; process definitions never reference that implementation key directly.

`TOOL` is not part of this model. If an AGENTIC_EXECUTION needs a Tool, Agent
Platform decides and invokes it through its own Tool/MCP subsystem.

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


## Terminology boundary: SERVICE vs Agent Platform Tool

Process Platform deliberately exposes only two execution mechanisms for ordinary
automated work:

```text
SERVICE
  -> deterministic invocation chosen by the process designer

AGENTIC_EXECUTION
  -> open-ended objective delegated to Agent Platform
```

A Process Platform SERVICE may call the same external backend that an Agent
Platform Tool eventually calls, but the paths are intentionally different:

```text
Process Platform
  SERVICE
     |
     v
external service


Process Platform
  AGENTIC_EXECUTION
     |
     v
Agent Platform
     |
     v
Agent
     |
     v
MCP / Tool
     |
     v
external service
```

Process Platform never selects, lists or invokes Agent Platform Tools directly.


---

# M9.4 — Process Capabilities & Long-running Workflow

M9.4 completes the backend primitives required before building the visual Process
Control Plane.

## Process execution primitives

Process Platform now exposes:

```text
SERVICE
AGENTIC_EXECUTION
DECISION
HUMAN
WAIT_EVENT
SUBPROCESS   (modeled, activation rejected until a later milestone)
```

`TOOL` is intentionally not part of Process Platform.

## Service Registry

A SERVICE is selected from the Process Platform catalog, not by writing a Spring
handler name in a ProcessDefinition.

Catalog resource:

```text
ProcessServiceDefinition
  - serviceKey
  - version
  - status: DRAFT | ACTIVE | RETIRED
  - name / description
  - inputSchema / outputSchema
  - implementationKey   (internal adapter binding)
```

Lifecycle:

```text
DRAFT -> ACTIVE -> RETIRED
          |
          +-> next-version -> DRAFT
```

APIs:

```http
GET  /v1/process-services
GET  /v1/process-services?activeOnly=true
GET  /v1/process-services/{id}
POST /v1/process-services
PUT  /v1/process-services/{id}
POST /v1/process-services/{id}/activate
POST /v1/process-services/{id}/retire
POST /v1/process-services/{id}/next-version
```

A process designer references only:

```json
{
  "type": "SERVICE",
  "configuration": {
    "serviceKey": "customer.lookup"
  }
}
```

When the ProcessDefinition is activated, the latest ACTIVE version is resolved
and pinned:

```json
{
  "serviceKey": "customer.lookup",
  "serviceVersion": 3
}
```

If version 3 is later RETIRED, already-active ProcessDefinitions remain
executable with that pinned version. New activation cannot select a retired
version.

The internal `implementationKey` maps to `ProcessServiceHandlerPort`. It is
not part of the ProcessDefinition language.

## DECISION

DECISION is deterministic. It does not invoke an LLM.

Example:

```json
{
  "type": "DECISION",
  "configuration": {
    "path": "processInput.riskScore",
    "operator": "GTE",
    "value": 80,
    "onTrue": "HIGH",
    "onFalse": "LOW"
  }
}
```

Supported operators:

```text
EQ NE GT GTE LT LTE EXISTS IN
```

The persisted output is:

```json
{
  "outcome": "HIGH",
  "matched": true,
  "actual": 92
}
```

A branch step declares a condition:

```json
{
  "dependsOn": ["risk-route"],
  "configuration": {
    "when": {
      "decisionStep": "risk-route",
      "equals": "HIGH"
    }
  }
}
```

Non-selected branches become `SKIPPED`.

Skip propagation is dependency-aware:

```text
decision
   |
   +-- chosen branch ------ COMPLETED ----+
   |                                     |
   +-- other branch ------- SKIPPED ------+--> join
```

A step whose dependencies are all SKIPPED is itself skipped. A join with at least
one completed dependency and the remaining dependencies skipped can execute.

## HUMAN

A HUMAN step creates durable `HumanTask` state and moves the step to WAITING.

Definition:

```json
{
  "type": "HUMAN",
  "configuration": {
    "title": "Approve proposal",
    "description": "Review risk and cost"
  }
}
```

Inbox:

```http
GET /v1/human-tasks
GET /v1/human-tasks?pendingOnly=true
```

Complete:

```http
POST /v1/human-tasks/{taskId}/complete
Content-Type: application/json

{
  "decision": "APPROVED",
  "result": {
    "comment": "Reviewed"
  }
}
```

The step output becomes:

```json
{
  "decision": "APPROVED",
  "result": {
    "comment": "Reviewed"
  }
}
```

Human task completion uses a pessimistic lock and is idempotent with respect to
process progression.

## WAIT_EVENT

WAIT_EVENT persists a durable subscription without blocking a thread.

Definition:

```json
{
  "type": "WAIT_EVENT",
  "configuration": {
    "eventType": "contract.signed"
  }
}
```

By default the ProcessInstance `correlationId` is used.

Signal:

```http
POST /v1/process-events

{
  "eventType": "contract.signed",
  "correlationId": "CASE-123",
  "payload": {
    "documentId": "D-9"
  }
}
```

The API returns:

```json
{
  "matchedWaits": 1
}
```

Event consumption is durable and pessimistically locked. Duplicate delivery
cannot advance the same waiting step twice.

## Pause / resume / cancel

```http
POST /v1/process-instances/{id}/pause
POST /v1/process-instances/{id}/resume
POST /v1/process-instances/{id}/cancel
```

`PAUSED` freezes DAG progression.

External work already in flight is not forcibly interrupted. For example, an
Agent Platform execution or a deterministic SERVICE already running may still
finish; its durable result is stored while the ProcessInstance remains PAUSED.
Resume continues from persisted state.

Cancel marks all non-terminal process steps CANCELLED and cancels pending Human
Tasks/Event Waits.

M9.4 does not yet send a cancellation command to an already delegated Agent
Platform execution. Agent cancellation remains a separate public-contract
extension; Process Platform never calls Agent Platform internals.

## Retry and timeout

Automated executable steps can declare:

```json
{
  "retry": {
    "maxAttempts": 3,
    "backoffMs": 2000
  },
  "timeoutSeconds": 60
}
```

Retry is supported for:

```text
SERVICE
AGENTIC_EXECUTION
DECISION
```

Retry state is persisted on ProcessStepInstance:

```text
attemptCount
availableAt
deadlineAt
```

Backoff therefore survives process/runtime restarts.

A retry clears the old delegatedExecutionId before a new AGENTIC_EXECUTION is
created so late events from an older attempt cannot complete the new attempt.

HUMAN and WAIT_EVENT use timeout as a terminal waiting deadline rather than
automatic retry.

For AGENTIC_EXECUTION, retry after a timeout has at-least-once semantics: the old
remote execution may still consume resources because M9.4 does not yet expose
cross-platform cancellation.

## Activation-time semantic validation

Before a ProcessDefinition becomes ACTIVE, M9.4 validates:

- SERVICE references resolve to an ACTIVE service and get version-pinned;
- AGENTIC_EXECUTION has `intent`;
- HUMAN has `title`;
- WAIT_EVENT has `eventType`;
- DECISION path/operator are valid;
- conditional branch references point to a DECISION dependency;
- retry values are valid;
- timeout is positive;
- SUBPROCESS is rejected because it is not executable yet.

## M9.4 smoke

```bash
docker compose up -d process-postgres nats otel-collector process-platform
bash scripts/m9-process-long-running-smoke.sh
```

The smoke test verifies:

```text
Service Registry discovery
        |
SERVICE version pinning
        |
SERVICE
        |
DECISION
     /       \
 HUMAN      SERVICE
 WAITING    SKIPPED
     \       /
        join
         |
     pause
         |
human result persisted while PAUSED
         |
       resume
         |
     WAIT_EVENT
         |
correlated event
         |
      SERVICE
         |
     COMPLETED

+ process cancellation
+ pending human-task cancellation
+ durable WAIT_EVENT timeout
```


## M9.4 generic HTTP SERVICE adapter

The Service Registry includes a built-in `http` implementation so deterministic
external-service calls do not require a new Java handler for every endpoint.

Example catalog entry:

```json
{
  "serviceKey": "customer.lookup",
  "name": "Lookup customer",
  "version": 1,
  "implementationKey": "http",
  "configuration": {
    "url": "http://customer-service:8080/v1/customers/lookup",
    "method": "POST",
    "headers": {
      "X-Client": "process-platform"
    }
  },
  "inputSchema": {"type": "object"},
  "outputSchema": {"type": "object"}
}
```

Supported methods:

```text
GET POST PUT PATCH DELETE
```

For POST/PUT/PATCH the request body is the standard step input envelope:

```json
{
  "processInput": {},
  "context": {},
  "dependencies": {}
}
```

GET and DELETE are invoked without a request body.

HTTP 4xx/5xx responses are treated as SERVICE execution failures and therefore
participate in the normal retry/timeout policy.

Do not store credentials or long-lived secrets as literal catalog headers.
Secret references/credential providers are a later hardening concern.

Fine-grained input/output mapping expressions are intentionally not introduced
in M9.4; the future designer can add them without changing SERVICE ownership or
the Service Registry model.
