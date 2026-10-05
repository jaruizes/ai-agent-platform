---
name: google-drive-get-file
description: Get Google Drive file metadata by file ID.
implementationType: MCP
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
  tool: drive_get_file
inputSchema:
  type: object
  properties:
    fileId:
      type: string
      minLength: 1
  required:
    - fileId
  additionalProperties: false
---

Use this tool to inspect a Drive item's name, MIME type, parents and metadata without reading its content.
