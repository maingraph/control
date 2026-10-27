# Control → ChatGPT Plus web: Sites plugin setup

This is for **ChatGPT Plus web** in **Work mode** using **@Sites**.
Our real task and context database runs on Railway. Do not create a second production database.

## Starter prompt for @Sites (paste into a Work chat)

Build a **private ChatGPT Site** named "Control Connector" that hosts an MCP server and exposes **read/write tools in regular ChatGPT Plus web chats through its installed plugin**. The Site should act as a secure server-side bridge to my existing Control API; it must not create a second source of truth or hold permanent task data.

Existing Control backend:
- Base URL: https://control-api-production-0cff.up.railway.app
- API documentation: https://github.com/maingraph/control (read README and control/api.py and control/server.py)
- All /api endpoints require a secret bearer token.
- The secret is configured in Railway as CONTROL_API_KEY; I will enter the same value into the **Site's secret/environment variable settings** myself. Never ask me to paste the value into chat, source code, browser JavaScript, screenshots, or logs.

Site server-side access to the existing Control REST API must use:
`Authorization: Bearer <CONTROL_API_KEY>`

Expose these MCP tools through the Site plugin, with precise descriptions and safe input validation:

1. `list_control_tasks(status="open"|"done"|"all")` → `GET /api/tasks?status=...`
2. `get_control_task(task_id)` → `GET /api/tasks/{task_id}`
3. `create_control_task(title,notes?,due_at?,priority?,project?)` → `POST /api/tasks`
4. `update_control_task(task_id,patch)` → `PATCH /api/tasks/{task_id}`; never delete
5. `read_control_context()` → `GET /api/context`; show existing personal goals, preferences and notes
6. `update_control_context(key,value)` → `PUT /api/context/{key}` with `{"value":"..."}`
7. `export_control_data()` → `GET /api/export/all`

Use server-side fetch, never client-side secret access. Dates must use an explicit timezone; never invent a deadline. Handle 401/404/422 and unreachable-backend errors clearly. Do not store user data or credentials in Site files or repository.

Add a minimal connection test page (health check `GET /healthz` + authenticated context/task counts). The health check by itself does NOT prove authenticated API access.

First verify external API access and secure secret handling. If the Site runtime cannot reach the API securely, report the blocker; do not silently substitute a second database.

After previewing and testing, publish privately. Publishing must create the Site-hosted plugin, and I should then **install/connect it explicitly**. I want to @mention "Control Connector" in ordinary ChatGPT Plus browser chats to read and write the same Control data as Claude.

## Manual installation steps

1. On ChatGPT web choose **Work**, then start a Sites project (@Sites). Paste the prompt above.
2. In the resulting Site settings, configure `CONTROL_API_KEY` as a **secret**, not an ordinary browser-visible value, using the token from Railway's `control-api` service.
3. Confirm the Site makes authenticated server-side requests to the Railway API and reads previously populated context.
4. Publish the Site privately. Install the created plugin and authorize it.
5. In a standard ChatGPT web chat, mention **@Control Connector** and ask: "Read my Control context and list my open tasks."
6. After read works, create a disposable test task and verify it in both ChatGPT and Claude. Do not assume working sync until this test succeeds.

**Important**: Direct custom MCP server installation is not supported on ChatGPT Plus. Use a Site-hosted plugin. The Site's ability to make authenticated requests to this external Railway backend still requires testing.

The original GitHub repository is currently **public**. Keep all user data and secrets in Railway and the Site's private secrets; consider changing the GitHub repo to private.


## October 2026 update: mobile capture and structured inbox

The backend now has a private raw thought inbox used by the Android PWA:

- `GET /api/inbox?status=inbox|reviewed|archived|all`
- `POST /api/inbox` with `{"text":"verbatim thought","kind":"thought","source":"chatgpt"}`
- `PATCH /api/inbox/{capture_id}` with `{"status":"reviewed"}`
- `GET /api/context` now includes the pending `thought_inbox` field automatically.
- `GET /api/export/all` now includes `inbox` and capture audit events.

The existing installed Sites plugin's `read_control_context` tool already returns pending inbox entries without modification. However, its *write* tool definitions must be updated in the Sites editor for full functionality. Add three secure server-only proxy MCP tools:
1. `list_control_inbox(status="inbox")`
2. `capture_control_thought(text,kind="thought",source="chatgpt")` (never paraphrase original)
3. `review_control_capture(capture_id,status="reviewed")` (do not archive without confirmation)

These tools should call the REST endpoints with server-side secret injection. After republishing the Site, verify the new tools are exposed in ChatGPT Plus, and independently read back a newly created raw thought. Do not assert this is complete until tested. Avoid unnecessary exposure of the original thought content in Site logs.


## Semantic memory v0.2 — update the Sites plugin

The existing ChatGPT Plus connector can now read aggregate `semantic_memory` status via `GET /api/context`, but **new semantic tools won't appear automatically** in the installed Site. Add and republish these server-side proxy tools (same secret bearer authentication):

- `semantic_search_control(query,limit=8)` → `POST /api/memory/search` body `{"query":"...","limit":8}`
- `get_control_memory_status()` → `GET /api/memory/status`
- `suggest_related_control(node_id)` → `GET /api/memory/related/{node_id}?limit=5&threshold=0.42&propose=true` (link status remains suggested)
- `list_control_memory_nodes()` → `GET /api/memory/nodes`
- `list_control_links(status="all")` → `GET /api/memory/links?status=...`
- `propose_control_link(source_id,target_id,relation,rationale)` → `POST /api/memory/links` (all links created as suggested)
- `review_control_link(link_id,status)` → `PATCH /api/memory/links/{link_id}` `{"status":"confirmed"|"rejected"}` **only after user approval**
- `create_control_knowledge(kind,statement,source_node_id,evidence)` → `POST /api/memory/knowledge` (derived knowledge is always a draft)
- `review_control_knowledge(node_id,status)` → `PATCH /api/memory/knowledge/{node_id}` for user-confirmed derived claims.

**No secret may be embedded in site code, logs, browser JavaScript, or client requests.** Do not fabricate graph edges or represent high cosine similarity as evidence of psychological causation. All calls must proxy to the same Railway data, not a second Site database.

After republishing and installing the update, test a semantic search for "I postpone applying for jobs" and verify matches against Control nodes, then test an explicitly user-approved relationship before claiming ChatGPT write compatibility with graph operations.
