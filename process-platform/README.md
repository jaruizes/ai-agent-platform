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
AGENT
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
