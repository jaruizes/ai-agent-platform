---
name: google-drive-list-folder
description: List the direct children of a Google Drive folder, including file IDs and MIME types.
implementationType: MCP
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
  tool: drive_list_folder
inputSchema:
  type: object
  properties:
    folderId:
      type: string
      minLength: 1
    pageSize:
      type: integer
      minimum: 1
      maximum: 1000
      default: 200
  required:
    - folderId
  additionalProperties: false
---

Use this tool when a process or user provides a Google Drive folder ID and you need to discover the files that belong to that folder. The returned IDs can be passed to google-drive-read-file.
