---
name: google-drive-create-folder
description: Create a Google Drive folder, optionally under another folder.
implementationType: MCP
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
  tool: drive_create_folder
inputSchema:
  type: object
  properties:
    name:
      type: string
      minLength: 1
    parentFolderId:
      type: string
      minLength: 1
  required:
    - name
  additionalProperties: false
---

Create an output folder for an opportunity when the workflow requires one. This is an external side effect and requires approval.
