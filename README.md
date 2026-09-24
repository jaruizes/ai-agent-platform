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
