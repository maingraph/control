"""Portable smoke tests: run python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from control import db, inbox, context, memory
from unittest.mock import patch
from control.api import create_app

class ControlMobileSmokeTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.original={k:os.environ.get(k) for k in ("CONTROL_DB_PATH","CONTROL_API_KEY","CONTROL_CONTEXT_SEED")}
        os.environ.update({
            "CONTROL_DB_PATH":os.path.join(self.folder.name,"tasks.sqlite3"),
            "CONTROL_API_KEY":"x"*48,
            "CONTROL_CONTEXT_SEED":"{}",
        })
        db.init()
        context.ensure()
        inbox.init()
        memory.init()
        self.client=TestClient(create_app(),base_url="https://testserver")
        self.browser_headers={"Origin":"https://testserver","X-Control-Mobile":"1"}
    def tearDown(self):
        self.client.close()
        for key,value in self.original.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        self.folder.cleanup()
    def unlock(self):
        r=self.client.post("/mobile/login",json={"access_key":"x"*48},headers=self.browser_headers)
        self.assertEqual(r.status_code,200,r.text)
    def test_browser_assets_and_protected_access(self):
        self.assertEqual(self.client.get("/app").status_code,200)
        self.assertEqual(self.client.get("/manifest.webmanifest").status_code,200)
        icon=self.client.get("/assets/icon-192.png")
        self.assertEqual(icon.status_code,200)
        self.assertTrue(icon.content.startswith(bytes.fromhex("89504e470d0a1a0a")))
        self.assertEqual(self.client.get("/mobile/inbox").status_code,401)
        self.assertEqual(self.client.get("/api/export/all").status_code,401)
        self.assertEqual(self.client.post("/mobile/login",json={"access_key":"wrong"},headers=self.browser_headers).status_code,401)
    def test_unlock_capture_and_export(self):
        self.unlock()
        self.assertEqual(self.client.get("/mobile/me").json(),{"authenticated":True})
        original="I want to capture this thought exactly, without rewording."
        response=self.client.post("/mobile/capture",
            headers=self.browser_headers,json={"text":original,"kind":"thought","source":"mobile"})
        self.assertEqual(response.status_code,201,response.text)
        item=response.json()
        self.assertEqual(item["original_text"],original)
        self.assertEqual(item["status"],"inbox")
        api=self.client.get("/api/context",headers={"Authorization":"Bearer "+"x"*48})
        self.assertEqual(api.status_code,200,api.text)
        self.assertEqual(api.json()["thought_inbox"][0]["id"],item["id"])
        export=self.client.get("/api/export/all",headers={"X-Control-Key":"x"*48})
        self.assertEqual(export.status_code,200)
        self.assertEqual(export.json()["inbox"]["captures"][0]["original_text"],original)
        reviewed=self.client.patch("/mobile/inbox/"+item["id"],
            headers=self.browser_headers,json={"status":"reviewed"})
        self.assertEqual(reviewed.status_code,200)
        self.assertEqual(self.client.get("/mobile/inbox").json(),[])
    def test_task_sync(self):
        self.unlock()
        response=self.client.post("/mobile/tasks",headers=self.browser_headers,
            json={"title":"Apply for one role","priority":"low","project":"Job Search"})
        self.assertEqual(response.status_code,201,response.text)
        task=response.json()
        self.assertIsNone(task["due_at"])
        self.assertEqual(len(self.client.get("/api/tasks",
            headers={"Authorization":"Bearer "+"x"*48}).json()),1)
        completed=self.client.patch("/mobile/tasks/"+task["id"],headers=self.browser_headers,
            json={"status":"done"})
        self.assertEqual(completed.status_code,200,completed.text)
        self.assertEqual(completed.json()["status"],"done")

    def test_move_task_to_thought_preserves_history(self):
        self.unlock()
        r=self.client.post("/mobile/tasks",headers=self.browser_headers,
            json={"title":"Remember to call a friend","priority":"low"})
        self.assertEqual(r.status_code,201,r.text)
        task=r.json()
        moved=self.client.post("/mobile/tasks/"+task["id"]+"/move-to-thought",
            headers=self.browser_headers,json={})
        self.assertEqual(moved.status_code,200,moved.text)
        self.assertEqual(moved.json()["original_text"],task["title"])
        self.assertEqual(moved.json()["source"],"converted_from_task")
        self.assertEqual(self.client.get("/mobile/tasks").json(),[])
        self.assertEqual(self.client.get("/mobile/inbox").json()[0]["original_text"],task["title"])
        exports=self.client.get("/api/export/all",headers={"X-Control-Key":"x"*48}).json()
        original=next(x for x in exports["tasks"]["tasks"] if x["id"]==task["id"])
        self.assertEqual(original["status"],"converted")
        self.assertIsNone(original["completed_at"])
        self.assertTrue(any(e["event"]=="converted_from_task" for e in exports["inbox"]["events"]))



    def test_mobile_semantic_search_and_link_review(self):
        self.unlock()
        first=self.client.post("/mobile/capture",headers=self.browser_headers,
            json={"text":"I keep delaying job applications"}).json()
        second=self.client.post("/mobile/capture",headers=self.browser_headers,
            json={"text":"Applying for work is hard"}).json()
        def fake_embed(texts):
            return [[1.0,0.0,0.0] for _ in texts]
        with patch.object(memory,"embed",side_effect=fake_embed):
            result=self.client.post("/mobile/memory/search",headers=self.browser_headers,
                json={"query":"Why do I postpone applying for jobs?","limit":6})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()["index"]["remaining"],0)
            self.assertGreaterEqual(len(result.json()["matches"]),2)
            proposed=self.client.post("/mobile/memory/suggest/"+first["id"].join(("capture:","")),
                headers=self.browser_headers,json={})
            self.assertEqual(proposed.status_code,200,proposed.text)
            pending=self.client.get("/mobile/memory/links")
            self.assertEqual(pending.status_code,200,pending.text)
            links=pending.json()["links"]
            self.assertTrue(links)
            confirmed=self.client.patch("/mobile/memory/links/"+links[0]["id"],
                headers=self.browser_headers,json={"status":"confirmed"})
            self.assertEqual(confirmed.status_code,200,confirmed.text)
            self.assertEqual(confirmed.json()["status"],"confirmed")

if __name__=="__main__":unittest.main()
