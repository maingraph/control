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
