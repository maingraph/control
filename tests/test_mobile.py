"""Portable smoke tests: run python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from control import db, inbox, context
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

if __name__=="__main__":unittest.main()
