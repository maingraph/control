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
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from . import db, inbox
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

@router.get("/mobile/inbox",dependencies=[Depends(authorized)])
def captures():
    return inbox.listing("inbox",100)

@router.post("/mobile/capture",status_code=201,dependencies=[Depends(authorized)])
def capture(body:inbox.CaptureInput):
    try:return inbox.record(body)
    except ValueError as exc:raise HTTPException(422,str(exc))

@router.patch("/mobile/inbox/{capture_id}",dependencies=[Depends(authorized)])
def review(capture_id:str,body:inbox.CaptureStatus):
    result=inbox.update_status(capture_id,body.status)
    if result is None:raise HTTPException(404,"Capture not found")
    return result

@router.get("/mobile/context",dependencies=[Depends(authorized)])
def planning_context():
    from . import context
    return context.list_context()

@router.get("/app")
def app():
    response=FileResponse(ASSETS / "index.html",media_type="text/html")
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
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
