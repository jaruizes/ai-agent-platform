---
name: google-docs-create-with-text
description: Create a Google Docs document from generated text and optionally place it in a Drive folder.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: docs_create_with_text
inputSchema:
  type: object
  properties:
    title:
      type: string
      minLength: 1
    text:
      type: string
    destinationFolderId:
      type: string
      minLength: 1
  required:
    - title
    - text
  additionalProperties: false
---

Preferred write tool for materializing a generated report, solution document or RFP/RFI response as a Google Doc.

Use destinationFolderId when the final document should be placed in a specific customer/opportunity folder.

Because this creates an external document, execution requires approval.
