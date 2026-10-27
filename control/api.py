import os,secrets
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,HTMLResponse
from pathlib import Path
from . import db, context as ctx, inbox, memory
from .mobile import router as mobile_router
from pydantic import BaseModel
class ContextValue(BaseModel):
    value: str
class MemoryQuery(BaseModel):
    query: str
    limit: int = 8
from .models import TaskCreate,TaskPatch
def create_app(lifespan=None):
    app=FastAPI(title="Control",lifespan=lifespan)
    @app.middleware("http")
    async def auth(request:Request,call_next):
        if request.url.path.startswith(("/api/","/mcp")):
            key=os.environ.get("CONTROL_API_KEY","")
            token=request.headers.get("X-Control-Key","")
            bearer=request.headers.get("Authorization","")
            if bearer.lower().startswith("bearer "):token=bearer[7:]
            if len(key)<32:return JSONResponse({"detail":"Server secret missing"},status_code=503)
            if not secrets.compare_digest(token,key):return JSONResponse({"detail":"Unauthorized"},status_code=401)
        return await call_next(request)
    @app.get("/healthz")
    def health():return {"status":"ok","service":"control-v0.1"}
    @app.get("/")
    def home():return HTMLResponse('<html><head><title>Control</title></head><body><h1>Control v0.1</h1><p>Backend online. Authenticate using the API or connect an AI client.</p></body></html>')
    @app.get("/api/tasks")
    def tasks(status:str="all"):
        try:return db.listing(status)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.get("/api/tasks/{task_id}")
    def task(task_id:str):
        return db.get(task_id) or (_ for _ in ()).throw(HTTPException(404,"Not found"))
    @app.post("/api/tasks",status_code=201)
    def create(task:TaskCreate):return db.create(task)
    @app.patch("/api/tasks/{task_id}")
    def patch(task_id:str,patch:TaskPatch):
        try:return db.update(task_id,patch) or (_ for _ in ()).throw(HTTPException(404,"Not found"))
        except ValueError as e:raise HTTPException(422,str(e))
    @app.get("/api/export")
    def export():return db.export()
    @app.get("/api/context")
    def context():
        return {"context":ctx.list_context(),"open_tasks":db.listing("open"),"thought_inbox":inbox.listing("inbox",50)}
    @app.put("/api/context/{key}")
    def edit_context(key:str,body:ContextValue):
        try:return ctx.set_context(key,body.value)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.get("/api/inbox")
    def get_inbox(status:str="inbox"):
        try:return inbox.listing(status,200)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.post("/api/inbox",status_code=201)
    def add_inbox(body:inbox.CaptureInput):
        try:return inbox.record(body)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.patch("/api/inbox/{capture_id}")
    def change_inbox(capture_id:str,body:inbox.CaptureStatus):
        return inbox.update_status(capture_id,body.status) or (_ for _ in ()).throw(HTTPException(404,"Not found"))
    @app.get("/api/memory/status")
    def memory_status():return memory.status()
    @app.post("/api/memory/reindex")
    def memory_reindex(limit:int=100):
        try:return memory.index_pending(limit)
        except RuntimeError as exc:raise HTTPException(503,"Embedding index unavailable") from exc
    @app.get("/api/memory/nodes")
    def memory_nodes(limit:int=100,kind:str|None=None):return memory.get_nodes(limit,kind)
    @app.post("/api/memory/knowledge",status_code=201)
    def create_knowledge(body:memory.KnowledgeInput):
        try:return memory.add_knowledge(body)
        except ValueError as exc:raise HTTPException(422,str(exc))
    @app.get("/api/memory/links")
    def memory_links(status:str="all"):
        try:return memory.links(status)
        except ValueError as exc:raise HTTPException(422,str(exc))
    @app.post("/api/memory/links",status_code=201)
    def add_link(body:memory.LinkInput):
        try:return memory.add_link(body)
        except ValueError as exc:raise HTTPException(422,str(exc))
    @app.patch("/api/memory/links/{link_id}")
    def decide_link(link_id:str,body:memory.LinkDecision):
        return memory.decide_link(link_id,body) or (_ for _ in ()).throw(HTTPException(404,"Link not found"))
    @app.post("/api/memory/search")
    def semantic_search(body:MemoryQuery):
        try:return memory.search(body.query,body.limit)
        except RuntimeError as exc:raise HTTPException(503,"Embedding model unavailable") from exc
    @app.get("/api/memory/related/{node_id:path}")
    def semantic_related(node_id:str,limit:int=5,threshold:float=0.35,propose:bool=False):
        try:return memory.related(node_id,limit,threshold,propose)
        except ValueError as exc:raise HTTPException(404,str(exc))
    @app.get("/api/export/all")
    def export_all():
        return {"format":"control.full_export.v2","tasks":db.export(),"context":ctx.list_context(),"inbox":inbox.export(),"memory":{"nodes":memory.get_nodes(500),"links":memory.links("all")}}
    app.include_router(mobile_router)
    return app
app=create_app()
