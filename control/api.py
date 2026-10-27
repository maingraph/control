import os,secrets
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,HTMLResponse
from pathlib import Path
from . import db
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
        return {"open_tasks":db.listing("open")}
    return app
app=create_app()
