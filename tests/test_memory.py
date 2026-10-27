"""Unit tests for provenance, indexing, related suggestions and confirmation.
A deterministic mock tests database plumbing; Docker also runs a real-model smoke test.
"""
import os
import tempfile
import unittest
from unittest.mock import patch
from control import db,context,inbox,memory
from control.models import TaskCreate

class SemanticMemoryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.prev={k:os.environ.get(k) for k in ("CONTROL_DB_PATH","CONTROL_CONTEXT_SEED")}
        os.environ["CONTROL_DB_PATH"]=os.path.join(self.folder.name,"memory.sqlite3")
        os.environ["CONTROL_CONTEXT_SEED"]="{}"
        db.init();context.ensure();inbox.init();memory.init()
    def tearDown(self):
        for k,v in self.prev.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        self.folder.cleanup()

    @staticmethod
    def mock_embed(texts):
        import math
        output=[]
        for text in texts:
            lower=text.lower()
            job=sum(w in lower for w in ("job","application","cv","work","employment","resume","delay"))
            guitar=sum(w in lower for w in ("guitar","chord","practice","music"))
            v=[float(job)+.2,float(guitar)+.2,.2]
            norm=math.sqrt(sum(x*x for x in v))
            output.append([x/norm for x in v])
        return output

    def test_embedding_retrieval_provenance_and_graph(self):
        a=inbox.record(inbox.CaptureInput(text="I keep delaying job applications",source="mobile"))
        b=inbox.record(inbox.CaptureInput(text="Practice guitar chords",source="mobile"))
        task=db.create(TaskCreate(title="Prepare job application",project="Job Search"))
        context.set_context("goal_test_job","Seek stable employment")
        with patch.object(memory,"embed",side_effect=self.mock_embed):
            result=memory.search("I cannot begin my job applications",limit=5)
            self.assertEqual(result["model"],memory.MODEL)
            self.assertEqual(result["index"]["remaining"],0)
            self.assertEqual(result["matches"][0]["kind"] in ("capture","task","goal"),True)
            self.assertTrue(any(r["id"]=="capture:"+a["id"] for r in result["matches"]))
            self.assertTrue(any(r["id"]=="capture:"+b["id"] for r in result["matches"]))
            relation=memory.related("capture:"+a["id"],limit=3,threshold=0.3,propose=True)
            self.assertGreater(len(relation["candidates"]),0)
            suggestions=memory.links("suggested")
            self.assertTrue(suggestions)
            self.assertTrue(all(x["status"]=="suggested" for x in suggestions))
            accepted=memory.decide_link(suggestions[0]["id"],memory.LinkDecision(status="confirmed"))
            self.assertEqual(accepted["status"],"confirmed")
        # A raw note must never change through derived knowledge.
        self.assertEqual(next(x["original_text"] for x in inbox.listing("all") if x["id"]==a["id"]),"I keep delaying job applications")
        self.assertEqual(memory.status()["embeddings"],4)

    def test_draft_knowledge_has_source(self):
        captured=inbox.record(inbox.CaptureInput(text="I have many ideas",source="mobile"))
        memory.sync_sources()
        knowledge=memory.add_knowledge(memory.KnowledgeInput(
            kind="obstacle",statement="Possible difficulty selecting priorities",
            source_node_id="capture:"+captured["id"],evidence="Interpretation pending review"))
        self.assertEqual(knowledge["status"],"draft")
        self.assertEqual(knowledge["source_ref"],"capture:"+captured["id"])
        with self.assertRaises(ValueError):
            memory.add_link(memory.LinkInput(source_id=knowledge["id"],target_id=knowledge["id"]))

if __name__=="__main__":unittest.main()
