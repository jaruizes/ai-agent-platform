---
name: google-workspace
description: Google Workspace MCP server exposing Drive, Docs, Slides and Sheets.
command: node
args:
  - /opt/mcp/google-workspace/dist/server.js
cwd: /opt/mcp/google-workspace
environment:
  GOOGLE_OAUTH_CREDENTIALS: /run/secrets/google/google-oauth-credentials.json
  GOOGLE_OAUTH_TOKEN: /run/secrets/google/google-token.json
enabled: true
---

Google Workspace MCP server. Authentication material is mounted at runtime and is never stored in this definition.
