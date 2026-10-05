---
name: google-drive-read-file
description: Read semantic text from any supported Google Drive file by file ID. Handles Google Docs, Sheets and Slides through native APIs and PDF/DOCX/PPTX/XLSX/CSV/TXT/legacy office files through download plus Agent Platform document parsing.
implementationType: GOOGLE_DRIVE_READ
enabled: true
sideEffect: READ
approvalPolicy: NEVER
configuration:
  server: google-workspace
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

Preferred tool whenever you need to read, summarize, analyze or reason over a Google Drive file and you already have its file ID.

Do not guess which Google API to call from the MIME type. This tool resolves the file metadata first and automatically chooses:
- Google Docs -> compact Docs text reader
- Google Sheets -> compact Sheets text reader
- Google Slides -> compact Slides text reader
- supported binary documents such as PDF, DOCX, PPTX, XLSX, CSV and legacy Office formats -> Drive download plus Agent Platform DocumentParser

If you only have a folder ID, call google-drive-list-folder first and then call this tool once per relevant file ID.
