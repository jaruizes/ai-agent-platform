---
name: google-drive-copy-file
description: Copy a Google Drive file, optionally into a destination folder.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: drive_copy_file
inputSchema:
  type: object
  properties:
    fileId:
      type: string
      minLength: 1
    newName:
      type: string
      minLength: 1
    destinationFolderId:
      type: string
      minLength: 1
  required:
    - fileId
    - newName
  additionalProperties: false
---

Useful when a corporate template document must be copied before editing. Requires approval.
