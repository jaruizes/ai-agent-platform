---
name: google-drive-search-files
description: Search files and folders accessible in Google Drive.
implementationType: MCP
enabled: true
configuration:
  server: google-workspace
  tool: drive_search_files
inputSchema:
  type: object
  properties:
    name:
      type: string
    mimeType:
      type: string
    folderId:
      type: string
    fullText:
      type: string
    pageSize:
      type: integer
      minimum: 1
      maximum: 100
  additionalProperties: false
---

Use this tool to locate a Drive file when enough search information is present in the command.
