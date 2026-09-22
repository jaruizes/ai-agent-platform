# AI Agent Platform

Intent-driven AI execution platform with declarative Agents, Skills, Tools/MCP, managed Knowledge/RAG, LangGraph orchestration, durable execution and an Angular Control Plane.

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
M7  Context & Memory                   next
M8  Governance & Evals
M9  Semantic Layer
```
