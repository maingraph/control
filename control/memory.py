"""Local semantic embeddings + provenance-safe memory graph.

All embedding inference runs inside Control's Railway container using FastEmbed.
Similarity is a discovery aid, not evidence of causality.
"""
from __future__ import annotations
from array import array
from functools import lru_cache
from hashlib import sha256
from math import sqrt
from typing import Literal
import os
import uuid

from pydantic import BaseModel, Field
from . import db

MODEL = "BAAI/bge-small-en-v1.5"
RELATIONS = {"related_to", "supports", "blocks", "part_of", "depends_on"}
KINDS = {"goal","project","decision","experience","obstacle","routine","preference","note"}
STATES = {"suggested","confirmed","rejected"}
SOURCE_KINDS = {"task","capture","context","knowledge"}

class KnowledgeInput(BaseModel):
    kind: Literal["goal","project","decision","experience","obstacle","routine","preference","note"]
    statement: str = Field(min_length=1,max_length=10000)
    source_node_id: str | None = None
    evidence: str = Field(default="",max_length=2000)

class LinkInput(BaseModel):
    source_id: str
    target_id: str
    relation: Literal["related_to","supports","blocks","part_of","depends_on"] = "related_to"
    rationale: str = Field(default="",max_length=2000)

class LinkDecision(BaseModel):
    status: Literal["confirmed","rejected"]

def init() -> None:
    with db.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS memory_nodes(
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            source_ref TEXT,
            status TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS memory_vectors(
            node_id TEXT PRIMARY KEY REFERENCES memory_nodes(id),
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            payload BLOB NOT NULL,
            fingerprint TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS memory_links(
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            status TEXT NOT NULL,
            rationale TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_id,target_id,relation)
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_memory_links_source ON memory_links(source_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_memory_links_target ON memory_links(target_id)")

@lru_cache(maxsize=1)
def _encoder():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL,cache_dir=os.getenv("CONTROL_EMBED_CACHE","/opt/control-embeddings"),threads=2)

def embed(texts: list[str]) -> list[list[float]]:
    if not texts:return []
    if len(texts)>32: raise ValueError("Embedding batch too large")
    values=list(_encoder().embed([text[:4000] for text in texts],batch_size=8))
    results=[]
    for vec in values:
        nums=[float(v) for v in vec]
        magnitude=sqrt(sum(v*v for v in nums))
        if not magnitude:raise RuntimeError("Embedding model produced zero vector")
        results.append([v/magnitude for v in nums])
    return results

def _save_node(c, node_id:str, kind:str,content:str,source_ref:str|None,
               status:str="source",evidence:str=""):
    fingerprint=sha256(content.encode("utf-8")).hexdigest()
    t=db.now()
    old=c.execute("SELECT fingerprint FROM memory_nodes WHERE id=?",(node_id,)).fetchone()
    if old:
        if old["fingerprint"]!=fingerprint:
            c.execute("UPDATE memory_nodes SET kind=?,content=?,source_ref=?,status=?,evidence=?,fingerprint=?,updated_at=? WHERE id=?",
                      (kind,content,source_ref,status,evidence,fingerprint,t,node_id))
        return old["fingerprint"]!=fingerprint
    c.execute("INSERT INTO memory_nodes(id,kind,content,source_ref,status,evidence,fingerprint,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (node_id,kind,content,source_ref,status,evidence,fingerprint,t,t))
    return True

def sync_sources() -> dict:
    """Copy the existing source records into search nodes, never changing source text.
    This sync is database-only, and does not require the embedding model.
    """
    init()
    changed=0
    from . import context
    context.ensure()
    with db.connect() as c:
        for row in c.execute("SELECT id,title,notes FROM tasks WHERE status != 'converted'"):
            text=row["title"] + ("\n"+row["notes"] if row["notes"] else "")
            changed+=_save_node(c,"task:"+row["id"],"task",text,"task:"+row["id"])
        for row in c.execute("SELECT id,original_text FROM captures"):
            changed+=_save_node(c,"capture:"+row["id"],"capture",row["original_text"],"capture:"+row["id"])
        for row in c.execute("SELECT key,value FROM context_records"):
            key=row["key"]
            changed+=_save_node(c,"context:"+key,"goal" if key.startswith("goal_") else "context",
                                row["value"],"context:"+key)
    return {"sources_added_or_changed":changed}

def index_pending(limit:int=100) -> dict:
    sync=sync_sources()
    limit=min(500,max(1,int(limit)))
    with db.connect() as c:
        rows=c.execute("""SELECT n.id,n.content,n.fingerprint FROM memory_nodes n
            LEFT JOIN memory_vectors v ON n.id=v.node_id
            WHERE v.node_id IS NULL OR v.fingerprint != n.fingerprint OR v.model != ?
            ORDER BY n.updated_at LIMIT ?""",(MODEL,limit)).fetchall()
    if not rows:return {**sync,"indexed":0,"remaining":0,"model":MODEL}
    total=0
    for offset in range(0,len(rows),8):
        batch=rows[offset:offset+8]
        vectors=embed([r["content"] for r in batch])
        with db.connect() as c:
            for row,vector in zip(batch,vectors):
                buff=array("f",vector).tobytes()
                c.execute("""INSERT INTO memory_vectors(node_id,model,dimensions,payload,fingerprint,indexed_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET
                    model=excluded.model,dimensions=excluded.dimensions,payload=excluded.payload,
                    fingerprint=excluded.fingerprint,indexed_at=excluded.indexed_at""",
                    (row["id"],MODEL,len(vector),buff,row["fingerprint"],db.now()))
                total+=1
    with db.connect() as c:
        remaining=c.execute("""SELECT COUNT(*) FROM memory_nodes n LEFT JOIN memory_vectors v ON n.id=v.node_id
            WHERE v.node_id IS NULL OR v.fingerprint!=n.fingerprint OR v.model!=?""",(MODEL,)).fetchone()[0]
    return {**sync,"indexed":total,"remaining":remaining,"model":MODEL}

def status() -> dict:
    init()
    with db.connect() as c:
        nodes=c.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
        vectors=c.execute("SELECT COUNT(*) FROM memory_vectors WHERE model=?",(MODEL,)).fetchone()[0]
        links=[dict(x) for x in c.execute("SELECT status,COUNT(*) AS count FROM memory_links GROUP BY status")]
    return {"model":MODEL,"model_execution":"local_cpu","nodes":nodes,"embeddings":vectors,
            "links":links,"index_mode":"exact_cosine_sqlite","scope":"source-text + user-confirmed knowledge"}

def _cosine(query:list[float],payload:bytes)->float:
    vector=array("f")
    vector.frombytes(payload)
    if len(query)!=len(vector):return -1.
    return float(sum(a*b for a,b in zip(query,vector)))

def _nearest(query_vector:list[float],limit:int,exclude_id:str|None=None) -> list[dict]:
    with db.connect() as c:
        rows=c.execute("""SELECT n.id,n.kind,n.content,n.source_ref,n.status,n.evidence,
            v.payload FROM memory_nodes n JOIN memory_vectors v ON n.id=v.node_id
            WHERE v.model=?""",(MODEL,)).fetchall()
    results=[{"id":r["id"],"kind":r["kind"],"content":r["content"],"source_ref":r["source_ref"],
              "status":r["status"],"evidence":r["evidence"],
              "similarity":round(_cosine(query_vector,r["payload"]),4)} for r in rows if r["id"]!=exclude_id]
    results.sort(key=lambda r:r["similarity"],reverse=True)
    return results[:limit]

def search(query:str,limit:int=8) -> dict:
    if not query.strip():raise ValueError("Search query cannot be empty")
    limit=min(25,max(1,int(limit)))
    index=index_pending(300)
    matches=_nearest(embed([query])[0],limit)
    return {"query":query,"model":MODEL,"index":index,"matches":matches}

def node(node_id:str)->dict|None:
    init()
    with db.connect() as c:
        r=c.execute("SELECT * FROM memory_nodes WHERE id=?",(node_id,)).fetchone()
        return dict(r) if r else None

def get_nodes(limit:int=100,kind:str|None=None)->list[dict]:
    sync_sources()
    with db.connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM memory_nodes"+(" WHERE kind=?" if kind else "")+" ORDER BY updated_at DESC LIMIT ?",
            (kind,min(500,max(1,limit))) if kind else (min(500,max(1,limit)),))]

def add_knowledge(data:KnowledgeInput)->dict:
    init()
    if data.source_node_id and not node(data.source_node_id):raise ValueError("Unknown source node")
    value=data.statement.strip()
    if not value:raise ValueError("Empty statement")
    node_id="knowledge:"+str(uuid.uuid4())
    with db.connect() as c:
        _save_node(c,node_id,data.kind,value,data.source_node_id,"draft",data.evidence)
    return node(node_id)

def _add_link(data:LinkInput,source:str="user_or_assistant_suggestion")->dict:
    if data.source_id==data.target_id:raise ValueError("Cannot link a node to itself")
    if not node(data.source_id) or not node(data.target_id):raise ValueError("Unknown node")
    src,tgt=(sorted([data.source_id,data.target_id]) if data.relation=="related_to"
             else (data.source_id,data.target_id))
    with db.connect() as c:
        existing=c.execute("SELECT * FROM memory_links WHERE source_id=? AND target_id=? AND relation=?",
                           (src,tgt,data.relation)).fetchone()
        if existing:return dict(existing)
        link_id=str(uuid.uuid4());t=db.now()
        c.execute("INSERT INTO memory_links VALUES (?,?,?,?,?,?,?,?,?)",
                  (link_id,src,tgt,data.relation,"suggested",data.rationale,source,t,t))
        return dict(c.execute("SELECT * FROM memory_links WHERE id=?",(link_id,)).fetchone())

def add_link(data:LinkInput)->dict:
    sync_sources()
    return _add_link(data)

def decide_link(link_id:str,decision:LinkDecision)->dict|None:
    with db.connect() as c:
        r=c.execute("SELECT * FROM memory_links WHERE id=?",(link_id,)).fetchone()
        if not r:return None
        c.execute("UPDATE memory_links SET status=?,updated_at=? WHERE id=?",
                  (decision.status,db.now(),link_id))
        return dict(c.execute("SELECT * FROM memory_links WHERE id=?",(link_id,)).fetchone())

def links(status_filter:str="all")->list[dict]:
    if status_filter not in {"all"}|STATES:raise ValueError("Invalid link status")
    with db.connect() as c:
        return [dict(x) for x in c.execute(
            "SELECT * FROM memory_links"+(" WHERE status=?" if status_filter!="all" else "")+" ORDER BY created_at DESC LIMIT 500",
            (status_filter,) if status_filter!="all" else ())]

def related(node_id:str,limit:int=5,threshold:float=0.35,propose:bool=False)->dict:
    index=index_pending(300)
    item=node(node_id)
    if not item:raise ValueError("Unknown node")
    with db.connect() as c:
        vector=c.execute("SELECT payload FROM memory_vectors WHERE node_id=? AND model=?",(node_id,MODEL)).fetchone()
    if vector:
        vec=array("f");vec.frombytes(vector["payload"]);q=list(vec)
    else:q=embed([item["content"]])[0]
    candidates=[r for r in _nearest(q,min(25,max(1,limit*3)),node_id) if r["similarity"]>=threshold][:limit]
    if propose:
        for r in candidates:
            _add_link(LinkInput(source_id=node_id,target_id=r["id"],relation="related_to",
                                rationale="Semantic similarity score "+str(r["similarity"])),
                      source="embedding_candidate_not_confirmed")
    return {"node_id":node_id,"model":MODEL,"index":index,"candidates":candidates,
            "proposed":bool(propose),"note":"Similarity is not proof of a real-life relationship."}
