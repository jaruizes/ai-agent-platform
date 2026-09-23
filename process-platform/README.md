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
