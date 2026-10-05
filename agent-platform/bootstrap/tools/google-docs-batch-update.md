---
name: google-docs-batch-update
description: Apply Google Docs API batchUpdate requests to an existing document.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: docs_batch_update
inputSchema:
  type: object
  properties:
    documentId:
      type: string
      minLength: 1
    requests:
      type: array
      minItems: 1
      items:
        type: object
  required:
    - documentId
    - requests
  additionalProperties: false
---

Advanced write tool for formatting or modifying a Google Doc after creation.

Use only when the simpler google-docs-create-with-text capability is insufficient.
