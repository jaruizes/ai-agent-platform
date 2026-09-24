# Google Workspace MCP

Local stdio MCP used by AI Agent Platform to access Google Drive, Docs, Slides
and Sheets.

## Read-oriented MCP tools

Drive:

- `drive_search_files`
- `drive_list_folder`
- `drive_get_file`
- `drive_download_file`
- `drive_export_file`

Google-native semantic readers:

- `docs_get_text`
- `slides_get_text`
- `sheets_get_text`

Lower-level structured readers are also available:

- `docs_get_document`
- `slides_get_presentation`
- `sheets_get_spreadsheet`
- `sheets_get_values`

The MCP also exposes write operations for generated Docs/Slides/Sheets and Drive
file management. Those are separate from the read-only bootstrap Tools used by
the proposal-analysis workflow.

## Agent Platform Tools

Agent Platform registers MCP capabilities as governed Tools.

For normal Drive analysis prefer:

```text
google-drive-list-folder(folderId)
        |
        v
google-drive-read-file(fileId)
```

`google-drive-read-file` is a high-level Agent Platform Tool backed by this MCP.

It resolves metadata with `drive_get_file` and then:

```text
Google Docs   -> docs_get_text
Google Sheets -> sheets_get_text
Google Slides -> slides_get_text

PDF/DOCX/PPTX/XLSX/CSV/TXT/legacy Office
        -> drive_download_file
        -> Agent Platform DocumentParser
        -> semantic text
```

This avoids teaching every planner how to branch on Google MIME types and keeps
binary parsing in Agent Platform, where the existing document parser already
supports those formats.

## Scratch-storage safety

`drive_download_file` and `drive_export_file` only write under the
`workspace/` tree. They refuse destinations outside that boundary and do not
overwrite existing files unless `overwrite=true`.

The high-level `google-drive-read-file` Tool creates a unique scratch
subdirectory, parses the file and removes the temporary download afterwards.

## OAuth setup

Create an OAuth client in Google Cloud and place the downloaded client
credentials at:

```text
.secrets/google-oauth-credentials.json
```

From the repository root:

```bash
npm --prefix mcp/google-workspace install
npm --prefix mcp/google-workspace run auth
```

The authorization flow writes:

```text
.secrets/google-token.json
```

Both files stay outside the platform catalog. Docker mounts `.secrets`
read-only into the Agent Platform container and the bootstrap MCP definition
points to:

```text
/run/secrets/google/google-oauth-credentials.json
/run/secrets/google/google-token.json
```

The OAuth scopes currently cover Drive read access plus Docs, Slides and Sheets.

## Local source validation

```bash
npm --prefix mcp/google-workspace run build
npm --prefix mcp/google-workspace run doctor
```

## Docker/platform validation

After rebuilding Agent Platform:

```bash
docker compose up -d --build agent-platform
bash scripts/google-workspace-mcp-smoke.sh
```

To exercise the full high-level reader against a real file:

```bash
GOOGLE_DRIVE_TEST_FILE_ID=<drive-file-id> \
  bash scripts/google-workspace-mcp-smoke.sh
```

The file may be a Google Doc/Sheet/Slides file or a supported binary such as a
PDF or DOCX.
