"""Production-image smoke test using real local 384D embeddings, no personal data."""
import os
import tempfile
from control import db, context, inbox, memory

with tempfile.TemporaryDirectory() as temp:
    os.environ["CONTROL_DB_PATH"]=os.path.join(temp,"semantic-test.sqlite3")
    os.environ["CONTROL_CONTEXT_SEED"]="{}"
    db.init();context.ensure();inbox.init();memory.init()
    job=inbox.record(inbox.CaptureInput(text="Applying for jobs makes me feel overwhelmed and I keep postponing my resume",source="build_test"))
    guitar=inbox.record(inbox.CaptureInput(text="I love learning guitar chords and practicing music",source="build_test"))
    context.set_context("goal_job","Find employment, prepare a CV and submit job applications")
    result=memory.search("I keep delaying job applications even though I need work",limit=8)
    scores={r["id"]:r["similarity"] for r in result["matches"]}
    assert scores["capture:"+job["id"]]>scores["capture:"+guitar["id"]],scores
    assert result["index"]["remaining"]==0,result
    assert memory.status()["embeddings"]>=3,memory.status()
    linked=memory.related("capture:"+job["id"],limit=5,threshold=0.2,propose=True)
    assert linked["candidates"],linked
    suggested=memory.links("suggested")
    assert suggested and all(link["status"]=="suggested" for link in suggested),suggested
    approved=memory.decide_link(suggested[0]["id"],memory.LinkDecision(status="confirmed"))
    assert approved["status"]=="confirmed",approved
    assert any(link["status"]=="confirmed" for link in memory.links("all"))
    assert inbox.listing("all")[0]["original_text"] in (job["original_text"],guitar["original_text"])
    print("VERIFIED: Real 384D semantic search, ranking, persistent vectors, proposed and confirmed links")
