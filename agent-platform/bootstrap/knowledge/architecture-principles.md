---
knowledgeBase: architecture-standards
knowledgeBaseDescription: Principios y criterios de calidad para el diseño y revisión de soluciones técnicas.
documentName: architecture-principles.md
scope: TENANT
retentionPolicy: PERSISTENT
useCase: presales
chunkingPolicy:
  strategy: PARAGRAPH
  chunkSize: 1400
  overlap: 180
---

# Principios de arquitectura para ofertas

Estos principios son criterios de calidad genéricos, no decisiones obligatorias de tecnología.

## Ajuste al problema

La solución debe responder a requisitos y NFRs reales. Evitar plataformas, productos o patrones cuya complejidad no esté justificada.

## Separación de responsabilidades

Definir límites claros entre dominios, servicios, integraciones y responsabilidades operativas.

## Contratos explícitos

APIs, eventos, esquemas y dependencias relevantes deben tener contratos identificables y versionables.

## Seguridad desde diseño

Identidad, autorización, secretos, cifrado, exposición de red, auditoría y protección de datos deben tratarse como arquitectura, no como añadido final.

## Operabilidad

La solución debe contemplar observabilidad, diagnóstico, despliegue, soporte, recuperación y gestión de configuración.

## Resiliencia proporcional

Diseñar HA, DR, retries, timeouts e idempotencia según impacto y requisitos, evitando sobrearquitectura.

## Evolución

Favorecer decisiones reversibles y evolución incremental cuando sea viable.

## Datos

Aclarar ownership, sistemas de registro, consistencia, retención, acceso y gobierno.

## Integración

Elegir síncrono, eventos, batch o CDC según semántica y necesidades; no por moda tecnológica.

## Trazabilidad

Las principales decisiones deben poder relacionarse con requisitos, restricciones, riesgos o trade-offs.
