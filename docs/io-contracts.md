# Contratos de Entrada y Salida

## 1. Objetivo

Este documento define los contratos canónicos de integración de AI Agent Platform.

El objetivo es que la plataforma tenga una interfaz **genérica, estable, versionable e independiente de los casos de uso**.

Una nueva capacidad como `analyse-proposal`, `generate-architecture` o `review-code` no crea un nuevo tipo de mensaje. Todas utilizan los mismos contratos estándar.

---

## 2. Modelo conceptual

Se definen tres familias principales:

1. **ExecutionCommand**: solicita una ejecución.
2. **ExecutionLifecycleEvent**: comunica cambios de estado o progreso.
3. **ExecutionResultEvent**: comunica el resultado funcional.
4. **ArtifactProducedEvent**: comunica la producción de un artifact cuando resulte útil notificarlo de forma independiente.

Todos utilizan un envelope común.

```text
PlatformMessage
|
+-- metadata
|   +-- specVersion
|   +-- messageId
|   +-- messageType
|   +-- timestamp
|   +-- correlationId
|   +-- causationId
|   +-- source
|
+-- data
    +-- execution
```

---

## 3. Envelope común

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `specVersion` | string | Sí | Versión del contrato del mensaje. Ej. `1.0`. |
| `messageId` | string/UUID | Sí | Identificador globalmente único del mensaje. |
| `messageType` | string | Sí | Tipo estándar de mensaje. |
| `timestamp` | RFC3339 datetime | Sí | Momento de creación del mensaje en UTC. |
| `correlationId` | string | Sí | Identificador que correlaciona todos los mensajes de un flujo lógico. |
| `causationId` | string/null | No | `messageId` del mensaje que causó este mensaje. |
| `source` | object | Sí | Sistema que origina el mensaje. |
| `tenantId` | string/null | No | Tenant cuando la plataforma opere en modo multi-tenant. |
| `data` | object | Sí | Payload específico de la familia de mensaje. |

### 3.1 Source

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `type` | string | Sí | Tipo de origen: `application`, `platform`, `service`, etc. |
| `name` | string | Sí | Nombre estable del productor. |
| `instance` | string/null | No | Instancia concreta para troubleshooting. |

---

## 4. ExecutionCommand

### 4.1 Estructura

```json
{
  "specVersion": "1.0",
  "messageId": "msg-123",
  "messageType": "execution.command",
  "timestamp": "2026-09-22T09:45:00Z",
  "correlationId": "corr-456",
  "causationId": null,
  "source": {
    "type": "application",
    "name": "proposal-service"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal",
        "intent": "Analiza los documentos recibidos.",
        "input": {},
        "context": {},
        "instructions": []
      }
    }
  }
}
```

### 4.2 Campos de execution

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `executionId` | string/UUID | No* | ID de ejecución. Puede ser suministrado por el cliente o generado por la plataforma según el canal. |
| `command` | object | Sí | Descripción de la capacidad solicitada. |
| `requestedAt` | RFC3339 datetime | No | Fecha de solicitud si difiere del timestamp del envelope. |
| `expiresAt` | RFC3339 datetime/null | No | Fecha tras la que la ejecución no debe iniciarse. |
| `priority` | string/null | No | Prioridad lógica; valores concretos se definirán por política. |

`*` Para REST puede generarlo la plataforma al aceptar la petición. Para NATS es recomendable que el productor pueda enviarlo para facilitar idempotencia y correlación.

### 4.3 Campos de command

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `name` | string | Sí | Identificador machine-readable de la capacidad. No identifica un agente. |
| `intent` | string | Sí | Objetivo que el consumidor quiere conseguir. |
| `input` | object | No | Datos estructurados sobre los que debe trabajar la capacidad. |
| `context` | object | No | Información contextual conocida por el consumidor. |
| `instructions` | array[string] | No | Aclaraciones, restricciones o preferencias de esta ejecución. |
| `metadata` | object | No | Metadata extensible no funcional. |

### 4.4 Semántica de los campos

#### name

Identifica una capacidad registrada:

```json
"name": "analyse-proposal"
```

No debe contener nombres de agentes:

```json
"name": "proposal-analysis-agent"
```

#### intent

Expresa el resultado esperado en lenguaje natural:

```json
"intent": "Analiza los documentos recibidos e identifica riesgos, inconsistencias y puntos relevantes."
```

#### input

Contiene datos de trabajo, preferentemente estructurados:

```json
"input": {
  "proposalId": "P-1234",
  "documents": [
    {
      "artifactId": "art-001"
    }
  ]
}
```

#### context

Añade información de contexto que no constituye la orden principal:

```json
"context": {
  "author": {
    "profile": "commercial"
  },
  "businessArea": "banking"
}
```

#### instructions

Aclaraciones específicas de esta ejecución:

```json
"instructions": [
  "La estimación del apartado 5 no es fiable.",
  "Da especial importancia a los riesgos de seguridad."
]
```

No se denomina `prompt` porque el prompt efectivo es responsabilidad interna de la plataforma.

---

## 5. REST: creación de una ejecución

### Request

```http
POST /v1/executions
Content-Type: application/json
```

El body puede omitir los campos del envelope que la plataforma puede generar de forma segura.

Ejemplo:

```json
{
  "correlationId": "proposal-P-1234",
  "command": {
    "name": "analyse-proposal",
    "intent": "Analiza los documentos recibidos e identifica riesgos e inconsistencias.",
    "input": {
      "proposalId": "P-1234",
      "documents": [
        {
          "artifactId": "art-doc-01"
        },
        {
          "artifactId": "art-doc-02"
        }
      ]
    },
    "context": {
      "authorProfile": "commercial"
    },
    "instructions": [
      "La sección que describe la arquitectura actual contiene información incorrecta.",
      "Prioriza los riesgos técnicos."
    ]
  }
}
```

### Response

```http
HTTP/1.1 202 Accepted
Location: /v1/executions/exec-789
```

```json
{
  "executionId": "exec-789",
  "correlationId": "proposal-P-1234",
  "status": "ACCEPTED"
}
```

El resultado final **no se devuelve** en esta respuesta.

---

## 6. NATS: creación de una ejecución

Subject inicial propuesto:

```text
platform.commands.execution
```

Payload:

```json
{
  "specVersion": "1.0",
  "messageId": "msg-cmd-001",
  "messageType": "execution.command",
  "timestamp": "2026-09-22T09:45:00Z",
  "correlationId": "proposal-P-1234",
  "causationId": null,
  "source": {
    "type": "application",
    "name": "proposal-service"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal",
        "intent": "Analiza los documentos recibidos e identifica riesgos e inconsistencias.",
        "input": {
          "proposalId": "P-1234",
          "documents": [
            {
              "artifactId": "art-doc-01"
            }
          ]
        },
        "context": {
          "authorProfile": "commercial"
        },
        "instructions": [
          "La sección de arquitectura actual contiene información incorrecta."
        ]
      }
    }
  }
}
```

---

## 7. ExecutionLifecycleEvent

Comunica cambios de estado y progreso.

### 7.1 Estados iniciales

- `ACCEPTED`
- `PLANNING`
- `RUNNING`
- `WAITING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

### 7.2 Estructura

```json
{
  "specVersion": "1.0",
  "messageId": "evt-002",
  "messageType": "execution.lifecycle",
  "timestamp": "2026-09-22T09:45:02Z",
  "correlationId": "proposal-P-1234",
  "causationId": "msg-cmd-001",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "RUNNING",
      "event": {
        "type": "EXECUTION_STARTED",
        "sequence": 2,
        "detail": {}
      }
    }
  }
}
```

### 7.3 Campos

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `executionId` | string/UUID | Sí | Ejecución afectada. |
| `command.name` | string | Sí | Capacidad solicitada originalmente. |
| `status` | enum | Sí | Estado actual de la ejecución. |
| `event.type` | string | Sí | Hecho ocurrido. |
| `event.sequence` | integer | Sí | Secuencia monotónica dentro de la ejecución. |
| `event.detail` | object | No | Detalle extensible del evento. |
| `progress` | object | No | Información opcional de progreso. |
| `error` | object | No | Error normalizado cuando aplique. |

### 7.4 Progress

El progreso no debe prometer un porcentaje cuando la plataforma no pueda conocerlo.

Ejemplo basado en pasos:

```json
"progress": {
  "completedSteps": 3,
  "knownSteps": 5,
  "message": "Reviewing technical risks"
}
```

---

## 8. ExecutionResultEvent

Comunica el resultado funcional final o un resultado parcial explícitamente publicable.

### 8.1 Estructura

```json
{
  "specVersion": "1.0",
  "messageId": "evt-result-001",
  "messageType": "execution.result",
  "timestamp": "2026-09-22T09:47:20Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-previous",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "COMPLETED",
      "result": {
        "type": "proposal-analysis",
        "summary": "La propuesta presenta tres riesgos técnicos principales.",
        "data": {
          "riskCount": 3,
          "findingCount": 8
        },
        "artifacts": [
          {
            "artifactId": "art-report-001",
            "type": "analysis-report",
            "mediaType": "text/markdown",
            "uri": "/v1/artifacts/art-report-001"
          }
        ]
      }
    }
  }
}
```

### 8.2 Campos de result

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `type` | string | Sí | Tipo funcional del resultado. Extensible por capacidad. |
| `summary` | string/null | No | Resumen legible del resultado. |
| `data` | object | No | Resultado estructurado específico de la capacidad. |
| `artifacts` | array | No | Referencias a artifacts producidos. |
| `warnings` | array | No | Advertencias no fatales. |

El schema externo permanece estable aunque `result.data` cambie según la capacidad.

---

## 9. ArtifactProducedEvent

Permite notificar artifacts conforme se producen, sin esperar al final de la ejecución.

```json
{
  "specVersion": "1.0",
  "messageId": "evt-art-001",
  "messageType": "execution.artifact-produced",
  "timestamp": "2026-09-22T09:46:10Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-step-004",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "artifact": {
        "artifactId": "art-report-001",
        "type": "analysis-report",
        "mediaType": "text/markdown",
        "name": "proposal-analysis.md",
        "uri": "/v1/artifacts/art-report-001",
        "size": 18421,
        "checksum": "sha256:..."
      }
    }
  }
}
```

### Artifact

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `artifactId` | string/UUID | Sí | Identificador del artifact. |
| `type` | string | Sí | Tipo lógico. |
| `mediaType` | string | Sí | MIME type. |
| `name` | string/null | No | Nombre sugerido. |
| `uri` | string | Sí | Referencia recuperable. |
| `size` | integer/null | No | Tamaño en bytes. |
| `checksum` | string/null | No | Integridad del contenido. |
| `metadata` | object | No | Metadata extensible. |

Los artifacts grandes no deben viajar embebidos en NATS.

---

## 10. Error normalizado

Los errores deben tener una representación estándar independiente del agente o proveedor.

```json
{
  "code": "EXECUTION_FAILED",
  "category": "PLATFORM",
  "message": "The execution could not be completed.",
  "retryable": true,
  "details": {
    "reason": "MODEL_PROVIDER_TIMEOUT"
  }
}
```

| Campo | Tipo | Req. | Descripción |
|---|---|---:|---|
| `code` | string | Sí | Código estable de plataforma. |
| `category` | string | Sí | Categoría del error. |
| `message` | string | Sí | Mensaje seguro para consumidores. |
| `retryable` | boolean | Sí | Indica si el consumidor puede reintentar. |
| `details` | object | No | Detalle estructurado no sensible. |

No deben exponerse stack traces, prompts internos, secrets ni detalles de proveedores que rompan la abstracción.

---

## 11. Ejemplo completo de ciclo de E/S

### Paso 1: entrada REST

```http
POST /v1/executions
```

```json
{
  "correlationId": "proposal-P-1234",
  "command": {
    "name": "analyse-proposal",
    "intent": "Analiza la documentación recibida y detecta riesgos.",
    "input": {
      "proposalId": "P-1234"
    },
    "context": {
      "authorProfile": "commercial"
    },
    "instructions": [
      "Considera incorrecta la descripción del apartado 4.",
      "Prioriza riesgos de arquitectura y seguridad."
    ]
  }
}
```

### Paso 2: aceptación REST

```json
{
  "executionId": "exec-789",
  "correlationId": "proposal-P-1234",
  "status": "ACCEPTED"
}
```

### Paso 3: evento NATS - started

```json
{
  "specVersion": "1.0",
  "messageId": "evt-001",
  "messageType": "execution.lifecycle",
  "timestamp": "2026-09-22T09:45:01Z",
  "correlationId": "proposal-P-1234",
  "causationId": "msg-cmd-001",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "RUNNING",
      "event": {
        "type": "EXECUTION_STARTED",
        "sequence": 1
      }
    }
  }
}
```

### Paso 4: evento NATS - artifact

```json
{
  "specVersion": "1.0",
  "messageId": "evt-010",
  "messageType": "execution.artifact-produced",
  "timestamp": "2026-09-22T09:47:19Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-step-009",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "artifact": {
        "artifactId": "art-report-001",
        "type": "analysis-report",
        "mediaType": "text/markdown",
        "name": "proposal-analysis.md",
        "uri": "/v1/artifacts/art-report-001"
      }
    }
  }
}
```

### Paso 5: evento NATS - result

```json
{
  "specVersion": "1.0",
  "messageId": "evt-011",
  "messageType": "execution.result",
  "timestamp": "2026-09-22T09:47:20Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-010",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "COMPLETED",
      "result": {
        "type": "proposal-analysis",
        "summary": "Se identificaron tres riesgos técnicos principales.",
        "data": {
          "riskCount": 3
        },
        "artifacts": [
          {
            "artifactId": "art-report-001",
            "type": "analysis-report",
            "mediaType": "text/markdown",
            "uri": "/v1/artifacts/art-report-001"
          }
        ]
      }
    }
  }
}
```

### Paso 6: evento NATS - completed

```json
{
  "specVersion": "1.0",
  "messageId": "evt-012",
  "messageType": "execution.lifecycle",
  "timestamp": "2026-09-22T09:47:20Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-011",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "COMPLETED",
      "event": {
        "type": "EXECUTION_COMPLETED",
        "sequence": 12
      }
    }
  }
}
```

---

## 12. Ejemplo de fallo

```json
{
  "specVersion": "1.0",
  "messageId": "evt-fail-001",
  "messageType": "execution.lifecycle",
  "timestamp": "2026-09-22T09:47:20Z",
  "correlationId": "proposal-P-1234",
  "causationId": "evt-step-004",
  "source": {
    "type": "platform",
    "name": "ai-agent-platform"
  },
  "data": {
    "execution": {
      "executionId": "exec-789",
      "command": {
        "name": "analyse-proposal"
      },
      "status": "FAILED",
      "event": {
        "type": "EXECUTION_FAILED",
        "sequence": 5
      },
      "error": {
        "code": "EXECUTION_FAILED",
        "category": "PLATFORM",
        "message": "The execution could not be completed.",
        "retryable": true,
        "details": {
          "reason": "MODEL_PROVIDER_TIMEOUT"
        }
      }
    }
  }
}
```

---

## 13. Idempotencia y orden

### Idempotencia

Los productores deben mantener estable el `messageId` cuando reintentan exactamente el mismo mensaje.

La plataforma debe registrar mensajes procesados o una clave idempotente equivalente para evitar ejecuciones duplicadas.

### Orden

`event.sequence` es monotónico dentro de una `executionId` y permite reconstruir el orden lógico aunque el transporte entregue mensajes con redelivery.

No debe asumirse un orden global entre ejecuciones distintas.

---

## 14. Subjects NATS iniciales

Propuesta inicial, deliberadamente genérica:

```text
platform.commands.execution

platform.events.execution.lifecycle
platform.events.execution.result
platform.events.execution.artifact
```

El caso de uso no debe codificarse en el subject:

```text
platform.commands.analyse-proposal
platform.events.proposal-analysed
```

La capacidad concreta viaja dentro de `command.name`.

Esto evita crear infraestructura y contratos de transporte diferentes para cada nueva capacidad.

---

## 15. Versionado

`specVersion` versiona el contrato de plataforma.

Reglas:

- cambios aditivos compatibles no requieren cambiar la major version;
- cambios incompatibles requieren nueva major version;
- los consumidores deben ignorar campos desconocidos salvo que la especificación indique lo contrario;
- `command.name` y `result.type` tienen su propio ciclo de vida funcional, independiente del envelope.

---

## 16. Relación con CloudEvents

El contrato toma conceptos compatibles con CloudEvents:

- `id`;
- `source`;
- `type`;
- `specversion`;
- `time`;
- `data`.

En una fase posterior puede adoptarse CloudEvents de forma literal si aporta interoperabilidad suficiente. Hasta entonces, el envelope debe mantener una correspondencia sencilla con esos conceptos para evitar un formato propietario innecesariamente alejado de estándares.

---

## 17. Reglas de diseño

1. No crear un nuevo schema de integración por cada caso de uso.
2. No utilizar nombres de agentes como `command.name`.
3. No exponer prompts internos.
4. No acoplar los contratos a un proveedor LLM.
5. No incluir payloads grandes en NATS cuando puedan ser artifacts.
6. Mantener `correlationId` y `causationId` en toda la cadena.
7. Diseñar consumidores idempotentes.
8. Emitir eventos desde un Transactional Outbox.
9. Mantener la salida funcional de ejecución en NATS JetStream.
10. Usar REST para aceptación de comandos y consultas, no para esperar el resultado final.
