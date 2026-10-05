---
name: google-drive-move-file
description: Move a Google Drive file to a destination folder.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: drive_move_file
inputSchema:
  type: object
  properties:
    fileId:
      type: string
      minLength: 1
    destinationFolderId:
      type: string
      minLength: 1
  required:
    - fileId
    - destinationFolderId
  additionalProperties: false
---

Move a generated or existing Drive file to the expected opportunity folder. Requires approval.
