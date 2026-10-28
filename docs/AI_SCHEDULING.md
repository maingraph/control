# Control — AI-first processing (2026-10-28)

Control's source of truth is still the authenticated Railway SQLite database. The **ChatGPT Plus Scheduled** tasks are configured separately in ChatGPT (not in GitHub and not via Railway cron) so that an eligible ChatGPT model, rather than a locally hosted LLM, handles thoughtful analysis.

## Scheduled ChatGPT jobs

**Control AI thought review**: recurrence every 6 hours, condition watch. Using the installed Control Connector, read current goals and unprocessed raw notes; deduplicate using `ai_analysis_<32-character-capture-id>` context keys; write review *drafts* for at most 3 new captures; update `ai_latest_review`. No task creation, rescheduling, deletion, capture archiving, relationship confirmation or unsupported diagnosis. Do not notify on no-op. An active schedule is **not** yet proof that the scheduled context can reach the connector; test the first actual run and inspect saved output.

**Control weekly AI plan**: Monday morning in America/New_York. Draft context keys `ai_weekly_review_YYYYMMDD` and `ai_latest_weekly_review`; focus on a realistic 3–4 meaningful priorities, with optional implementation intentions; do not auto-create or edit commitments.

The ChatGPT scheduled task may run an eligible model different from the GPT-6 model selected in an interactive chat; users should inspect model options in the ChatGPT Scheduled UI. These tasks consume the account's relevant scheduled/agent usage limits.

## Mobile results

The Control PWA reads the existing authenticated `GET /mobile/context` endpoint and renders `ai_analysis_...` records as a dedicated AI thought analyses panel. These are *draft interpretations*, not verified truths. Data is escaped into textContent, not inserted as HTML. Full raw source text remains in the capture inbox and export.

## Railway cost controls

`CONTROL_INDEX_ON_STARTUP=false` (default) avoids eager ONNX loading at app restart.
`CONTROL_AUTO_PROCESS_ON_CAPTURE=false` (default) saves raw capture without immediately running local similarity, while retaining queued jobs.
The old `control-maintenance` Railway Function now runs once daily at `17 3 * * *` UTC as a recovery/snapshot fallback, not every six hours. On-demand semantic search still uses a local model in Railway, and the core server/volume incur their normal hosting charges.

## Event trigger limitations

An arbitrary Control HTTP webhook cannot directly launch this same ChatGPT conversation/model with ChatGPT Plus. Supported ChatGPT event-triggered tasks depend on official connected app events; the Control Sites plugin does not currently expose such an event source. Avoid fabricating a GitHub/Gmail/Slack event by copying private journal content there. For immediate AI review, open ChatGPT web and request a Control Connector read. Keep automatic scheduling separate from that immediate user-initiated flow.

## Verification checklist

- ChatGPT scheduled tasks visible and enabled in Scheduled: yes
- Railway daily recovery function cron confirmed: yes
- Latest Railway Control API deployment healthy: yes
- Mobile AI review display committed: yes
- Unattended ChatGPT run read/write to Control: pending actual execution
- End-to-end arbitrary new-capture webhook-to-GPT trigger: unsupported
