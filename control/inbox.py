"""Durable inbox for unprocessed thoughts, observations, questions and ideas."""
import uuid
from pydantic import BaseModel, Field
from typing import Literal
from . import db

Kind=Literal["thought","idea","question","journal","observation","task_seed"]
State=Literal["inbox","reviewed","archived"]

class CaptureInput(BaseModel):
    text: str = Field(min_length=1,max_length=20000)
    kind: Kind = "thought"
    source: str = Field(default="mobile",max_length=60)

class CaptureStatus(BaseModel):
    status: State

def init():
    with db.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS captures (
            id TEXT PRIMARY KEY,
            original_text TEXT NOT NULL,
            kind TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('inbox','reviewed','archived')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_captures_status_created ON captures(status,created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS capture_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capture_id TEXT NOT NULL,
            event TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
def record(data: CaptureInput):
    text=data.text
    if not text.strip(): raise ValueError("empty capture")
    now=db.now()
    value={"id":str(uuid.uuid4()),"original_text":text,"kind":data.kind,
           "source":data.source,"status":"inbox","created_at":now,"updated_at":now}
    with db.connect() as c:
        c.execute("INSERT INTO captures(id,original_text,kind,source,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",tuple(value.values()))
        c.execute("INSERT INTO capture_events(capture_id,event,timestamp,payload) VALUES (?,?,?,?)",(value["id"],"created",now,""))
        from . import automation
        automation.init()
        automation.queue_capture_in_tx(c,value["id"])
    return value
def listing(status:State|Literal["all"]="inbox",limit:int=100):
    if status not in ("inbox","reviewed","archived","all"):raise ValueError("invalid inbox status")
    limit=min(500,max(1,limit))
    with db.connect() as c:
        query="SELECT * FROM captures"+(" WHERE status=?" if status!="all" else "")+" ORDER BY created_at DESC LIMIT ?"
        args=(status,limit) if status!="all" else (limit,)
        return [dict(row) for row in c.execute(query,args)]
def update_status(capture_id:str,new_status:State):
    if new_status not in ("inbox","reviewed","archived"):raise ValueError("invalid status")
    with db.connect() as c:
        row=c.execute("SELECT * FROM captures WHERE id=?",(capture_id,)).fetchone()
        if not row:return None
        if row["status"]!=new_status:
            now=db.now()
            c.execute("UPDATE captures SET status=?,updated_at=? WHERE id=?",(new_status,now,capture_id))
            c.execute("INSERT INTO capture_events(capture_id,event,timestamp,payload) VALUES (?,?,?,?)",(capture_id,"status_changed",now,new_status))
        return dict(c.execute("SELECT * FROM captures WHERE id=?",(capture_id,)).fetchone())
def export():
    with db.connect() as c:
        return {"format":"control.inbox.v1","captures":[dict(r) for r in c.execute("SELECT * FROM captures ORDER BY created_at")],
                "events":[dict(r) for r in c.execute("SELECT * FROM capture_events ORDER BY id")]}

def convert_task_to_thought(task_id:str)->dict|None:
    """Atomically migrate a mistakenly categorized task without destroying its history.
    Converted tasks are no longer open, but are NOT marked completed.
    """
    init()
    with db.connect() as conn:
        row=conn.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not row:return None
        if row["status"]=="converted":
            raise ValueError("Task already converted")
        original=row["title"]+(("\n"+row["notes"]) if row["notes"] else "")
        identifier=str(uuid.uuid4()); t=db.now()
        conn.execute("INSERT INTO captures(id,original_text,kind,source,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                     (identifier,original,"thought","converted_from_task","inbox",t,t))
        import json
        provenance={"task_id":task_id,"original_task_created_at":row["created_at"],
                    "original_task_due_at":row["due_at"]}
        conn.execute("INSERT INTO capture_events(capture_id,event,timestamp,payload) VALUES (?,?,?,?)",
                     (identifier,"converted_from_task",t,json.dumps(provenance)))
        from . import automation
        automation.init()
        automation.queue_capture_in_tx(conn,identifier)
        conn.execute("UPDATE tasks SET status='converted',updated_at=? WHERE id=?",(t,task_id))
        conn.execute("INSERT INTO events(task_id,action,at,changes) VALUES (?,?,?,?)",
                     (task_id,"converted_to_thought",t,json.dumps({"capture_id":identifier,"previous_status":row["status"]})))
        return dict(conn.execute("SELECT * FROM captures WHERE id=?",(identifier,)).fetchone())
