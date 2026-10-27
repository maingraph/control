from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from . import db, context as ctx, inbox
from .api import create_app
from .models import TaskCreate,TaskPatch
mcp=FastMCP("Control",stateless_http=True,json_response=True,streamable_http_path="/")
@mcp.tool()
def list_control_tasks(status:str="open")->list[dict]:
    """List tasks by status open, done or all."""
    return db.listing(status)
@mcp.tool()
def get_control_task(task_id:str)->dict:
    """Get a task by ID."""
    return db.get(task_id) or {"error":"not found"}
@mcp.tool()
def create_control_task(title:str,notes:str="",due_at:str|None=None,priority:str="medium",project:str|None=None)->dict:
    """Create task. Dates must include timezone. Do not invent deadlines."""
    return db.create(TaskCreate(title=title,notes=notes,due_at=due_at,priority=priority,project=project))
@mcp.tool()
def update_control_task(task_id:str,patch:dict)->dict:
    """Update task fields such as status='done'."""
    return db.update(task_id,TaskPatch.model_validate(patch)) or {"error":"not found"}
@mcp.tool()
def read_control_context()->dict:
    """Read structured context: goals, obstacles, planning preferences and priorities."""
    return ctx.list_context()
@mcp.tool()
def update_control_context(key:str,value:str)->dict:
    """Save a user-confirmed update to a context record."""
    return ctx.set_context(key,value)
@mcp.tool()
def list_control_inbox(status:str="inbox")->list[dict]:
    """Read raw thoughts, questions and ideas for later user-approved triage."""
    return inbox.listing(status,100)
@mcp.tool()
def capture_control_thought(text:str,kind:str="thought",source:str="assistant")->dict:
    """Store the user's original thought without interpreting or rewriting it."""
    return inbox.record(inbox.CaptureInput(text=text,kind=kind,source=source))
@mcp.tool()
def review_control_capture(capture_id:str,status:str="reviewed")->dict:
    """Set an explicitly reviewed inbox entry to reviewed, archived, or inbox."""
    return inbox.update_status(capture_id,status) or {"error":"not found"}
@mcp.tool()
def export_control_data()->dict:
    """Portable export with event history."""
    return {"format":"control.full_export.v2","tasks":db.export(),"context":ctx.list_context(),"inbox":inbox.export()}
@asynccontextmanager
async def lifespan(app:FastAPI):
    db.init()
    ctx.ensure()
    inbox.init()
    async with mcp.session_manager.run():
        yield
app=create_app(lifespan=lifespan)
app.mount("/mcp",mcp.streamable_http_app())
