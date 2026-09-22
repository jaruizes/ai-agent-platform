---
name: google-slides-get-text
description: Read compact semantic text from a Google Slides presentation for analysis and RAG ingestion.
implementationType: MCP
enabled: true
configuration:
  server: google-workspace
  tool: slides_get_text
inputSchema:
  type: object
  properties:
    presentationId:
      type: string
      minLength: 1
  required:
    - presentationId
  additionalProperties: false
---

Preferred Google Slides reader for summarization, analysis and knowledge ingestion. Returns semantic text instead of the complete Slides API structure.
