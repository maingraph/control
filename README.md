# Control — v0.1

A single private-task data store with authenticated REST API and MCP endpoint for AI assistants.

## Railway
Deploy Dockerfile, add volume mounted at `/data`, set `CONTROL_DB_PATH=/data/control.sqlite3` and `CONTROL_API_KEY` (random >=32 characters), and generate HTTPS domain. Keep one replica for SQLite. The key must be a Railway secret, never committed to Git.

## API
- `GET /healthz` (public)
- `GET /api/tasks?status=open|done|all`
- `POST /api/tasks` (title, notes?, priority?, project?, due_at?)
- `GET /api/tasks/{id}`
- `PATCH /api/tasks/{id}`
- `GET /api/export`
- MCP: `/mcp/`

Private routes require `Authorization: Bearer <CONTROL_API_KEY>` or `X-Control-Key`. Use your Railway domain for MCP connector URL. Do not put the key in chats or GitHub.

**Not yet verified:** live Claude Pro and ChatGPT Plus browser connectors. They must both pass an end-to-end task-sync test before claiming compatibility.
