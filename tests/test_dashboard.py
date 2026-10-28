"""Control dashboard contract tests. No network access or personal data required."""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from control import db, inbox, context, memory
from control.api import create_app

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.previous={k:os.environ.get(k) for k in ("CONTROL_DB_PATH","CONTROL_API_KEY","CONTROL_CONTEXT_SEED")}
        os.environ.update({"CONTROL_DB_PATH":self.folder.name+"/control.sqlite3",
                           "CONTROL_API_KEY":"test_"+"K"*48,"CONTROL_CONTEXT_SEED":"{}"})
        db.init();inbox.init();context.ensure();memory.init()
        self.client=TestClient(create_app(),base_url="https://testserver")
        self.headers={"Origin":"https://testserver","X-Control-Mobile":"1"}
    def tearDown(self):
        self.client.close()
        for key,old in self.previous.items():
            if old is None:os.environ.pop(key,None)
            else:os.environ[key]=old
        self.folder.cleanup()
    def unlock(self):
        res=self.client.post("/mobile/login",json={"access_key":"test_"+"K"*48},headers=self.headers)
        self.assertEqual(res.status_code,200,res.text)
    def test_dashboard_and_legacy_quick_capture_routes(self):
        redirected=self.client.get("/",follow_redirects=False)
        self.assertEqual(redirected.status_code,307)
        self.assertEqual(redirected.headers["location"],"/app")
        dashboard=self.client.get("/app")
        self.assertEqual(dashboard.status_code,200)
        self.assertIn('id="calendar-grid"',dashboard.text)
        self.assertIn('id="urgent-list"',dashboard.text)
        self.assertIn('id="daily-plan-form"',dashboard.text)
        self.assertIn('id="ai-preview"',dashboard.text)
        self.assertEqual(dashboard.text.count('<details class="more-section"'),3)
        self.assertIn('id="plan-more"',dashboard.text)
        self.assertIn('id="thought-more"',dashboard.text)
        self.assertIn('id="insights-more"',dashboard.text)
        self.assertIn('id="thought-summary-count"',dashboard.text)
        self.assertLess(dashboard.text.index('id="attention"'),dashboard.text.index('id="calendar-panel"'))
        self.assertLess(dashboard.text.index('id="calendar-panel"'),dashboard.text.index('id="plan-more"'))
        self.assertIn("no-store",dashboard.headers.get("cache-control",""))
        self.assertIn("script-src 'self'",dashboard.headers.get("content-security-policy",""))
        self.assertEqual(self.client.get("/assets/dashboard.js").status_code,200)
        self.assertEqual(self.client.get("/assets/dashboard.css").status_code,200)
        legacy=self.client.get("/capture")
        self.assertEqual(legacy.status_code,200)
        self.assertIn('id="capture-form"',legacy.text)
        self.assertIn('href="/app"',legacy.text)
        manifest=self.client.get("/manifest.webmanifest").json()
        self.assertEqual(manifest["start_url"],"/app")
        self.assertEqual({s["url"] for s in manifest["shortcuts"]},
                         {"/capture?mode=thought","/capture?mode=task"})
    def test_save_plan_requires_session_and_cannot_overwrite_general_context(self):
        url="/mobile/context/daily_plan_20261028"
        body={"value":'{"date":"2026-10-28","task_id":null,"next_action":"Open CV","if_then":"After coffee, open CV."}'}
        self.assertEqual(self.client.put(url,json=body,headers=self.headers).status_code,401)
        self.unlock()
        forbidden=self.client.put("/mobile/context/system_purpose",json=body,headers=self.headers)
        self.assertEqual(forbidden.status_code,403)
        saved=self.client.put(url,json=body,headers=self.headers)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()["key"],"daily_plan_20261028")
        records=self.client.get("/mobile/context").json()["records"]
        self.assertEqual(records["daily_plan_20261028"]["value"],body["value"])
        self.assertEqual(self.client.put(url,json={"value":'{"next_action":""}'},headers=self.headers).status_code,422)
        self.assertEqual(self.client.put(url,json={"value":"not json"},headers=self.headers).status_code,422)
    def test_deadline_is_explicit_and_returns_to_dashboard(self):
        self.unlock()
        r=self.client.post("/mobile/tasks",headers=self.headers,json={
            "title":"Job application","priority":"high","due_at":"2026-10-29T08:30:00+03:00","project":"Employment"})
        self.assertEqual(r.status_code,201,r.text)
        self.assertIsNotNone(r.json()["due_at"])
        tasks=self.client.get("/mobile/tasks").json()
        self.assertEqual(len(tasks),1)
        self.assertEqual(tasks[0]["title"],"Job application")
        self.assertIn("2026-10-29",tasks[0]["due_at"])
        self.assertEqual(self.client.get("/mobile/inbox").json(),[])

if __name__=="__main__":unittest.main()
