"""Durable-event, exact capture, link safety and recurring digest tests."""
import os
import tempfile
import unittest
from unittest.mock import patch
from control import db,context,inbox,memory,automation

class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.saved={k:os.environ.get(k) for k in ("CONTROL_DB_PATH","CONTROL_CONTEXT_SEED")}
        os.environ["CONTROL_DB_PATH"]=os.path.join(self.temp.name,"control.db")
        os.environ["CONTROL_CONTEXT_SEED"]="{}"
        db.init();context.ensure();inbox.init();memory.init();automation.init()
    def tearDown(self):
        for k,v in self.saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        self.temp.cleanup()

    def test_event_queue_saves_exact_text_and_generates_review_card(self):
        first=inbox.record(inbox.CaptureInput(text="  I keep putting off applications.\n",source="mobile"))
        second=inbox.record(inbox.CaptureInput(text="I feel unable to start the job search",source="mobile"))
        self.assertEqual(first["original_text"],"  I keep putting off applications.\n")
        self.assertEqual(sum(x["count"] for x in automation.status()["jobs"]),2)
        def fake_embed(texts):
            return [[1.0,0.0,0.0] for _ in texts]
        with patch.object(memory,"embed",side_effect=fake_embed):
            result=automation.run(10,False)
            self.assertEqual(result["state"],"complete",result)
            self.assertEqual(result["processed"],2)
            self.assertEqual(automation.run(10,False)["processed"],0)
        cards=[c for c in automation.cards() if c["kind"]=="capture_review"]
        self.assertEqual(len(cards),2)
        self.assertTrue(all(c["payload"]["requires_approval"] for c in cards))
        self.assertTrue(all(c["payload"]["model"]=="local_embedding_similarity" for c in cards))
        self.assertTrue(all(link["status"]=="suggested" for link in memory.links("all")))
        self.assertEqual(next(x for x in inbox.listing("all") if x["id"]==first["id"])["original_text"],first["original_text"])

    def test_daily_and_weekly_briefs_idempotent_no_new_tasks(self):
        with patch.object(memory,"embed",side_effect=lambda texts:[[1.,0.,0.] for _ in texts]):
            run=automation.run(0,True)
        self.assertCountEqual(run["briefs_created"],["daily","weekly"])
        self.assertEqual(automation.run(0,True)["briefs_created"],[])
        briefs=[x for x in automation.cards() if x["kind"] in ("daily_brief","weekly_brief")]
        self.assertEqual(len(briefs),2)
        self.assertEqual(db.listing("all"),[])
        self.assertTrue(all(c["payload"]["open_task_count"]==0 for c in briefs))

if __name__=="__main__":
    unittest.main()
