# Control event-triggered ChatGPT analysis — implementation plan

**Status (2026-10-28):**
- ChatGPT Plus **Scheduled**: existing Control AI thought review upgraded to every hour (the fastest supported recurring interval).
- Mobile PWA: **Analyze pending thoughts in ChatGPT** opens a new ChatGPT window and copies a prompt. A human must paste/send the prompt. Not an unattended trigger.
- True webhook-to-GPT: **NOT CONNECTED**. ChatGPT Work supports supported Gmail, Slack and GitHub events, not an arbitrary custom Control webhook. An event bridge must use one of those authorized connectors.

See the official OpenAI scheduled tasks documentation:
https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt

## Recommended: private GitHub PR signal

Why: GitHub is already connected. Supported ChatGPT Work triggers include new PRs and PR commit updates in an authorized GitHub.com repo.

Prerequisites:
1. Create a **private**, dedicated repo such as `maingraph/control-signals`. **Do not use the public `maingraph/control` repo** to signal private journal activity.
2. Give ChatGPT's GitHub connector access to that repository.
3. Create a fine-grained GitHub token (or dedicated GitHub App) with only Contents and Pull Requests write permission **for the signal repository**. Store it only as a Railway secret. Never add it to source, journal entries, browser JavaScript or ChatGPT instructions.
4. In ChatGPT **Work**, create a new **event-triggered** task monitoring PR commit updates in that repo. OpenAI's available trigger selections and authorization UI govern the final setup. If PR commits cannot be monitored, PR-open is an alternative but makes a PR for each batch.

Proposed event transport:
- Control persists raw text only in private Railway SQLite.
- The server queues a unique event ID and its source capture UUID; this is an outbox so events can be retried.
- A tiny Python/GitHub API call creates or updates a branch/PR in the private signal repo containing only an opaque ID and timestamp, never content, note titles, projects, or user details.
- ChatGPT Work detects the PR update and runs the **same instructions as hourly review**, using the installed Control Connector to retrieve the actual private records and write `ai_analysis_<captureidwithoutdashes>` drafts.
- Deduplicate by capture ID and review record; multiple or late GitHub deliveries must not create duplicate analyses.
- Pause/throttle bursts (e.g. a single PR update every 5–10 minutes; at most 3–10 uncategorized captures per run) to avoid costs and noisy notifications.
- Keep the hourly scheduled check as recovery when events are dropped.
- Before enabling, test one non-sensitive synthetic capture and verify (i) GitHub received only opaque metadata; (ii) event-triggered ChatGPT task actually started; (iii) connector read and saved review; (iv) no unrelated tasks changed.

**Caveats:** The GitHub private repo still exposes capture *activity metadata* to GitHub; PR events may consume ChatGPT Work limits, and are not necessarily immediate. A GitHub token has broad effect if leaked. Turn this feature off by default until the private repo and token exist. Avoid creating GitHub PRs for each thought unless the user explicitly agrees.

## Alternative: private Slack channel signal

If the user already has Slack:
1. Connect Slack in ChatGPT and create a private channel specifically for Control signals; add @ChatGPT.
2. Create a ChatGPT Work event-triggered task for **new channel messages**.
3. Configure an incoming Slack webhook URL as a Railway secret, and send only `Control has new capture: <opaque id>`, not the private note.
4. GPT must fetch the raw entry through Control Connector and write reviews back to Control.

Pros: simpler HTTP POST than GitHub branches/PRs. Cons: another external service/account, channel permissions and possible noisy Slack messages. Slack messages may also expose metadata.

## Alternative: Gmail notification trigger

A Gmail event-triggered task can watch a filtered subject/sender. Server would send a minimal non-sensitive notification email using a sender service; the model should then fetch actual data via Control. Requires mail sending credentials and Gmail connector. Emails are another external data/metadata store; not my first choice.

## Not supported

- There is no documented API to push arbitrary `POST /new-control-thought` directly into the ChatGPT Plus consumer Scheduled engine.
- A Railway cron job or a ChatGPT share URL cannot force an unattended GPT-6 model to run as the user's Plus account.
- The installed Control Sites plugin is a set of tools, not automatically a supported custom event source.
- The specific model used in Work/scheduled tasks and quotas may differ from the GPT-6 model selected in an interactive chat.
- Do not use a public GitHub repository to send raw journal text or other personally identifiable content.

## Safety and lifecycle

- Only draft analyses and proposed graph edges may be written without review; no automated deadline changes, deletes, self-diagnoses or commitments.
- Revoke signal tokens and disable the ChatGPT Work trigger when turning the bridge off.
- The authoritative record and deduplication state stay in Control, not in GitHub/Slack/Gmail.
- One private signal repo can later serve job applications, project changes, and captures; subject to explicit user permissions and safe per-event routing.
