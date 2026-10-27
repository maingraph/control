# Control semantic memory — implementation status

**Implemented (v0.2):** Local, CPU-only FastEmbed `BAAI/bge-small-en-v1.5` 384-dimensional embeddings; encrypted-transport/private SQLite persistence; exact cosine similarity retrieval; source-preserving raw capture, task and context nodes; draft derived-knowledge nodes; explicit suggested/confirmed/rejected relationship edges; portable export containing nodes and links. Production Docker builds run synthetic-data semantic ranking and link review smoke tests.

**Important limitations:** SQLite does not use an approximate-nearest-neighbor vector index yet. Search scans embeddings and ranks by cosine. This is appropriate for a small personal archive, not a large deployment. The model is English-oriented, and similarity is not proof of cause, intention or psychological status. No extraction model automatically converts every thought into a structured interpretation: derived knowledge must be reviewed. `embedding` inference runs locally inside Railway, not via a separately billed external text API. Control remains a single-user prototype and has not been security-hardened for highly sensitive journaling.

## Capture → Clarify → Connect → Commit → Review

1. **Capture.** Store the exact original wording, creation time and capture source.
2. **Clarify.** Distinguish a task, reflection, concern, question or idea. Keep hypotheses as separate draft knowledge records, never replacing a raw note.
3. **Connect.** Retrieve semantically similar nodes. `related_to`, `supports`, `blocks`, `depends_on`, `part_of` edges initially have **suggested** status, even when suggested by AI. A person confirms or rejects.
4. **Commit.** Create the smallest action the user chooses, without invented deadlines. Optional if–then start cues and a realistic daily limit support doing rather than tracking.
5. **Review.** Revisit the raw inbox, drafts, linked evidence, priorities and unclear dates. Avoid punitive scores or diagnosing the person from recurring patterns.

## Database

- `captures` + `capture_events`: immutable original thoughts; review state changes audited.
- `tasks` + `events`: actions, deadlines and changes. Accidental task → thought conversion keeps the original task as `converted`, with provenance, and is not misreported as completion.
- `context_records`: named goals and planning preferences with provenance.
- `memory_nodes`: searchable source snapshots and separately derived draft knowledge.
- `memory_vectors`: normalized 384D local model vectors as float32 SQLite BLOBs plus model and text fingerprint.
- `memory_links`: typed relationships, source, rationale, timestamps, and human review status.

Source changes are indexed lazily at the next semantic query or explicit `POST /api/memory/reindex` call. The first query may take longer as it builds vectors. Query results carry source references and scores.

## API

- `GET /api/memory/status`
- `POST /api/memory/search` `{"query":"hard to start job applications","limit":8}`
- `POST /api/memory/reindex?limit=100`
- `GET /api/memory/nodes` and `POST /api/memory/knowledge`
- `PATCH /api/memory/knowledge/{node_id}` (confirm/reject drafted interpretation)
- `GET /api/memory/related/{node_id}?propose=true`
- `GET /api/memory/links`, `POST /api/memory/links`, `PATCH /api/memory/links/{link_id}`

All `/api/` endpoints require the existing Control secret. The installed ChatGPT Plus Sites plugin needs its tool definitions extended to call semantic search and link review endpoints. Claude's remote MCP endpoint exposes matching tools from the backend.

## Next improvements, not yet completed

- Postgres or sqlite-vec for indexed ANN retrieval if the personal corpus grows.
- Automatic summarization with a transparent confirmation queue, not silent AI rewriting.
- Optional multilingual embedding model after language needs are known.
- Robust backups, device-scoped authentication, key rotation, audit, and encrypted-at-rest storage.
- Native Samsung widget and background reminders.
