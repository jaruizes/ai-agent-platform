---
name: google-drive-export-file
description: Export a Google-native Drive file to Agent Platform scratch workspace.
implementationType: MCP
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
  tool: drive_export_file
inputSchema:
  type: object
  properties:
    fileId:
      type: string
      minLength: 1
    mimeType:
      type: string
      minLength: 1
    outputPath:
      type: string
      pattern: "^workspace/"
    overwrite:
      type: boolean
      default: false
  required:
    - fileId
    - mimeType
    - outputPath
  additionalProperties: false
---

Low-level diagnostic/export tool. Prefer google-drive-read-file when the goal is to analyze document content.
