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
