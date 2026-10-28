"""Durable, conservative Control processor.

Every raw thought is queued atomically; its original text is never changed.
Local semantic suggestions are non-authoritative, and all digests are derived
deterministically from database facts. This is NOT a background ChatGPT session.
"""
from __future__ import annotations
import json
import logging
import sqlite3
import uuid
from datetime import datetime,timedelta,timezone
from . import db,memory,inbox

log=logging.getLogger("control.automation")

def init():
    with db.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS automation_jobs(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          leased_until TEXT, error TEXT,
          created_at TEXT NOT NULL, completed_at TEXT,
          UNIQUE(kind,source_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS automation_cards(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL,
          source_ref TEXT NOT NULL, title TEXT NOT NULL,
          payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(kind,source_ref))""")
        c.execute("""CREATE TABLE IF NOT EXISTS automation_runs(
          id TEXT PRIMARY KEY, mode TEXT NOT NULL, started_at TEXT NOT NULL,
          finished_at TEXT, status TEXT NOT NULL, jobs_processed INTEGER DEFAULT 0,
          message TEXT)""")

def queue_capture_in_tx(conn:sqlite3.Connection,capture_id:str):
    """Call in the original capture transaction, ensuring no lost trigger."""
    conn.execute("""INSERT OR IGNORE INTO automation_jobs(id,kind,source_id,state,created_at)
                VALUES (?,?,?,'pending',?)""",(str(uuid.uuid4()),"capture",capture_id,db.now()))

def backfill():
    """Repair jobs missing from older data or interrupted migrations."""
    init()
    with db.connect() as c:
        rows=c.execute("""SELECT id FROM captures
                 WHERE id NOT IN (SELECT source_id FROM automation_jobs WHERE kind='capture')""")
        for row in rows:queue_capture_in_tx(c,row["id"])

def _claim_job():
    now=db.now()
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("""SELECT * FROM automation_jobs
            WHERE (state IN ('pending','retry') OR (state='running' AND leased_until<?))
              AND attempts<4
            ORDER BY created_at,id LIMIT 1""",(now,)).fetchone()
        if row is None:return None
        lease=(datetime.now(timezone.utc)+timedelta(minutes=7)).isoformat(timespec="seconds")
        c.execute("""UPDATE automation_jobs SET state='running', attempts=attempts+1,
                 leased_until=?,error=NULL WHERE id=?""",(lease,row["id"]))
        return dict(row)

def _card(kind,source_ref,title,payload):
    serialized=json.dumps(payload,ensure_ascii=False,separators=(",",":"))
    t=db.now()
    with db.connect() as c:
        c.execute("""INSERT INTO automation_cards(id,kind,source_ref,title,payload,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(kind,source_ref) DO UPDATE SET title=excluded.title,
          payload=excluded.payload, updated_at=excluded.updated_at""",
          (str(uuid.uuid4()),kind,source_ref,title,serialized,t,t))

def _capture_job(source_id:str):
    with db.connect() as c:
        row=c.execute("SELECT * FROM captures WHERE id=?",(source_id,)).fetchone()
    if row is None:return
    source="capture:"+source_id
    # This indexes the new entry and finds neighbors without changing raw text.
    related=memory.related(source,limit=3,threshold=0.45,propose=False)
    matches=[{"node_id":x["id"],"kind":x["kind"],"similarity":x["similarity"],
              "excerpt":x["content"][:200]} for x in related["candidates"]]
    # Link suggestions are discoverable and explicitly unconfirmed.
    for x in matches:
        memory.add_link(memory.LinkInput(source_id=source,target_id=x["node_id"],
            relation="related_to",
            rationale="Unconfirmed semantic similarity ("+str(x["similarity"])+"); not evidence of causation."))
    _card("capture_review",source,"Thought ready to review",{
        "source_ref":source,"captured_at":row["created_at"],"kind":row["kind"],
        "preview":row["original_text"][:280],"related":matches,
        "prompt":"What does this mean to you? Is it an action, idea, feeling, or something else?",
        "requires_approval":True,
        "model":"local_embedding_similarity","not_a_diagnosis":True})

def cards(limit:int=30):
    init()
    with db.connect() as c:
        rows=c.execute("""SELECT id,kind,source_ref,title,payload,created_at,updated_at
             FROM automation_cards ORDER BY updated_at DESC LIMIT ?""",(max(1,min(100,limit)),)).fetchall()
    return [{**dict(x),"payload":json.loads(x["payload"])} for x in rows]

def _digest(mode:str):
    """Fact-bound snapshot, not made-up AI coaching or unwanted new tasks."""
    t=datetime.now(timezone.utc)
    today=t.date().isoformat()
    period=today if mode=="daily" else (t-timedelta(days=t.weekday())).date().isoformat()
    source_ref=mode+":"+period
    with db.connect() as c:
        rows=[dict(x) for x in c.execute("SELECT * FROM tasks WHERE status='open'")]
        inbox_count=c.execute("SELECT COUNT(*) FROM captures WHERE status='inbox'").fetchone()[0]
        unconfirmed=c.execute("SELECT COUNT(*) FROM memory_links WHERE status='suggested'").fetchone()[0]
        captures_week=c.execute("SELECT COUNT(*) FROM captures WHERE created_at >= ?",
                                ((t-timedelta(days=7)).isoformat(timespec="seconds"),)).fetchone()[0]
        done_week=c.execute("SELECT COUNT(*) FROM tasks WHERE completed_at>=?",
                             ((t-timedelta(days=7)).isoformat(timespec="seconds"),)).fetchone()[0]
    def order(task):
        due=task["due_at"] or "9999"
        return (0 if due!="9999" else 1,due,0 if task["priority"]=="high" else 1,task["created_at"])
    sorted_tasks=sorted(rows,key=order)
    upcoming=[]
    for task in sorted_tasks:
        if not task["due_at"]:continue
        try:
            dt=datetime.fromisoformat(task["due_at"])
            if dt.tzinfo is None:continue
            hours=(dt-t).total_seconds()/3600
            if hours<=72:
                upcoming.append({"id":task["id"],"title":task["title"],
                   "due_at":task["due_at"],"overdue":hours<0})
        except (ValueError,TypeError):continue
    payload={"period":period,"period_type":mode,"generated_at":db.now(),
        "open_task_count":len(rows),"thoughts_awaiting_review":inbox_count,
        "links_awaiting_confirmation":unconfirmed,
        "upcoming_72h":upcoming[:15],
        "possible_focus":[{"id":x["id"],"title":x["title"],"priority":x["priority"],
                           "due_at":x["due_at"]} for x in sorted_tasks[:3]],
        "unprocessed_last_7_days":captures_week,
        "completed_tasks_last_7_days":done_week,
        "caveat":"Snapshot and optional focus suggestions only. No deadlines, tasks or psychological conclusions added."}
    _card(mode+"_brief",source_ref,"Daily overview" if mode=="daily" else "Weekly review",payload)
    return payload

def _needs_digest(mode):
    t=datetime.now(timezone.utc)
    period=t.date().isoformat() if mode=="daily" else (t-timedelta(days=t.weekday())).date().isoformat()
    with db.connect() as c:
        return c.execute("SELECT id FROM automation_cards WHERE kind=? AND source_ref=?",
                         (mode+"_brief",mode+":"+period)).fetchone() is None

def run(max_jobs:int=12,make_briefs:bool=True):
    """Idempotent scheduled entrypoint; retries failed jobs and logs runs."""
    init();backfill()
    run_id=str(uuid.uuid4());started=db.now();success=0;errors=[]
    with db.connect() as c:
        c.execute("INSERT INTO automation_runs(id,mode,started_at,status) VALUES (?,?,?,'running')",
                  (run_id,"scheduled" if make_briefs else "event",started))
    for _ in range(min(50,max(0,int(max_jobs)))):
        job=_claim_job()
        if job is None:break
        try:
            if job["kind"]=="capture":_capture_job(job["source_id"])
            with db.connect() as c:
                c.execute("""UPDATE automation_jobs SET state='completed',leased_until=NULL,
                    completed_at=?,error=NULL WHERE id=?""",(db.now(),job["id"]))
            success+=1
        except Exception as e:
            log.exception("Failed processing automation job %s",job["id"])
            errors.append(type(e).__name__)
            with db.connect() as c:
                c.execute("UPDATE automation_jobs SET state=?,leased_until=NULL,error=? WHERE id=?",
                          ("retry" if job["attempts"]+1<4 else "failed",type(e).__name__,job["id"]))
    briefs=[]
    if make_briefs:
        for mode in ("daily","weekly"):
            try:
                if _needs_digest(mode):_digest(mode);briefs.append(mode)
            except Exception as e:
                errors.append("digest_"+mode+"_"+type(e).__name__)
                log.exception("Digest %s failed",mode)
    ended=db.now();state="partial" if errors else "complete"
    with db.connect() as c:
        c.execute("""UPDATE automation_runs SET finished_at=?,status=?,
                  jobs_processed=?,message=? WHERE id=?""",
                  (ended,state,success,",".join(errors)[:200],run_id))
    return {"run_id":run_id,"state":state,"processed":success,"briefs_created":briefs,
            "errors":errors,"finished_at":ended}

def status():
    init()
    with db.connect() as c:
        jobs=[dict(x) for x in c.execute("SELECT state,COUNT(*) AS count FROM automation_jobs GROUP BY state")]
        last=c.execute("SELECT * FROM automation_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        cards_count=c.execute("SELECT COUNT(*) FROM automation_cards").fetchone()[0]
    return {"jobs":jobs,"latest_run":dict(last) if last else None,"cards":cards_count,
            "processing":"local_embedding_and_rules_no_cloud_agent"}

def export():
    return {"cards":cards(100),"status":status()}
