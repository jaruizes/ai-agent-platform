---
name: google-sheets-get-text
description: Read compact semantic text from all sheets in a Google Sheets spreadsheet for analysis and RAG ingestion.
implementationType: MCP
enabled: true
configuration:
  server: google-workspace
  tool: sheets_get_text
inputSchema:
  type: object
  properties:
    spreadsheetId:
      type: string
      minLength: 1
  required:
    - spreadsheetId
  additionalProperties: false
---

Preferred Google Sheets reader for analysis and knowledge ingestion. Preserves sheet boundaries and row values in a compact textual representation.
