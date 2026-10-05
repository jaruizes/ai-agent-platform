---
name: google-docs-create-from-artifact
description: Materialize a HUMAN_DOCUMENT or FINAL_DELIVERABLE artifact as a Google Doc without putting the long document text back into the Logical Plan.
implementationType: GOOGLE_DOCS_ARTIFACT_WRITE
enabled: true
sideEffect: WRITE
approvalPolicy: REQUIRED
configuration:
  server: google-workspace
inputSchema:
  type: object
  properties:
    artifactId:
      type: string
      format: uuid
    title:
      type: string
      minLength: 1
    destinationFolderId:
      type: string
      minLength: 1
  required:
    - artifactId
  additionalProperties: false
---

Preferred Tool for externally materializing a document that already exists as a managed Agent Platform artifact.

Pass an artifactId produced by a previous AGENT step. The platform retrieves the document content internally and sends it to Google Docs through the Google Workspace MCP.

Do not copy the artifact markdown into Tool arguments. This keeps the Logical Plan and orchestration state compact.

Use destinationFolderId when the Google Doc belongs in a specific opportunity folder.

Because this creates an externally visible document, approval is REQUIRED.
