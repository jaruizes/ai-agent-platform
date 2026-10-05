---
name: google-drive-download-file
description: Download a non-Google-native Drive file to Agent Platform scratch workspace.
implementationType: MCP
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
  tool: drive_download_file
inputSchema:
  type: object
  properties:
    fileId:
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
    - outputPath
  additionalProperties: false
---

Low-level diagnostic tool. Prefer google-drive-read-file for normal agent reasoning because it downloads and parses supported binary documents automatically.
