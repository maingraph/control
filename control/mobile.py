"""Single-user mobile capture interface with an HttpOnly signed session.

The API secret is entered once over HTTPS, verified server-side, and is never
stored in front-end JavaScript or persistent browser storage.
"""
import hashlib
import hmac
import os
import time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from . import db, inbox, memory, automation
from .models import TaskCreate,TaskPatch

router=APIRouter()
ASSETS=Path(__file__).parent / "mobile_assets"
COOKIE="control_mobile_session"
TTL=30 * 24 * 60 * 60
FAILED:dict[str,list[float]] = {}

def configured_secret():
    secret=os.getenv("CONTROL_API_KEY","")
    if len(secret)<32:raise HTTPException(503,"Server authentication is not configured")
    return secret

def sign(exp:int,key:str):
    body="v1."+str(exp)
    signature=hmac.new(key.encode("utf-8"),body.encode("ascii"),hashlib.sha256).hexdigest()
    return body+"."+signature

def verify(cookie:str|None,key:str):
    if not cookie:return False
    try:
        version,expiry,sig=cookie.split(".")
        if version!="v1" or not expiry.isdecimal() or len(sig)!=64:return False
        if int(expiry)<time.time() or int(expiry)>time.time()+TTL+300:return False
        return hmac.compare_digest(sign(int(expiry),key),cookie)
    except (ValueError,OverflowError):return False

def require_browser_write(request:Request):
    if request.headers.get("X-Control-Mobile")!="1":
        raise HTTPException(403,"Missing same-origin request header")
    origin=request.headers.get("origin")
    if origin:
        origin_url=urlsplit(origin)
        if origin_url.scheme!="https" or origin_url.netloc.lower()!=request.headers.get("host","").lower():
            raise HTTPException(403,"Cross-origin request blocked")
    if request.headers.get("content-type","").split(";")[0].strip().lower()!="application/json":
        raise HTTPException(415,"JSON required")

def authorized(request:Request):
    if not verify(request.cookies.get(COOKIE),configured_secret()):
        raise HTTPException(401,"Unlock Control to continue")
    if request.method not in ("GET","HEAD","OPTIONS"):
        require_browser_write(request)

def login_allowed(ip:str):
    now=time.monotonic()
    recent=[t for t in FAILED.get(ip,[]) if now-t<300]
    FAILED[ip]=recent
    if len(recent)>=8:raise HTTPException(429,"Too many attempts. Try again later.")

class Login(BaseModel):
    access_key:str=Field(min_length=1,max_length=1000)

@router.post("/mobile/login")
def login(request:Request,body:Login):
    require_browser_write(request)
    ip=request.client.host if request.client else "unknown"
    login_allowed(ip)
    key=configured_secret()
    if not hmac.compare_digest(body.access_key,key):
        FAILED.setdefault(ip,[]).append(time.monotonic())
        raise HTTPException(401,"Incorrect access key")
    FAILED.pop(ip,None)
    resp=JSONResponse({"ok":True})
    resp.set_cookie(COOKIE,sign(int(time.time())+TTL,key),max_age=TTL,secure=True,httponly=True,samesite="strict",path="/mobile")
    return resp

@router.post("/mobile/logout",dependencies=[Depends(authorized)])
def logout():
    response=JSONResponse({"ok":True})
    response.delete_cookie(COOKIE,path="/mobile",secure=True,httponly=True,samesite="strict")
    return response

@router.get("/mobile/me",dependencies=[Depends(authorized)])
def me():
    return {"authenticated":True}

@router.get("/mobile/tasks",dependencies=[Depends(authorized)])
def tasks():
    return db.listing("open")

@router.get("/mobile/tasks/recent",dependencies=[Depends(authorized)])
def recent_completed_tasks():
    """Completed tasks for contextual dashboard summaries, not active work."""
    return db.listing("done")[:20]

@router.post("/mobile/tasks",status_code=201,dependencies=[Depends(authorized)])
def add_task(body:TaskCreate):
    return db.create(body)

@router.patch("/mobile/tasks/{task_id}",dependencies=[Depends(authorized)])
def modify_task(task_id:str,body:TaskPatch):
    try:
        result=db.update(task_id,body)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    if result is None:raise HTTPException(404,"Task not found")
    return result

@router.post("/mobile/tasks/{task_id}/move-to-thought",dependencies=[Depends(authorized)])
def move_to_thought(task_id:str,background_tasks:BackgroundTasks):
    try:
        result=inbox.convert_task_to_thought(task_id)
        if result:background_tasks.add_task(automation.run,3,False)
        if result is None:raise HTTPException(404,"Task not found")
        return result
    except ValueError as exc:raise HTTPException(409,str(exc))

@router.get("/mobile/inbox",dependencies=[Depends(authorized)])
def captures():
    return inbox.listing("inbox",100)

@router.post("/mobile/capture",status_code=201,dependencies=[Depends(authorized)])
def capture(body:inbox.CaptureInput,background_tasks:BackgroundTasks):
    try:
        result=inbox.record(body)
        if os.getenv("CONTROL_AUTO_PROCESS_ON_CAPTURE","false").lower()=="true":
            background_tasks.add_task(automation.run,3,False)
        return result
    except ValueError as exc:raise HTTPException(422,str(exc))

@router.patch("/mobile/inbox/{capture_id}",dependencies=[Depends(authorized)])
def review(capture_id:str,body:inbox.CaptureStatus):
    result=inbox.update_status(capture_id,body.status)
    if result is None:raise HTTPException(404,"Capture not found")
    return result


class MemorySearch(BaseModel):
    query:str=Field(min_length=1,max_length=1000)
    limit:int=Field(default=8,ge=1,le=20)

@router.get("/mobile/automation",dependencies=[Depends(authorized)])
def automation_dashboard():
    return {"status":automation.status(),"cards":automation.cards(30)}

@router.post("/mobile/automation/run",dependencies=[Depends(authorized)])
def automation_manual_run():
    return automation.run(10,True)

@router.get("/mobile/memory/status",dependencies=[Depends(authorized)])
def memory_health():return memory.status()

@router.post("/mobile/memory/search",dependencies=[Depends(authorized)])
def search_memory(body:MemorySearch):
    return memory.search(body.query,body.limit)

@router.post("/mobile/memory/suggest/{node_id}",dependencies=[Depends(authorized)])
def propose_related(node_id:str):
    try:return memory.related(node_id,limit=5,threshold=0.42,propose=True)
    except ValueError as exc:raise HTTPException(404,str(exc))

@router.get("/mobile/memory/links",dependencies=[Depends(authorized)])
def pending_links():
    return {"links":memory.links("suggested"),"nodes":memory.get_nodes(500)}

@router.patch("/mobile/memory/links/{link_id}",dependencies=[Depends(authorized)])
def review_link(link_id:str,body:memory.LinkDecision):
    return memory.decide_link(link_id,body) or (_ for _ in ()).throw(HTTPException(404,"Link not found"))

class DailyPlanValue(BaseModel):
    value: str=Field(min_length=1,max_length=1500)

@router.put("/mobile/context/{key}",dependencies=[Depends(authorized)])
def save_daily_plan(key:str,body:DailyPlanValue):
    import re,json
    if not re.fullmatch(r"daily_plan_[0-9]{8}",key):
        raise HTTPException(403,"Only daily start plans can be saved here")
    try:
        value=json.loads(body.value)
        if not isinstance(value,dict) or not value.get("next_action") or len(value["next_action"])>250 or len(value.get("if_then") or "")>250:
            raise ValueError("A small next action is required")
        if value.get("task_id") is not None and (not isinstance(value["task_id"],str) or len(value["task_id"])>60):
            raise ValueError("Invalid task ID")
    except (ValueError,TypeError,KeyError) as exc:
        raise HTTPException(422,"Invalid daily plan") from exc
    from . import context
    return context.set_context(key,body.value)

@router.get("/mobile/context",dependencies=[Depends(authorized)])
def planning_context():
    from . import context
    return context.list_context()

@router.get("/app")
def app():
    response=FileResponse(ASSETS / "dashboard.html",media_type="text/html")
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

@router.get("/capture")
def capture_page():
    response=FileResponse(ASSETS / "index.html",media_type="text/html")
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

@router.get("/assets/dashboard.css")
def dashboard_style():
    response=FileResponse(ASSETS/"dashboard.css",media_type="text/css")
    response.headers["Cache-Control"]="no-cache"
    return response

@router.get("/assets/dashboard.js")
def dashboard_script():
    response=FileResponse(ASSETS/"dashboard.js",media_type="application/javascript")
    response.headers["Cache-Control"]="no-cache"
    return response

@router.get("/assets/mobile.css")
def style():
    return FileResponse(ASSETS/"mobile.css",media_type="text/css")
@router.get("/assets/mobile.js")
def script():
    return FileResponse(ASSETS/"mobile.js",media_type="application/javascript")
@router.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ASSETS/"manifest.webmanifest",media_type="application/manifest+json")
@router.get("/service-worker.js")
def worker():
    response=FileResponse(ASSETS/"service-worker.js",media_type="application/javascript")
    response.headers["Service-Worker-Allowed"]="/"
    response.headers["Cache-Control"]="no-cache"
    return response
@router.get("/assets/control-icon.svg")
def icon():
    return FileResponse(ASSETS/"control-icon.svg",media_type="image/svg+xml")

# Raster icons make Android's PWA installer more reliable than SVG-only icons.
from functools import lru_cache
import math
import struct
import zlib

def _png_chunk(name:bytes,data:bytes)->bytes:
    return struct.pack(">I",len(data))+name+data+struct.pack(">I",zlib.crc32(name+data)&0xffffffff)

@lru_cache(maxsize=2)
def _icon_png(size:int)->bytes:
    rows=[]
    for y in range(size):
        line=bytearray(b"\x00")
        for x in range(size):
            px=(x+0.5)/size
            py=(y+0.5)/size
            # Solid midnight background; draw a simple high-contrast letter C.
            color=(17,17,17,255)
            dx=px-.50;dy=py-.50
            radius=math.hypot(dx,dy)
            angle=math.atan2(dy,dx)
            if 0.24<radius<0.32 and abs(angle)>0.63:
                color=(250,250,250,255)
            if (px-.76)**2+(py-.25)**2<0.036**2:
                color=(250,250,250,255)
            line.extend(color)
        rows.append(bytes(line))
    pixels=zlib.compress(b"".join(rows),level=9)
    header=struct.pack(">IIBBBBB",size,size,8,6,0,0,0)
    return b"\x89PNG\r\n\x1a\n"+_png_chunk(b"IHDR",header)+_png_chunk(b"IDAT",pixels)+_png_chunk(b"IEND",b"")

@router.get("/assets/icon-{size}.png")
def png_icon(size:int):
    if size not in (192,512):raise HTTPException(404,"Icon not found")
    return Response(content=_icon_png(size),media_type="image/png",headers={"Cache-Control":"public,max-age=604800"})
