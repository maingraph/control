"""AI update audit regression tests, including protected mobile access and graph deltas."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from control import db, context, memory
from control.api import create_app
from control.models import TaskCreate

class DebugTimelineTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.old={k:os.environ.get(k) for k in ("CONTROL_DB_PATH","CONTROL_API_KEY","CONTROL_CONTEXT_SEED")}
        os.environ.update({"CONTROL_DB_PATH":self.folder.name+"/control.sqlite3",
                           "CONTROL_API_KEY":"t"*48,"CONTROL_CONTEXT_SEED":"{}"})
        db.init();context.ensure();memory.init()
        self.client=TestClient(create_app(),base_url="https://testserver")
    def tearDown(self):
        self.client.close()
        for key,value in self.old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        self.folder.cleanup()
    def test_history_is_authenticated_and_append_only(self):
        self.assertEqual(self.client.get("/mobile/ai-updates").status_code,401)
        self.client.post("/mobile/login",json={"access_key":"t"*48},
                         headers={"Origin":"https://testserver","X-Control-Mobile":"1"})
        context.set_context("ai_latest_overview",'{"headline":"first"}')
        context.set_context("ai_latest_overview",'{"headline":"second"}')
        context.set_context("ai_latest_overview",'{"headline":"second"}')
        items=self.client.get("/mobile/ai-updates?limit=1").json()
        self.assertEqual(len(items["updates"]),1)
        self.assertEqual(items["updates"][0]["before_value"],'{"headline":"first"}')
        self.assertTrue(items["has_more"])
        older=self.client.get("/mobile/ai-updates?limit=1&before_id="+str(items["next_before_id"])).json()
        self.assertEqual(older["updates"][0]["after_value"],'{"headline":"first"}')
    def test_graph_delta_observes_changes_between_ai_writes(self):
        context.set_context("ai_latest_overview",'{"headline":"before"}')
        db.create(TaskCreate(title="A task"))
        memory.sync_sources()
        context.set_context("ai_latest_overview",'{"headline":"after"}')
        updates=context.list_ai_updates()["updates"]
        delta=updates[0]["semantic_delta"]
        self.assertGreaterEqual(delta["counts"]["nodes_added"],1)
        self.assertTrue(any(item["kind"]=="task" for item in delta["nodes"]))

if __name__=="__main__":
    unittest.main()
