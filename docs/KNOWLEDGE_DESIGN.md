# Control knowledge architecture and processing protocol

**Implemented today:** persistent SQLite tables for tasks, task events, named context records, raw inbox captures and capture events. AI can read/update them via authenticated REST/MCP. No embedding/vector index or semantic-nearest-neighbor search is currently implemented.

## Capture → Clarify → Connect → Commit → Review

1. **Capture.** Store original words, exact creation timestamp, capture source and a broad kind (thought, idea, question, observation, journal, task seed). Do not silently paraphrase or diagnose.
2. **Clarify.** When reviewing, distinguish obligations from possibilities, feelings, concerns, information and projects. Preserve original entry separately from derived interpretations. Record uncertainty.
3. **Connect.** Link items to existing goals and projects only when supported by the user. Avoid imposing causal/psychological conclusions.
4. **Commit.** Where the user chooses to act, prefer one physical next action, an appropriate deadline only if specified, and optional situational if-then start cue. Cap daily planned priorities to the user's stated comfort level rather than inventing a fixed rigid routine.
5. **Review.** Revisit the unprocessed inbox and priorities regularly; allow edits, deferrals, and corrections without a punitive score. Do not mark journal entries as tasks unless the user asks.

The implementation-intentions and mental-contrasting/WOOP concepts can support getting started but cannot guarantee outcomes or substitute for professional psychological treatment.

## Proposed semantic memory (not implemented)

- **Knowledge nodes:** `id`, `kind` (goal/project/event/decision/preference/constraint/observation), `statement`, `source_id`, `certainty`, `confirmed_by_user`, `valid_from`, `valid_to`, `created_at`, `updated_at`
- **Relations:** `source_id`, `target_id`, `relation` (supports/blocks/part_of/related_to/depends_on), `rationale`, `provenance`
- **Embeddings:** source text fingerprint, model name/version, vector representation, update timestamp, explicit consent to processing
- **Retrieval:** exact structured SQL first, then scoped semantic retrieval, and AI synthesis quoting original supporting records
- **Corrections:** retain original capture immutable; revise the derived structured knowledge without rewriting history
- **Privacy:** choose an explicitly approved local/private embedding model vs. hosted embeddings before processing sensitive thoughts. Model changes require reindexing; all user data must remain exportable.

Suggested implementation: SQLite or PostgreSQL with a vector extension, semantic embedding pipeline, index rebuild/versioning, duplicate handling and tests for retrieval quality. The term 'semantic database' should only be claimed after the vector layer, linking/provenance and retrieval have been implemented and verified.

## Current data caveats

Prior user conversation has supplied broad goals and planning preferences, not full task deadlines, detailed finances, all past notes, or every thought. Context records include source flags. Do not infer details or silently migrate content that hasn't been explicitly provided.
