import json,os,sqlite3,uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
from .models import TaskCreate,TaskPatch
def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def dbfile(): return os.environ.get("CONTROL_DB_PATH","./data/control.sqlite3")
@contextmanager
def connect():
    p=dbfile();Path(p).parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(p,timeout=10);conn.row_factory=sqlite3.Row
    try:
        yield conn;conn.commit()
    except: conn.rollback();raise
    finally:conn.close()
def init():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY,title TEXT NOT NULL,notes TEXT NOT NULL,due_at TEXT,priority TEXT NOT NULL,project TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,completed_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,action TEXT,at TEXT,changes TEXT)")
def event(c,i,action,at,data):
    c.execute("INSERT INTO events (task_id,action,at,changes) VALUES (?,?,?,?)",(i,action,at,json.dumps(data)))
def normalized(d):
    for k,v in list(d.items()):
        if isinstance(v,datetime): d[k]=v.astimezone(timezone.utc).isoformat(timespec="seconds")
    return d
def create(data:TaskCreate):
    d=normalized(data.model_dump());d.update(id=str(uuid.uuid4()),status="open",created_at=now(),updated_at=now(),completed_at=None)
    with connect() as c:
        cols=list(d);c.execute("INSERT INTO tasks ("+",".join(cols)+") VALUES ("+",".join("?" for _ in cols)+")",tuple(d.values()))
        event(c,d["id"],"created",d["created_at"],d)
    return d
def get(i):
    with connect() as c:
        v=c.execute("SELECT * FROM tasks WHERE id=?",(i,)).fetchone()
        return dict(v) if v else None
def listing(status="all"):
    if status not in ("open","done","all"):raise ValueError("status invalid")
    with connect() as c:
        sql="SELECT * FROM tasks"+(" WHERE status=?" if status!="all" else "")+" ORDER BY due_at IS NULL,due_at,created_at DESC LIMIT 500"
        return [dict(x) for x in c.execute(sql,(status,) if status!="all" else ())]
def update(i,patch:TaskPatch):
    d=normalized(patch.model_dump(exclude_unset=True))
    for k in ("title","status","priority","notes"):
        if k in d and d[k] is None:raise ValueError(k+" cannot be null")
    if not d:return get(i)
    with connect() as c:
        row=c.execute("SELECT * FROM tasks WHERE id=?",(i,)).fetchone()
        if row is None:return None
        old=dict(row);d={k:v for k,v in d.items() if old.get(k)!=v}
        if not d:return old
        t=now();d["updated_at"]=t
        if d.get("status")=="done":d["completed_at"]=t
        elif d.get("status")=="open":d["completed_at"]=None
        c.execute("UPDATE tasks SET "+",".join(k+"=?" for k in d)+" WHERE id=?",(*d.values(),i))
        event(c,i,"updated",t,d)
    return get(i)
def export():
    with connect() as c:
        tasks=[dict(x) for x in c.execute("SELECT * FROM tasks")]
        events=[dict(x) for x in c.execute("SELECT * FROM events ORDER BY id")]
    for e in events:e["changes"]=json.loads(e["changes"])
    return {"format":"control.tasks.v1","tasks":tasks,"events":events}
