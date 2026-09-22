---
name: google-docs-get-document
description: Read the full structured content of a Google Docs document by document ID.
implementationType: MCP
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
  tool: docs_get_document
inputSchema:
  type: object
  properties:
    documentId:
      type: string
      minLength: 1
  required:
    - documentId
  additionalProperties: false
---

Use this tool when the user needs to read, summarize or analyze a Google Docs document and supplies its documentId.
