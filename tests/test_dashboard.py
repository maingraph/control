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
        self.assertIn('id="hero-day-tag"',dashboard.text)
        self.assertIn('<h1>JUST<br><em>BEGIN.</em></h1>',dashboard.text)
        self.assertIn('id="day-summary"',dashboard.text)
        self.assertIn('id="overview-text"',dashboard.text)
        self.assertIn('id="overview-meta"',dashboard.text)
        self.assertIn('id="task-editor"',dashboard.text)
        self.assertIn('id="edit-task-date"',dashboard.text)
        self.assertIn('id="edit-task-zone"',dashboard.text)
        self.assertIn('class="mobile-dock"',dashboard.text)
        self.assertIn('id="urgent-section"',dashboard.text)
        self.assertIn('id="undated-section"',dashboard.text)
        responsive_css=self.client.get("/assets/dashboard.css").text
        self.assertIn("@media (max-width:620px)",responsive_css)
        self.assertIn(".dashboard-header{display:flex;flex-direction:column-reverse",responsive_css)
        self.assertIn(".mobile-dock{",responsive_css)
        self.assertIn("env(safe-area-inset-bottom",responsive_css)
        self.assertIn('background:#f3f3ef;color:#101010',responsive_css)
        self.assertIn('@media(min-width:691px) and (max-width:870px)',responsive_css)
        dashboard_js=self.client.get("/assets/dashboard.js").text
        self.assertIn('display("urgent-section",urgent.length>0)',dashboard_js)
        self.assertIn('display("undated-section",suggested.length>0)',dashboard_js)
        self.assertIn('control_theme_studio',dashboard_js)
        self.assertIn('function renderOverview()',dashboard_js)
        self.assertIn('function openTaskEditor(task)',dashboard_js)
        self.assertIn('overviewIsFresh(data)',dashboard_js)
        self.assertIn('source_updated_at!==task.updated_at',dashboard_js)
        self.assertIn('?"light":"dark"',dashboard_js)
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

    def test_raw_task_keeps_original_until_confirmed_date(self):
        self.unlock()
        task=self.client.post("/mobile/tasks",headers=self.headers,json={
            "title":"Gamedev interview at 13","priority":"medium"}).json()
        self.assertIsNone(task["due_at"])
        self.assertEqual(task["title"],"Gamedev interview at 13")
        from control import context as context_store
        import json
        context_store.set_context("ai_task_"+task["id"].replace("-",""),json.dumps({
            "status":"draft","source_task_id":task["id"],
            "source_updated_at":task["updated_at"],
            "proposed_title":"Attend game-development interview",
            "proposed_project":None,"proposed_priority":"medium",
            "suggested_due_at":None,
            "clarification_question":"Which day is the 13:00 interview?",
            "reason":"Time is supplied but date is not"
        }))
        # AI draft does not silently change a committed task or calendar date.
        before=self.client.get("/mobile/tasks").json()[0]
        self.assertEqual(before["title"],"Gamedev interview at 13")
        self.assertIsNone(before["due_at"])
        edited=self.client.patch("/mobile/tasks/"+task["id"],headers=self.headers,json={
            "title":"Attend game-development interview","priority":"medium",
            "due_at":"2026-10-29T13:00:00+03:00",
            "notes":"Original task: Gamedev interview at 13"})
        self.assertEqual(edited.status_code,200,edited.text)
        self.assertEqual(edited.json()["title"],"Attend game-development interview")
        self.assertIn("2026-10-29",edited.json()["due_at"])
        self.assertIn("Original task:",edited.json()["notes"])

if __name__=="__main__":unittest.main()
