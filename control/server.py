from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from . import db, context as ctx, inbox, memory
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
def semantic_search_control(query:str,limit:int=8)->dict:
    """Semantic similarity retrieval over Control's actual private notes, tasks and goals. Results include provenance and similarity, not inferred fact."""
    return memory.search(query,limit)
@mcp.tool()
def control_memory_status()->dict:
    """Report local embedding model, indexed nodes and reviewable relationship links."""
    return memory.status()
@mcp.tool()
def create_control_knowledge(kind:str,statement:str,source_node_id:str|None=None,evidence:str="")->dict:
    """Record a DRAFT interpretation or decision, linked to source evidence if known; do not silently claim user confirmation."""
    return memory.add_knowledge(memory.KnowledgeInput(kind=kind,statement=statement,source_node_id=source_node_id,evidence=evidence))
@mcp.tool()
def get_control_related_memory(node_id:str,limit:int=5,threshold:float=0.35,propose:bool=False)->dict:
    """Find meaningfully similar memories; proposed relationships are unconfirmed until user reviews."""
    return memory.related(node_id,limit,threshold,propose)
@mcp.tool()
def list_control_links(status:str="all")->list[dict]:
    """Read user-confirmed and AI-suggested relationships, with statuses."""
    return memory.links(status)
@mcp.tool()
def suggest_control_link(source_id:str,target_id:str,relation:str="related_to",rationale:str="")->dict:
    """Record a proposed relationship; user must confirm before treating it as fact."""
    return memory.add_link(memory.LinkInput(source_id=source_id,target_id=target_id,relation=relation,rationale=rationale))
@mcp.tool()
def decide_control_link(link_id:str,status:str)->dict:
    """Only after explicit user instruction, mark a proposed link confirmed or rejected."""
    return memory.decide_link(link_id,memory.LinkDecision(status=status)) or {"error":"not found"}
@mcp.tool()
def export_control_data()->dict:
    """Portable export with event history."""
    return {"format":"control.full_export.v3","tasks":db.export(),"context":ctx.list_context(),"inbox":inbox.export(),"memory":{"nodes":memory.get_nodes(500),"links":memory.links("all")}}
@asynccontextmanager
async def lifespan(app:FastAPI):
    db.init()
    ctx.ensure()
    inbox.init()
    memory.init()
    async with mcp.session_manager.run():
        yield
app=create_app(lifespan=lifespan)
app.mount("/mcp",mcp.streamable_http_app())
