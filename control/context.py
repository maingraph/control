"""Persistent, AI-readable user context. Seed values remain private in Railway variables."""
import json
import os
import re
from . import db

_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")

def _valid_key(key: str) -> str:
    if not _KEY.fullmatch(key):
        raise ValueError("Context key must be lower_snake_case, 2-80 characters")
    return key

def ensure() -> None:
    """Safe to run on every access; bootstrap never overwrites user edits."""
    raw = os.environ.get("CONTROL_CONTEXT_SEED", "{}")
    seeds = json.loads(raw)
    if not isinstance(seeds, dict):
        raise ValueError("CONTROL_CONTEXT_SEED must be a JSON object")
    with db.connect() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS context_records "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL, source TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        for key, value in seeds.items():
            _valid_key(key)
            if not isinstance(value, str) or len(value) > 20000:
                raise ValueError("Context values must be strings <= 20000 characters")
            c.execute(
                "INSERT OR IGNORE INTO context_records (key,value,source,updated_at) VALUES (?,?,?,?)",
                (key, value, "user_conversation_bootstrap", db.now()),
            )

def list_context() -> dict:
    ensure()
    with db.connect() as c:
        records = c.execute(
            "SELECT key,value,source,updated_at FROM context_records ORDER BY key"
        ).fetchall()
    return {
        "format": "control.context.v1",
        "records": {row["key"]: {"value": row["value"], "source": row["source"],
                                "updated_at": row["updated_at"]} for row in records},
    }

def set_context(key: str, value: str) -> dict:
    _valid_key(key)
    if not isinstance(value, str) or len(value) > 20000:
        raise ValueError("Context value must be text <= 20000 characters")
    ensure()
    updated_at = db.now()
    with db.connect() as c:
        c.execute(
            "INSERT INTO context_records (key,value,source,updated_at) VALUES (?,?,'user_or_assistant_edit',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, updated_at=excluded.updated_at",
            (key, value, updated_at),
        )
    return {"key": key, "value": value, "source": "user_or_assistant_edit", "updated_at": updated_at}
