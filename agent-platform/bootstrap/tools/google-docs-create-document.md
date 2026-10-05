---
name: google-docs-create-document
description: Create an empty Google Docs document.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: docs_create_document
inputSchema:
  type: object
  properties:
    title:
      type: string
      minLength: 1
  required:
    - title
  additionalProperties: false
---

Low-level Google Docs creation tool. Prefer google-docs-create-with-text when the full document content is already available.
