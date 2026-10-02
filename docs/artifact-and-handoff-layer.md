# Artifact & Handoff Layer

## 1. El problema: una única salida no sirve bien a todos

En una demo es habitual tratar la salida de un agente como un único bloque de
texto:

    Agent
      |
      v
    informe narrativo de 20 páginas

Ese enfoque empieza a fallar cuando el resultado tiene dos consumidores muy
distintos:

- una persona que necesita leer, entender, comparar y aprobar;
- otro agente que necesita hechos, restricciones, decisiones y preguntas
  abiertas con el mínimo contexto posible.

Un humano quiere narrativa. Un agente posterior normalmente necesita un contrato
compacto.

Si damos a ambos el mismo documento largo aparecen cuatro problemas:

1. peor experiencia de revisión humana;
2. más tokens de entrada en cada paso posterior;
3. reinterpretación repetida de información ya comprendida;
4. contratos débiles entre pasos.

La plataforma cambia por tanto de "los agentes se pasan texto" a "los agentes
publican artefactos tipados".

---

## 2. Modelo de artefactos

Un agente productor puede publicar hasta cinco tipos:

    Agent execution
          |
          +-- HUMAN_DOCUMENT
          +-- MACHINE_DATA
          +-- AGENT_HANDOFF
          +-- EVIDENCE_SET
          +-- FINAL_DELIVERABLE

Cada tipo está optimizado para un consumidor diferente.

### HUMAN_DOCUMENT

Documento narrativo pensado para una persona.

Ejemplos:

- informe de entendimiento y cualificación;
- diseño de solución;
- revisión arquitectónica;
- borrador de propuesta.

Puede ser detallado y legible, pero no se inyecta automáticamente en el contexto
de agentes posteriores.

### MACHINE_DATA

Representación estructurada de hechos, requisitos, riesgos, restricciones y
decisiones duraderas.

Ejemplo conceptual:

    {
      "customerNeeds": [
        {
          "id": "NEED-001",
          "description": "Reduce release lead time"
        }
      ],
      "constraints": [
        {
          "id": "CON-001",
          "description": "Target platform must be AWS"
        }
      ],
      "risks": [
        {
          "id": "RISK-001",
          "severity": "HIGH",
          "description": "Migration timeline is aggressive"
        }
      ]
    }

Un agente posterior puede consumir este JSON sin volver a interpretar un informe
narrativo.

### AGENT_HANDOFF

Contexto deliberadamente pequeño para transferir trabajo entre agentes.

Ejemplo:

    {
      "objective": "Design the technical solution",
      "keyFacts": [
        "AWS is mandatory",
        "First production migration is expected in six months"
      ],
      "hardConstraints": [
        "Customer identifiers must be preserved"
      ],
      "openQuestions": [
        "Is active-active DR mandatory?"
      ],
      "recommendedNextActions": [
        "Consult security architecture"
      ]
    }

El handoff no es otro resumen para humanos. Su criterio de calidad es cuánto
contexto útil transmite con el menor coste cognitivo y de tokens posible.

### EVIDENCE_SET

Referencias que sustentan afirmaciones relevantes.

    {
      "items": [
        {
          "claim": "AWS is mandatory",
          "sourceId": "RFP.pdf",
          "locator": "page 14"
        }
      ]
    }

Se prefieren referencias a evidencia frente a copiar fragmentos de documentos en
cada salida.

### FINAL_DELIVERABLE

Artefacto humano cuyo propósito es la entrega externa.

Ejemplos:

- respuesta final a una RFP;
- propuesta técnica final;
- informe listo para cliente.

Comparte modelo con HUMAN_DOCUMENT, pero su semántica indica que ya es un
entregable.

---

## 3. Una llamada de modelo, varios artefactos

Una decisión fundamental es que no se hacen llamadas adicionales al LLM para
crear las distintas representaciones.

El agente principal recibe un contrato estructurado dentro de la misma llamada:

    business-analyst model call
             |
             v
    {
      summary,
      humanDocument,
      machineData,
      handoff,
      evidence
    }
             |
             v
       ArtifactService
             |
             +-- HUMAN_DOCUMENT
             +-- MACHINE_DATA
             +-- AGENT_HANDOFF
             +-- EVIDENCE_SET

La plataforma separa y persiste los campos de forma determinista.

Se evita así este antipatrón:

    call 1 -> generar resultado
    call 2 -> resumir para agentes
    call 3 -> reescribir para humanos
    call 4 -> extraer JSON estructurado

Ese enfoque multiplica coste y latencia y puede introducir divergencias
semánticas entre las cuatro representaciones.

Si el modelo no respeta el contrato estructurado, la plataforma no hace una
llamada de reparación automática. Usa un fallback:

- el contenido original se conserva como HUMAN_DOCUMENT;
- se genera deterministicamente un AGENT_HANDOFF mínimo;
- la ejecución sigue siendo inspeccionable.

La degradación es por tanto controlada y no multiplica llamadas.

---

## 4. artifactPolicy en AGENTIC_EXECUTION

El ProcessDefinition puede declarar la política de salida de un paso:

    {
      "artifactPolicy": {
        "enabled": true,
        "schema": "proposal-qualification/v1",
        "humanTitle": "Informe de entendimiento y cualificación",
        "humanArtifactType": "HUMAN_DOCUMENT",
        "agentNames": ["business-analyst"],
        "maxOutputTokens": 8000
      }
    }

Process Platform propaga esta política como metadata de la ejecución delegada.

agentNames es especialmente útil cuando un LogicalPlan contiene especialistas:

    security-architect
    cloud-architect
    data-architect
            |
            v
    solution-architect

Los especialistas pueden trabajar normalmente, pero sólo el arquitecto principal
publica el bundle autoritativo de solución.

Esto evita que una única fase de proceso genere versiones de artefactos por cada
agente auxiliar.

---

## 5. El proceso almacena referencias, no documentos

Sin una capa de artefactos el ProcessContext tiende a crecer:

    qualification:
      informe de 20 páginas

    solution:
      documento de 35 páginas

    final:
      respuesta de 50 páginas

Ese contenido termina circulando por persistencia, NATS, serialización y contexto
de modelo.

Con Artifact & Handoff, el resultado de la ejecución contiene referencias
compactas:

    {
      "summary": "Qualification ready for review",
      "artifacts": [
        {
          "artifactId": "...",
          "type": "HUMAN_DOCUMENT",
          "schema": "proposal-qualification/v1/human",
          "version": 1,
          "title": "Informe de entendimiento y cualificación"
        },
        {
          "artifactId": "...",
          "type": "MACHINE_DATA",
          "schema": "proposal-qualification/v1",
          "version": 1
        },
        {
          "artifactId": "...",
          "type": "AGENT_HANDOFF",
          "schema": "proposal-qualification/v1/handoff",
          "version": 1
        }
      ]
    }

Process Platform conserva estado de workflow y referencias. Agent Platform conserva
el contenido semántico.

    Process Platform
          |
          | artifact refs
          v
    Agent Platform Artifact Store
          |
          +-- human content
          +-- machine content
          +-- handoff
          +-- evidence

Esto preserva la separación de bounded contexts.

---

## 6. Contexto para agentes posteriores

Cuando Agent Platform encuentra artifactId en los inputs/dependencias, resuelve
automáticamente sólo los tipos apropiados para otro modelo.

Se incluyen:

    AGENT_HANDOFF
    MACHINE_DATA
    EVIDENCE_SET

Se excluyen:

    HUMAN_DOCUMENT
    FINAL_DELIVERABLE

Ejemplo:

    qualification HUMAN_DOCUMENT
           25k tokens
               X
               |
               | no se inyecta
               |
        solution-architect
               ^
               |
        qualification AGENT_HANDOFF
           ~1k tokens

        qualification MACHINE_DATA
           JSON compacto

El Context Engine registra este contenido como ARTIFACT_CONTEXT.

Esto no es simplemente truncar el documento largo. Es una proyección semántica
preparada por el propio productor.

El documento completo sigue disponible para el humano y para inspección, pero ya
no es contexto obligatorio de todos los modelos posteriores.

---

## 7. Presupuestos de salida y entrada

La capa introduce presupuestos en ambos sentidos.

### Presupuesto de generación

artifactPolicy.maxOutputTokens se pasa como límite a la llamada de modelo.

Valores iniciales del caso de preventa:

    qualification        8,000 max output tokens
    solution design     12,000 max output tokens
    final RFP response  16,000 max output tokens

Son límites, no objetivos.

El contrato también da objetivos internos:

    summary       <= 500 tokens
    machineData   ~ 2,500 tokens
    handoff       ~ 1,200 tokens

### Presupuesto de consumo

ARTIFACT_CONTEXT tiene un límite independiente:

    artifact_context_max_chars = 24,000

El handoff se limita además antes de persistirse.

La primera implementación usa límites de caracteres como guardrail portable. Una
evolución natural es hacerlos model-aware y expresarlos en tokens reales.

---

## 8. Versionado e iteración humana

El scope de un artefacto procedente de Process Platform es estable:

    process:{processInstanceId}:step:{processStepKey}

Por ello el review loop crea versiones automáticamente:

    understand-and-qualify

    iteration 1
      HUMAN_DOCUMENT v1
      MACHINE_DATA v1
      AGENT_HANDOFF v1

            HUMAN REQUEST_CHANGES

    iteration 2
      HUMAN_DOCUMENT v2
      MACHINE_DATA v2
      AGENT_HANDOFF v2

            HUMAN GO

Las versiones anteriores son inmutables.

Esto mejora auditabilidad y prepara la plataforma para una futura comparación
visual v1 vs v2.

---

## 9. Revisión humana amigable

La HumanTask recibe referencias porque depende del AGENTIC_EXECUTION productor.

El Control Plane descubre esas referencias y muestra una sección específica de
Review artifacts.

El humano puede abrir el HUMAN_DOCUMENT en una vista de lectura que proyecta de
forma segura:

- títulos;
- subtítulos;
- párrafos;
- bullets.

No se renderiza HTML arbitrario generado por el modelo.

El flujo esperado es:

    Qualification Review

    HUMAN_DOCUMENT
    Informe de entendimiento y cualificación
    v2

    Executive summary
    ...

    Customer needs
    ...

    Risks
    ...

    Open questions
    ...

    [REQUEST_CHANGES]       [GO]

MACHINE_DATA, AGENT_HANDOFF y EVIDENCE_SET siguen siendo inspeccionables para
diagnóstico, pero no son la UX principal del revisor.

---

## 10. Revisar antes de materializar externamente

Esta capa cambia un patrón importante.

Antes podía ocurrir:

    business-analyst
          |
          v
    google-docs-create-with-text
          |
          v
    Tool approval
          |
          v
    Process HUMAN review

Eso crea un side effect antes de saber si el contenido es válido.

El patrón recomendado pasa a ser:

    business-analyst
          |
          v
    internal HUMAN_DOCUMENT
          |
          v
    Process HUMAN review
          |
       GO / APPROVE
          |
          v
    materialización externa si hace falta

Para el entregable final:

    rfp-response-writer
          |
          v
    FINAL_DELIVERABLE
          |
          v
    google-docs-create-from-artifact
          |
          v
    Agent Platform WRITE approval
          |
          v
    Google Docs

Se separan dos decisiones humanas diferentes:

    Process HUMAN
    "¿El contenido funcional/técnico es válido?"

    Agent Tool Approval
    "¿Puede la plataforma ejecutar este WRITE externo?"

La optimización de artifacts no debilita governance.

---

## 11. Materialización desde referencia

Pasar otra vez todo el documento largo dentro de toolArguments eliminaría parte
del beneficio.

Por eso existe:

    google-docs-create-from-artifact

Input:

    {
      "artifactId": "...",
      "destinationFolderId": "..."
    }

La Tool:

1. recupera el artifact internamente;
2. comprueba que es HUMAN_DOCUMENT o FINAL_DELIVERABLE;
3. obtiene su Markdown;
4. llama al MCP google-workspace / docs_create_with_text;
5. devuelve la referencia al Google Doc.

El documento largo no forma parte del LogicalPlan ni de los argumentos generados
por el planner.

La Tool mantiene:

    sideEffect = WRITE
    approvalPolicy = REQUIRED

---

## 12. Persistencia y evolución del Artifact Store

La primera versión persiste metadata y contenido en PostgreSQL JSONB detrás de
ArtifactRepositoryPort.

Es una elección pragmática para esta fase:

- transacciones simples;
- desarrollo local sencillo;
- sin nueva infraestructura;
- consistencia entre metadata y body.

El dominio no depende de PostgreSQL.

En producción de mayor escala el mismo port puede evolucionar a:

    PostgreSQL metadata
           +
    S3 / Azure Blob / GCS bodies

sin cambiar Process Platform ni el contrato entre agentes.

Los artifacts actuales son contenido semántico textual/JSON. Los binarios grandes
deben seguir viviendo en almacenamiento externo y referenciarse.

---

## 13. Por qué esto va antes que prompt caching

Prompt caching puede abaratar contexto repetido, pero no corrige una arquitectura
que manda demasiado contexto.

Si todos los pasos reciben 90k tokens:

    prompt caching
          |
          v
    prompts de 90k más baratos

Artifact & Handoff ataca el problema anterior:

    90k tokens de resultado previo
          |
          v
    ~1k handoff
    + machine data compacta
    + retrieval selectivo

Después sí tiene sentido añadir caching para:

- system prompts;
- instrucciones de agentes;
- skills;
- schemas de tools;
- knowledge corporativo estable.

Orden recomendado de optimización:

    1. Typed artifacts
    2. Agent handoffs
    3. Selective retrieval
    4. Context budgets
    5. Prompt caching
    6. Model / decision routing

---

## 14. Ejemplo completo de preventa

    Google Drive RFP documents
            |
            v
    Business Analyst
            |
            +-- qualification HUMAN_DOCUMENT v1
            +-- qualification MACHINE_DATA v1
            +-- qualification AGENT_HANDOFF v1
            +-- qualification EVIDENCE_SET v1
            |
            v
    Human review
            |
      REQUEST_CHANGES
            |
            v
    Business Analyst
            |
            +-- qualification ... v2
            |
           GO
            |
            v
    Solution Architect
            |
            | recibe handoff + machine data
            | recupera fuentes sólo cuando las necesita
            |
            +-- solution HUMAN_DOCUMENT v1
            +-- solution MACHINE_DATA v1
            +-- solution AGENT_HANDOFF v1
            |
            v
    Human review
            |
         APPROVE
            |
            v
    RFP Response Writer
            |
            | recibe artifacts compactos aprobados
            | recupera fuentes/knowledge selectivamente
            |
            +-- FINAL_DELIVERABLE
            +-- MACHINE_DATA
            +-- AGENT_HANDOFF
            |
            v
    google-docs-create-from-artifact
            |
            v
    WRITE approval
            |
            v
    Google Drive

---

## 15. Antes y después

### Antes

    Agent A output:
      25k tokens narrative

    ProcessContext:
      25k tokens

    Agent B input:
      source documents
      + 25k previous report
      + instructions
      + skills
      + tools
      + knowledge

    Agent B output:
      35k tokens narrative

    Agent C input:
      sources
      + qualification
      + solution
      + ...

El contexto crece con cada fase.

### Después

    Agent A output:
      human report       -> almacenado/review
      machine data       -> compacto
      handoff            -> muy compacto
      evidence           -> referencias

    ProcessContext:
      summary + artifact refs

    Agent B input:
      handoff
      + selected machine data
      + selected evidence
      + retrieval bajo demanda

El ahorro exacto depende del workload, pero la mejora estructural es determinista:
el documento humano deja de ser contexto obligatorio para todos los pasos
posteriores.

---

## 16. Observabilidad

Los Context Snapshots registran provenance de artifacts.

La plataforma puede explicar:

- qué artifact se usó;
- tipo;
- versión;
- scope;
- si fue truncado por budget.

Métricas futuras especialmente útiles:

    artifact bytes produced
    handoff / human-document size ratio
    artifact context tokens
    human-document tokens avoided
    versions per human review
    external materializations
    estimated context tokens saved

Estas métricas ayudan a explicar por qué una ejecución es cara, no sólo cuánto
cuesta.

---

## 17. APIs actuales

Agent Platform expone:

    GET /v1/artifacts/{artifactId}

    GET /v1/executions/{executionId}/artifacts

    GET /v1/artifacts?scopeKey=...&latestOnly=true

Los endpoints de listado devuelven metadata, no el body completo.

El contenido se obtiene explícitamente por artifactId.

Esto evita transferir grandes documentos accidentalmente en listados o detalles
de ejecución.

---

## 18. Principios de diseño

### Diferentes consumidores merecen diferentes contratos

Un informe humano y un handoff agéntico tienen criterios de calidad diferentes.
Intentar que un documento sirva a ambos suele empeorar ambos.

### El proceso mantiene referencias, no working material agéntico

Process Platform necesita estado durable y referencias. No necesita duplicar el
contenido semántico interno de Agent Platform.

### Contexto es una proyección seleccionada

Que un artifact exista no significa que todo agente deba recibirlo.

### La revisión no debe requerir side effects externos

Un artifact interno permite revisar antes de escribir en Drive, enviar emails o
modificar sistemas externos.

### La optimización empieza antes de generar la salida

Los budgets y el contrato se dan al modelo. No se confía sólo en comprimir una
respuesta arbitrariamente grande después.

### El versionado es parte de la auditabilidad

REQUEST_CHANGES crea una nueva versión. No se sobreescribe lo que el humano
revisó anteriormente.

---


## 18.1 El productor del artifact es un contrato, no una sugerencia

Cuando una fase declara:

    "agentNames": ["solution-architect"]

la intención no es simplemente influir al planner.

Agent Platform valida después del planning que:

- existe un step AGENT ejecutado por `solution-architect`;
- ese step forma parte del camino que conduce al resultado final.

Por ejemplo, este plan es inválido:

    solution-architect     business-analyst
          |                      |
          v                      v
      artifact                 final

porque el productor configurado queda desconectado del resultado final.

El patrón aceptado es:

    specialists
        |
        v
    solution-architect
        |
        v
      final

Esta decisión ilustra una separación importante en plataformas agénticas:

    LLM
    propone una estrategia

    Plataforma
    garantiza invariantes

Los prompts expresan intención. Los contratos críticos de ejecución se validan
en código.

---

## 19. Limitaciones de esta primera versión

La implementación inicial es deliberadamente pequeña.

Limitaciones actuales:

- cuerpos de artifact inline en PostgreSQL;
- renderer humano seguro pero no Markdown completo;
- schema identificado por nombre, aún sin Schema Registry;
- selección automática por tipo/budget, no retrieval semántico de artifacts;
- sin diff visual entre versiones;
- métricas de ahorro de tokens aún no calculadas;
- la suspensión WAITING_APPROVAL de Agent Platform todavía debe propagarse a
  Process Platform para pausar el presupuesto temporal durante governance waits.

Evoluciones naturales:

1. JSON Schema Registry para MACHINE_DATA;
2. object storage para bodies grandes;
3. semantic artifact retrieval;
4. diff v1/v2 para reviews;
5. métricas de context tokens avoided;
6. prompt caching del contexto estático restante;
7. propagación de suspensiones Agent -> Process.

---

## 20. Idea central para un artículo

El cambio conceptual puede resumirse así:

    "Agents passing text to agents"

se convierte en:

    "Agents publishing typed, versioned artifacts"

con cuatro proyecciones principales:

    human projection
    machine contract
    compact handoff
    evidence references

La mejora no es solamente económica.

Introduce contratos de información explícitos entre pasos de razonamiento,
mejora el Human-in-the-Loop, reduce acoplamiento entre agentes, conserva
trazabilidad y evita convertir texto arbitrario del modelo en estado de workflow.

La plataforma deja de tratar cada respuesta del LLM como una cadena y empieza a
tratarla como datos gestionados.


---

## 21. Cómo validar la implementación

### Tests de código

Agent Platform incluye tests para:

- creación del bundle HUMAN_DOCUMENT / MACHINE_DATA / AGENT_HANDOFF /
  EVIDENCE_SET;
- versionado de artifacts en review loops;
- exclusión de HUMAN_DOCUMENT del contexto automático;
- fallback sin segunda llamada al modelo;
- materialización de un artifact directamente en Google Docs.

Ejecutar:

    cd agent-platform
    pytest -q

### Construcción de la plataforma

Desde la raíz:

    docker compose up -d --build agent-platform process-platform control-plane-ui

La migración 017 crea execution_artifacts automáticamente durante el arranque de
Agent Platform.

### Configuración desde Process Designer

En un AGENTIC_EXECUTION activar:

    Typed artifact output

Configurar, por ejemplo:

    Machine schema:
    proposal-qualification/v1

    Human artifact title:
    Informe de entendimiento y cualificación

    Human artifact type:
    HUMAN_DOCUMENT

    Capture only agents:
    business-analyst

    Max output tokens:
    8000

Guardar la nueva versión del ProcessDefinition y activarla.

### Qué observar en una ejecución

En el detalle de Agent Platform debe aparecer:

    TYPED ARTIFACTS

con al menos:

    HUMAN_DOCUMENT
    MACHINE_DATA
    AGENT_HANDOFF

y, cuando haya evidencia declarada:

    EVIDENCE_SET

El resultado técnico de la ejecución debe contener artifactRefs y no necesitar
transportar el cuerpo completo del informe humano.

### Qué observar en el Human Task

Cuando el siguiente step sea HUMAN, la bandeja de Process Platform debe mostrar:

    Review artifacts

El HUMAN_DOCUMENT se abre en la vista de lectura de Control Plane.

El humano puede dar GO/APPROVE o REQUEST_CHANGES sin crear previamente un Google
Doc.

### Comprobar versionado

Después de REQUEST_CHANGES y de una nueva ejecución del productor:

    v1 -> primera salida
    v2 -> salida revisada

Ambas versiones permanecen disponibles.

### Smoke sin nuevas llamadas LLM

Una vez exista una ejecución productora:

    ARTIFACT_EXECUTION_ID=<agent-execution-id> \
      bash scripts/artifact-layer-smoke.sh

Alternativamente, usando el scope del proceso:

    PROCESS_INSTANCE_ID=<process-instance-id> \
    PROCESS_STEP_KEY=understand-and-qualify \
      bash scripts/artifact-layer-smoke.sh

El smoke comprueba:

- metadata list sin bodies;
- HUMAN_DOCUMENT no vacío;
- MACHINE_DATA presente;
- AGENT_HANDOFF presente.

Resultado esperado:

    Artifact & Handoff Layer smoke test PASSED.

### Validar consumo compacto

En el siguiente AGENTIC_EXECUTION abrir:

    Context Snapshots

Debe aparecer un componente:

    ARTIFACT_CONTEXT

Su provenance mostrará referencias a MACHINE_DATA / AGENT_HANDOFF /
EVIDENCE_SET.

No debe aparecer el HUMAN_DOCUMENT completo como contexto automático.

Este es el punto principal de la optimización: el documento permanece disponible
para la persona, pero no se convierte en coste obligatorio para el siguiente
agente.


---

## Human review UX: artifact first, transport payload second

A HUMAN process task must not expose the integration envelope as its primary
review experience.

The review hierarchy is:

```text
1. HUMAN_DOCUMENT / FINAL_DELIVERABLE
   -> primary review surface

2. Legacy generated output
   -> compatibility fallback for process definitions created before artifactPolicy

3. Technical payload/result
   -> diagnostic information only
```

This matters because the Process Platform input envelope contains implementation
details such as `processInput`, `context`, dependencies and delegated execution
results. Those are useful for debugging but are not a business review document.

The Control Plane therefore renders human artifacts as structured review
content and keeps the raw payload behind an explicit "Show technical payload /
result" control.

The expansion state is owned by Angular rather than the native HTML `details`
element. This is intentional: the Control Plane refreshes live process state
periodically, and replacing task objects during polling must not collapse a
reviewer-opened diagnostic panel.

### Backward compatibility

Existing ACTIVE process definitions are immutable and may predate
`artifactPolicy`.

When a HUMAN review receives no typed human artifact, Control Plane attempts to
extract the previous producer's generated narrative output and renders it as
"Legacy output". This allows an in-flight process to be reviewed without
restarting it.

New process versions should enable typed artifact output on reviewable
AGENTIC_EXECUTION producers.
