---
name: google-docs-get-text
description: Read compact semantic text from a Google Docs document by document ID, optimized for summarization and LLM analysis.
implementationType: MCP
enabled: true
configuration:
  server: google-workspace
  tool: docs_get_text
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

Preferred tool for summarization, analysis and reasoning over Google Docs content. Returns title, documentId, extracted text and character count instead of the complete Google Docs API structure.
