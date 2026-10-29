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
        # AI debug history is append-only. Older overwritten advice cannot be reconstructed.
        c.execute("""CREATE TABLE IF NOT EXISTS ai_debug_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            before_value TEXT,
            after_value TEXT NOT NULL,
            semantic_delta TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_ai_debug_events_id ON ai_debug_events(id DESC)")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_debug_graph_snapshot(
            id INTEGER PRIMARY KEY CHECK(id=1),
            snapshot TEXT NOT NULL
        )""")
        # Backfill the last known state, clearly labelled a snapshot—not invented history.
        exists=c.execute("SELECT COUNT(*) FROM ai_debug_events").fetchone()[0]
        if not exists:
            historic=c.execute("SELECT key,value,updated_at FROM context_records WHERE key LIKE 'ai_%' ORDER BY updated_at,key").fetchall()
            empty=json.dumps(_empty_graph_delta(),ensure_ascii=False)
            for item in historic:
                c.execute("INSERT INTO ai_debug_events(key,kind,created_at,before_value,after_value,semantic_delta) VALUES (?,'existing',?,NULL,?,?)",
                          (item["key"],item["updated_at"],item["value"],empty))
        if not c.execute("SELECT 1 FROM ai_debug_graph_snapshot WHERE id=1").fetchone():
            # The memory tables may not exist on the first-ever startup.
            if _has_graph(c):
                c.execute("INSERT INTO ai_debug_graph_snapshot(id,snapshot) VALUES (1,?)",
                          (json.dumps(_graph_snapshot(c)),))


def _has_graph(c) -> bool:
    return all(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone()
               for name in ("memory_nodes","memory_links"))

def _graph_snapshot(c) -> dict:
    if not _has_graph(c):
        return {"nodes":{},"links":{}}
    nodes={
        r["id"]:{"kind":r["kind"],"status":r["status"],
                 "source":r["source_ref"],"fingerprint":r["fingerprint"]}
        for r in c.execute("SELECT id,kind,status,source_ref,fingerprint FROM memory_nodes")
    }
    links={
        r["id"]:{"status":r["status"],"relation":r["relation"],
                 "source":r["source_id"],"target":r["target_id"]}
        for r in c.execute("SELECT id,status,relation,source_id,target_id FROM memory_links")
    }
    return {"nodes":nodes,"links":links}

def _empty_graph_delta() -> dict:
    return {"nodes":[],"links":[],"counts":{"nodes_added":0,"nodes_changed":0,
                                           "nodes_removed":0,"links_added":0,
                                           "links_changed":0,"links_removed":0}}

def _graph_delta(before:dict,after:dict) -> dict:
    result=_empty_graph_delta()
    for part in ("nodes","links"):
        older=before.get(part,{})
        newer=after.get(part,{})
        for identifier in sorted(set(older)|set(newer)):
            if identifier not in older: change="added"
            elif identifier not in newer: change="removed"
            elif older[identifier]!=newer[identifier]: change="changed"
            else: continue
            value=newer.get(identifier,older.get(identifier,{}))
            item={"id":identifier,"change":change}
            if part=="nodes":
                item.update({"kind":value.get("kind"),"status":value.get("status"),
                             "source":value.get("source")})
            else:
                item.update({"relation":value.get("relation"),"status":value.get("status"),
                             "source":value.get("source"),"target":value.get("target")})
            result[part].append(item)
            result["counts"][part+"_"+change]+=1
    return result

def list_ai_updates(limit:int=20,before_id:int|None=None) -> dict:
    """Read the private chronological GPT-write log, newest first, with cursor pagination."""
    if limit<1 or limit>50:raise ValueError("limit must be 1..50")
    if before_id is not None and before_id<1:raise ValueError("before_id must be positive")
    ensure()
    with db.connect() as c:
        where="WHERE id < ?" if before_id is not None else ""
        rows=c.execute(
            "SELECT * FROM ai_debug_events "+where+" ORDER BY id DESC LIMIT ?",
            ((before_id,limit+1) if before_id is not None else (limit+1,))
        ).fetchall()
    has_more=len(rows)>limit
    chosen=rows[:limit]
    return {"updates":[{
                "id":r["id"],"key":r["key"],"kind":r["kind"],
                "created_at":r["created_at"],
                "before_value":r["before_value"],"after_value":r["after_value"],
                "semantic_delta":json.loads(r["semantic_delta"])
            } for r in chosen],
            "has_more":has_more,
            "next_before_id":chosen[-1]["id"] if has_more and chosen else None}

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
        previous=c.execute("SELECT value FROM context_records WHERE key=?",(key,)).fetchone()
        old_value=previous["value"] if previous else None
        c.execute(
            "INSERT INTO context_records (key,value,source,updated_at) VALUES (?,?,'user_or_assistant_edit',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, updated_at=excluded.updated_at",
            (key, value, updated_at),
        )
        if key.startswith("ai_") and old_value!=value:
            current=_graph_snapshot(c)
            row=c.execute("SELECT snapshot FROM ai_debug_graph_snapshot WHERE id=1").fetchone()
            before=json.loads(row["snapshot"]) if row else current
            delta=_graph_delta(before,current)
            c.execute("INSERT INTO ai_debug_events(key,kind,created_at,before_value,after_value,semantic_delta) VALUES (?,?,?,?,?,?)",
                      (key,"update",updated_at,old_value,value,json.dumps(delta,ensure_ascii=False)))
            c.execute("INSERT INTO ai_debug_graph_snapshot(id,snapshot) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot",
                      (json.dumps(current,ensure_ascii=False),))
    return {"key": key, "value": value, "source": "user_or_assistant_edit", "updated_at": updated_at}
