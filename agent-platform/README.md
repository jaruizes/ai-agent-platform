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
