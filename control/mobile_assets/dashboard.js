"use strict";
/* Control dashboard: browser-only presentation of the existing private Control database.
 * Never put auth secrets, private thoughts, or access tokens in browser storage.
 */
const $=id=>document.getElementById(id);
const state={tasks:[],recentDone:[],captures:[],context:{},month:new Date(),selected:null,timerEnd:null,timerHandle:null,unlocked:false};
const now=()=>new Date();
function pad(x){return String(x).padStart(2,"0");}
function dayKey(value){const d=new Date(value);return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());}
function localPlanKey(){return "daily_plan_"+dayKey(now()).replaceAll("-","");}
function dateLong(d){return d.toLocaleDateString(undefined,{weekday:"long",month:"long",day:"numeric",year:"numeric"});}
function dateShort(d){return d.toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"});}
function hhmm(d){return d.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"});}
function element(tag,className,text){const el=document.createElement(tag);if(className)el.className=className;if(text!=null)el.textContent=String(text);return el;}
function errorMessage(err){return err instanceof Error?err.message:String(err);}
function message(text){$("global-status").textContent=text||"";}
function display(id,visible){$(id).classList.toggle("hidden",!visible);}
async function api(path,options={}){
 const opts={credentials:"same-origin",...options};
 if(options.method&&options.method!=="GET")
  opts.headers={"Content-Type":"application/json","X-Control-Mobile":"1",...options.headers};
 const response=await fetch(path,opts);
 let payload;
 try{payload=await response.json();}catch{payload={detail:"Unexpected server response"};}
 if(response.status===401&&path!=="/mobile/login")lockView();
 if(!response.ok)throw new Error(typeof payload.detail==="string"?payload.detail:"Control request failed ("+response.status+")");
 return payload;
}
function lockView(){state.unlocked=false;display("dashboard",false);display("locked",true);display("lock",false);}
function unlockView(){
 state.unlocked=true;
 display("dashboard",true);display("locked",false);display("lock",true);
 $("access").value="";
 renderClock();
 loadDashboard();
}
function renderClock(){
 const d=now();
 $("local-time").textContent=hhmm(d);
 $("local-zone").textContent=Intl.DateTimeFormat().resolvedOptions().timeZone||"Local";
 $("hero-day-tag").textContent=d.toLocaleDateString(undefined,{weekday:"long"}).toUpperCase()+"\n"+d.toLocaleDateString(undefined,{month:"short",day:"numeric"}).toUpperCase();
 // The headline is evaluated from live commitments, not selected at random.
 if(state.unlocked)renderHero();
}
function taskDue(task){if(!task.due_at)return null;const date=new Date(task.due_at);return Number.isNaN(+date)?null:date;}
function taskPriority(task){return task.priority==="high"?0:task.priority==="medium"?1:2;}
function taskSort(a,b){
 const diff=rankScore(b)-rankScore(a);
 if(diff)return diff;
 const ad=taskDue(a),bd=taskDue(b);
 if(ad&&bd)return +ad-+bd;
 return taskPriority(a)-taskPriority(b)||a.title.localeCompare(b.title);
}
function currentOverview(){
 const r=state.context.ai_latest_overview;
 if(!r)return null;
 try{
  const data=JSON.parse(r.value);
  if(!overviewIsFresh(data))return null;
  const stamp=Date.parse(data.generated_at_utc||"");
  if(!Number.isFinite(stamp)||stamp>Date.now()+300000||Date.now()-stamp>26*3600000)return null;
  return data;
 }catch{return null;}
}
function rawTimeHint(task){
 if(taskDue(task))return false;
 return /\b(at\s+\d{1,2}(:\d{2})?|at\s+noon|today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i.test(task.title+" "+(task.notes||""));
}
function aiRank(task){
 const data=currentOverview();
 const row=Array.isArray(data?.ranked_tasks)?data.ranked_tasks.find(x=>x.id===task.id&&x.source_updated_at===task.updated_at):null;
 if(!row||typeof row.score!=="number"||!Number.isFinite(row.score))return null;
 return {score:Math.min(100,Math.max(0,row.score)),reason:typeof row.reason==="string"?row.reason.slice(0,180):""};
}
function rankScore(task){
 const due=taskDue(task);
 let base=task.priority==="high"?48:task.priority==="medium"?29:12;
 if(due){
  const hours=(due.getTime()-Date.now())/3600000;
  if(hours<=0)base=hours>=-24?100:86;
  else if(hours<=2)base=98;
  else if(hours<=6)base=92;
  else if(hours<=24)base=84;
  else if(hours<=72)base=70;
  else if(hours<=168)base=59;
  else base=48;
 }
 const rank=aiRank(task);
 // AI may adjust focus within an urgency band; it cannot override a real imminent deadline.
 if(rank&&(!due||due.getTime()-Date.now()>24*3600000))
  base=Math.max(0,Math.min(100,base+Math.max(-14,Math.min(14,(rank.score-50)*0.28))));
 return Math.round(base);
}
function priorityTag(task){
 const score=rankScore(task);
 return score>=80?"A1":score>=55?"B1":score>=30?"B2":"C3";
}
function recentlyFinished(){
 return state.recentDone.filter(t=>t.completed_at&&Date.now()-Date.parse(t.completed_at)<48*3600000)
  .sort((a,b)=>Date.parse(b.completed_at)-Date.parse(a.completed_at));
}
function renderHero(){
 const data=currentOverview();
 const imminent=state.tasks.filter(t=>{const d=taskDue(t);return d&&d.getTime()-Date.now()<=2*3600000;}).sort(taskSort);
 const today=state.tasks.filter(t=>{const d=taskDue(t);return d&&dayKey(d)===dayKey(now());});
 const done=recentlyFinished();
 const interview=done.find(t=>/interview/i.test(t.title));
 const sorted=[...state.tasks].sort(taskSort);
 let first="PICK",second="ONE.",subtitle="One clear next step beats an endless task list.";
 if(imminent.length){first="TIME",second="TO ACT.";subtitle=imminent[0].title+" · "+dueLabel(imminent[0]);}
 else if(today.length){first="ON",second="DECK.";subtitle=today[0].title+" is coming up today.";}
 else if(interview){first="GOOD",second="PROGRESS.";subtitle="Interview marked done. Capture the important details, then move on.";}
 else if(sorted.length){first="NEXT",second="UP.";subtitle=sorted[0].title+" · One practical move.";}
 else{first="ALL",second="CLEAR.";subtitle="No open tasks. Capture what's next when you're ready.";}
 // A scheduled GPT headline is used only if it matches the exact current task snapshot.
 if(data&&data.hero&&typeof data.hero==="object"){
  const hero=data.hero;
  const safe=s=>typeof s==="string"&&s.trim().length<=20&&/^[\p{L}\p{N} .,!?'-]+$/u.test(s);
  if(safe(hero.line1)&&safe(hero.line2)){
   first=hero.line1.toUpperCase().trim();second=hero.line2.trim();
   if(typeof hero.subtitle==="string"&&hero.subtitle.length<=170)subtitle=hero.subtitle;
  }
 }
 $("hero-primary").textContent=first;
 $("hero-secondary").textContent=second;
 $("today-long").textContent=subtitle;
 const dueSoon=state.tasks.filter(t=>{const d=taskDue(t);return d&&d.getTime()-Date.now()<=86400000;}).length;
 const unconfirmed=state.tasks.filter(rawTimeHint).length;
 const parts=[dueSoon?dueSoon+" due within 24h":null,state.tasks.length+" open",unconfirmed?unconfirmed+" time"+(unconfirmed===1?"":"s")+" to confirm":null,done.length?done.length+" recently finished":null].filter(Boolean);
 $("day-summary").textContent=parts.join(" · ");
}
function dueLabel(task){
 const due=taskDue(task);if(!due)return "No deadline";
 const delta=+due-Date.now();
 const label=delta<0?"Overdue":dayKey(due)===dayKey(now())?"Today":dayKey(due)===dayKey(new Date(Date.now()+86400000))?"Tomorrow":dateShort(due);
 return label+" · "+hhmm(due);
}
function taskDraft(task){
 const record=state.context["ai_task_"+task.id.replaceAll("-","")];
 if(!record)return null;
 try{
  const draft=JSON.parse(record.value);
  if(draft.status!=="draft"||draft.source_task_id!==task.id||draft.source_updated_at!==task.updated_at)return null;
  return draft;
 }catch{return null;}
}
function signatureRows(records){
 return records.map(x=>[x.id,x.updated_at]).sort((a,b)=>a[0].localeCompare(b[0]));
}
function overviewIsFresh(data){
 if(!data||!data.source_versions)return false;
 const values=data.source_versions;
 return JSON.stringify(values.tasks)===JSON.stringify(signatureRows(state.tasks))
  &&JSON.stringify(values.captures)===JSON.stringify(signatureRows(state.captures));
}
function renderOverview(){
 const data=currentOverview();
 const all=[...state.tasks].sort(taskSort);
 const done=recentlyFinished();
 const recentlyDoneInterview=done.find(x=>/interview/i.test(x.title));
 const due=all.find(t=>{const d=taskDue(t);return d&&d.getTime()-Date.now()<=86400000;});
 const pending=all.filter(rawTimeHint);
 let fallback;
 if(due)fallback=due.title+" is the time-sensitive one. "+(all.length>1?"Keep the other tasks secondary until it's handled.":"Take the smallest next step.");
 else if(recentlyDoneInterview)fallback="The interview is marked done. Nice—while it's fresh, capture any follow-up and what you learned. "+(all.length?all[0].title+" is still open.":"");
 else if(all.length)fallback="You've got "+all.length+" open task"+(all.length===1?"":"s")+". "+all[0].title+" looks like a sensible next place to start.";
 else fallback="No active commitments to chase. Capture what's on your mind and pick a small next step when you want.";
 $("overview-meta").textContent=data?"GPT review · "+(data.generated_at_utc?dateShort(new Date(data.generated_at_utc)):"Current"):"Live snapshot · GPT update pending";
 $("overview-text").textContent=data&&typeof data.headline==="string"&&data.headline.trim()?data.headline.trim():fallback;
 let insight=data&&typeof data.insight==="string"?data.insight.trim():"";
 if(!insight&&recentlyDoneInterview)insight="A quick post-interview note can save you from having to reconstruct the conversation later.";
 $("overview-insight").textContent=insight;
 display("overview-insight",Boolean(insight));
 const action=data&&typeof data.next_step==="string"?data.next_step.trim():"";
 $("overview-next-step").textContent=action?"Try this: "+action:"";
 display("overview-next-step",Boolean(action));
 const question=data&&typeof data.clarification_question==="string"?data.clarification_question.trim():"";
 const text=question||(pending.length?"A task mentions a time but has no calendar date. Open its details to schedule it.":"");
 $("overview-question").textContent=text;
 display("overview-question",Boolean(text));
}
function openTaskEditor(task){
 const draft=taskDraft(task);
 $("edit-task-id").value=task.id;
 $("task-editor-source").textContent="Original: "+task.title;
 $("task-editor-suggestion").textContent=draft
  ?[draft.reason,draft.clarification_question].filter(Boolean).join(" · "):"";
 display("task-editor-suggestion",Boolean(draft));
 $("edit-task-title").value=draft&&typeof draft.proposed_title==="string"&&draft.proposed_title.trim()
  ?draft.proposed_title.slice(0,200):task.title;
 $("edit-task-project").value=draft&&typeof draft.proposed_project==="string"&&draft.proposed_project
  ?draft.proposed_project:(task.project||"");
 const preferred=draft&&["low","medium","high"].includes(draft.proposed_priority)?draft.proposed_priority:task.priority;
 $("edit-task-priority").value=preferred;
 const due=taskDue(task);
 $("edit-task-date").value=due?dayKey(due)+"T"+pad(due.getHours())+":"+pad(due.getMinutes()):"";
 $("edit-task-zone").value="device";
 $("task-editor-error").textContent="";
 $("task-editor").showModal();
 $("edit-task-title").focus();
}
function taskCard(task,highlight=false){
 const row=element("div","task-card"+(highlight?" warning":""));
 const complete=element("button","done-button","");
 complete.type="button";complete.title="Mark task done";complete.setAttribute("aria-label","Mark "+task.title+" complete");
 complete.addEventListener("click",async()=>{
  complete.disabled=true;
  try{await api("/mobile/tasks/"+encodeURIComponent(task.id),{method:"PATCH",body:JSON.stringify({status:"done"})});await loadDashboard();message("Task completed. Nice progress.");}
  catch(e){complete.disabled=false;message("Couldn't complete task: "+errorMessage(e));}
 });
 const info=element("div","task-info");
 const draft=taskDraft(task);
 info.append(element("span","task-title",draft&&draft.proposed_title?draft.proposed_title:task.title));
 info.append(element("small","task-meta",[task.project||"Unsorted",taskDue(task)?dueLabel(task):rawTimeHint(task)?"Time mentioned · confirm date":"Not scheduled"].join(" · ")));
 const ai=aiRank(task);
 if(ai?.reason)info.append(element("small","task-reason",ai.reason));
 if(draft?.clarification_question)info.append(element("small","task-draft-cue","Needs confirmation: "+draft.clarification_question));
 const edit=element("button","task-edit-link",draft?"Review task details":"Edit details");
 edit.type="button";edit.addEventListener("click",()=>openTaskEditor(task));info.append(edit);
 const tag=element("span","pill"+(taskDue(task)&&taskDue(task).getTime()-Date.now()<0?" alert":""),priorityTag(task));
 tag.title="Relative urgency score "+rankScore(task)+" (time, priority and optional GPT advice)";
 row.append(complete,info,tag);return row;
}
function renderTaskGroup(target,tasks,empty,highlight=false){
 const parent=$(target);parent.replaceChildren();
 if(!tasks.length){parent.append(element("p","empty",empty));return;}
 tasks.forEach(t=>parent.append(taskCard(t,highlight)));
}
function renderTasks(){
 const ordered=[...state.tasks].sort(taskSort);
 const urgent=ordered.filter(t=>{const d=taskDue(t);return d&&d.getTime()-Date.now()<=86400000;});
 const remaining=ordered.filter(t=>!urgent.some(u=>u.id===t.id));
 const topRemaining=remaining.slice(0,Math.max(0,4-Math.min(urgent.length,4)));
 $("stat-due").textContent=urgent.length;
 $("stat-open").textContent=state.tasks.length;
 $("urgent-count").textContent=urgent.length+" task"+(urgent.length===1?"":"s");
 $("undated-count").textContent=topRemaining.length+" task"+(topRemaining.length===1?"":"s");
 $("undated-heading").textContent=urgent.length?"Other priorities":"Highest-impact next steps";
 display("urgent-section",urgent.length>0);
 display("undated-section",topRemaining.length>0);
 renderTaskGroup("urgent-list",urgent.slice(0,4),"",true);
 renderTaskGroup("undated-list",topRemaining,"",false);
 renderTaskGroup("all-task-list",ordered,"Nothing left to do. You're up to date.");
 if(!ordered.length){display("urgent-section",true);renderTaskGroup("urgent-list",[],"Nothing urgent. Your next thought can go straight into Capture.");}
 const select=$("focus-task"),previous=select.value;select.replaceChildren();
 const placeholder=element("option",null,"Choose an existing task (optional)");placeholder.value="";select.append(placeholder);
 ordered.forEach(t=>{const option=element("option",null,t.title);option.value=t.id;select.append(option);});
 if(ordered.some(t=>t.id===previous))select.value=previous;
}
function renderThoughts(){
 $("stat-thoughts").textContent=state.captures.length;
 $("inbox-badge").textContent=state.captures.length;
 $("thought-summary-count").textContent=state.captures.length?"("+state.captures.length+")":"";
 const box=$("thought-list");box.replaceChildren();
 if(!state.captures.length){box.append(element("p","empty","Your inbox is clear. Capture anything now; we can decide what it means later."));return;}
 for(const item of state.captures.slice(0,4)){
  const card=element("article","thought-card");
  const preview=item.original_text.length>185?item.original_text.slice(0,185)+"…":item.original_text;
  card.append(element("p","thought-title",preview));
  const meta=element("div","thought-meta");meta.append(element("span",null,dateShort(new Date(item.created_at))),element("span",null,item.kind||"thought"));card.append(meta);
  const link=element("a",null,"Review in inbox ↗");link.href="/capture#inbox-list";card.append(link);box.append(card);
 }
 if(state.captures.length>4){box.append(element("p","helper","+"+(state.captures.length-4)+" more in your inbox"));}
}
function calendarDueFor(day){return state.tasks.filter(task=>{const due=taskDue(task);return due&&dayKey(due)===day;});}
function unplacedTimedTasks(){
 const mentionsTime=/\b(at\s+\d{1,2}(:\d{2})?|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i;
 return state.tasks.filter(t=>!taskDue(t) && ((taskDraft(t)&&taskDraft(t).clarification_question)||mentionsTime.test(t.title)));
}
function renderUnscheduled(){
 const pending=unplacedTimedTasks();
 display("calendar-unscheduled",pending.length>0);
 $("unscheduled-count").textContent=pending.length+" task"+(pending.length===1?"":"s")+" need a confirmed date";
 const list=$("unscheduled-list");list.replaceChildren();
 for(const item of pending.slice(0,8)){
  const row=element("div","unscheduled-row");
  row.append(element("span",null,item.title));
  const btn=element("button",null,"Set date");
  btn.type="button";btn.addEventListener("click",()=>openTaskEditor(item));
  row.append(btn);list.append(row);
 }
}
function renderCalendar(){
 const root=$("calendar-grid");root.replaceChildren();
 const base=new Date(state.month.getFullYear(),state.month.getMonth(),1);
 const year=base.getFullYear(),month=base.getMonth();
 $("calendar-month").textContent=base.toLocaleDateString(undefined,{month:"long",year:"numeric"});
 renderUnscheduled();
 const startOffset=(base.getDay()+6)%7;
 const totalDays=new Date(year,month+1,0).getDate();
 // Render calendar with a stable six-week grid for quick visual scanning.
 for(let i=0;i<42;i++){
  const date=new Date(year,month,1-startOffset+i);
  const key=dayKey(date);
  const b=element("button","cal-day",null);b.type="button";b.setAttribute("aria-label",dateLong(date));
  if(date.getMonth()!==month)b.classList.add("muted");
  if(key===dayKey(now()))b.classList.add("is-today");
  if(key===state.selected)b.classList.add("selected");
  b.setAttribute("aria-pressed",String(key===state.selected));
  b.append(element("span",null,date.getDate()));
  if(calendarDueFor(key).length)b.append(element("span","cal-dot"));
  b.addEventListener("click",()=>{state.selected=key;if(date.getMonth()!==state.month.getMonth())state.month=new Date(date.getFullYear(),date.getMonth(),1);renderCalendar();});
  root.append(b);
 }
 const date=state.selected?new Date(state.selected+"T12:00:00"):now();
 $("selected-date").textContent=dateShort(date).toUpperCase()+" · TASK DEADLINES";
 const agenda=$("day-agenda");agenda.replaceChildren();
 const tasks=calendarDueFor(dayKey(date)).sort(taskSort);
 if(!tasks.length){agenda.append(element("p","calendar-empty","No Control deadlines on this date."));return;}
 for(const task of tasks){
  const row=element("div","cal-agenda-row");row.append(element("span",null,task.title),element("small",null,hhmm(taskDue(task))));agenda.append(row);
 }
 if(!agenda.childNodes.length)agenda.append(element("p","calendar-empty","No Control deadlines on this date."));
}
function renderGoals(){
 const box=$("goal-chips");box.replaceChildren();
 let count=0;
 Object.entries(state.context).filter(([key])=>key.startsWith("goal_")).forEach(([key,record])=>{
  let title="";
  try{const d=JSON.parse(record.value);title=d.title||"";}catch{}
  if(!title)title=key.replace(/^goal_/,"").replaceAll("_"," ");
  if(title&&count++<6)box.append(element("span","goal-chip",title));
 });
 if(!count)box.append(element("span","goal-chip","Add goals in Control context"));
}
function renderAnalyses(){
 const records=Object.entries(state.context)
  .filter(([key])=>/^ai_analysis_[a-f0-9]{32}$/.test(key))
  .sort(([,a],[,b])=>(b.updated_at||"").localeCompare(a.updated_at||""));
 const box=$("ai-preview");box.replaceChildren();
 if(records.length){
  try{
   const item=JSON.parse(records[0][1].value);
   box.append(element("p","review-caption","LATEST DRAFT ANALYSIS"));
   const text=item.tentative_interpretation||item.observed||item.proposed_next_step||"A saved analysis is available in Control.";
   box.append(element("p","review-text",typeof text==="string"?text:JSON.stringify(text)));
   $("review-updated").textContent=dateShort(new Date(records[0][1].updated_at));
  }catch{box.append(element("p","empty","A saved analysis needs review in the full Control desk."));}
  return;
 }
 const recent=state.context.ai_latest_weekly_review;
 if(recent){
  try{const item=JSON.parse(recent.value);box.append(element("p","review-caption","LATEST WEEKLY REVIEW"));box.append(element("p","review-text",JSON.stringify(item).slice(0,500)));$("review-updated").textContent="Weekly draft available";return;}
  catch{}
 }
 box.append(element("p","empty","No saved GPT review yet. Hourly checks are configured; this panel updates when an analysis is actually written."));
 $("review-updated").textContent="Awaiting first saved review";
}
function restoreDayPlan(){
 const rec=state.context[localPlanKey()];
 if(!rec){$("plan-status").textContent="";$("tiny-step").value="";$("start-cue").value="";return;}
 try{
  const data=JSON.parse(rec.value);
  $("focus-task").value=data.task_id||"";
  $("tiny-step").value=data.next_action||"";
  $("start-cue").value=data.if_then||"";
  $("plan-status").textContent="Your start plan for today is saved.";
 }catch{$("plan-status").textContent="Today's plan needs review.";}
}
async function loadDashboard(){
 if(!state.unlocked)return;
 const outcomes=await Promise.allSettled([api("/mobile/tasks"),api("/mobile/tasks/recent"),api("/mobile/inbox"),api("/mobile/context")]);
 const failures=[];
 if(outcomes[0].status==="fulfilled")state.tasks=outcomes[0].value;else failures.push("tasks");
 if(outcomes[1].status==="fulfilled")state.recentDone=outcomes[1].value;else failures.push("recent completions");
 if(outcomes[2].status==="fulfilled")state.captures=outcomes[2].value;else failures.push("inbox");
 if(outcomes[3].status==="fulfilled")state.context=outcomes[3].value.records||{};else failures.push("context");
 renderTasks();renderThoughts();renderCalendar();renderGoals();renderAnalyses();restoreDayPlan();
 renderOverview();renderHero();
 message(failures.length?"Some Control data is temporarily unavailable: "+failures.join(", "):"");
}
function setTheme(theme){
 document.documentElement.dataset.theme=theme;
 $("theme-toggle").textContent=theme==="dark"?"☼":"◐";
 $("theme-toggle").setAttribute("aria-label",theme==="dark"?"Switch to light mode":"Switch to dark mode");
 try{localStorage.setItem("control_theme_studio",theme);}catch{}
}
try{setTheme(localStorage.getItem("control_theme_studio")==="light"?"light":"dark");}catch{setTheme("dark");}
$("theme-toggle").addEventListener("click",()=>setTheme(document.documentElement.dataset.theme==="dark"?"light":"dark"));
$("unlock-form").addEventListener("submit",async ev=>{
 ev.preventDefault();const submit=ev.currentTarget.querySelector("button");submit.disabled=true;$("login-error").textContent="";
 try{await api("/mobile/login",{method:"POST",body:JSON.stringify({access_key:$("access").value})});unlockView();}
 catch(err){$("login-error").textContent=errorMessage(err);}
 finally{submit.disabled=false;}
});
$("lock").addEventListener("click",async()=>{
 try{await api("/mobile/logout",{method:"POST",body:"{}"});}catch{}
 lockView();
});
$("calendar-prev").addEventListener("click",()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()-1,1);state.selected=dayKey(state.month);renderCalendar();});
$("calendar-next").addEventListener("click",()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()+1,1);state.selected=dayKey(state.month);renderCalendar();});
$("calendar-today").addEventListener("click",()=>{state.month=new Date(now().getFullYear(),now().getMonth(),1);state.selected=dayKey(now());renderCalendar();});
$("show-all-tasks").addEventListener("click",()=>{
 const drawer=$("all-task-drawer"),show=drawer.classList.contains("hidden");
 display("all-task-drawer",show);$("show-all-tasks").textContent=show?"Hide all tasks ↑":"See all open tasks ↗";
});
$("task-editor-close").addEventListener("click",()=>$("task-editor").close());
$("task-editor-cancel").addEventListener("click",()=>$("task-editor").close());
$("task-edit-form").addEventListener("submit",async ev=>{
 ev.preventDefault();
 const task=state.tasks.find(x=>x.id===$("edit-task-id").value);
 if(!task){$("task-editor-error").textContent="Task no longer available. Refresh Control.";return;}
 const title=$("edit-task-title").value.trim();
 if(!title){$("task-editor-error").textContent="Enter a task title.";return;}
 let due_at=null;
 const requested=$("edit-task-date").value;
 if(requested){
  const due=$("edit-task-zone").value==="moscow"
   ?new Date(requested+":00+03:00"):new Date(requested);
  if(Number.isNaN(due.getTime())){$("task-editor-error").textContent="Check the date and timezone.";return;}
  due_at=due.toISOString();
 }
 const originalNote=task.title!==title&&!task.notes.includes("Original task: "+task.title)
  ?"Original task: "+task.title:"";
 const notes=[task.notes||"",originalNote].filter(Boolean).join("\n");
 const patch={title,project:$("edit-task-project").value.trim()||null,
  priority:$("edit-task-priority").value,due_at,notes};
 const button=$("task-editor-save");button.disabled=true;$("task-editor-error").textContent="";
 try{
  await api("/mobile/tasks/"+encodeURIComponent(task.id),{method:"PATCH",body:JSON.stringify(patch)});
  $("task-editor").close();
  await loadDashboard();
  message("Task structured and saved. Confirmed deadlines now appear in your calendar.");
 }catch(err){$("task-editor-error").textContent=errorMessage(err);}
 finally{button.disabled=false;}
});
$("daily-plan-form").addEventListener("submit",async ev=>{
 ev.preventDefault();
 const step=$("tiny-step").value.trim(),cue=$("start-cue").value.trim();
 if(!step){$("plan-status").textContent="Give your first action a name before saving.";return;}
 const payload={date:dayKey(now()),task_id:$("focus-task").value||null,next_action:step,if_then:cue,time_zone:Intl.DateTimeFormat().resolvedOptions().timeZone||"device"};
 const button=ev.currentTarget.querySelector("[type=submit]");button.disabled=true;
 try{
  await api("/mobile/context/"+localPlanKey(),{method:"PUT",body:JSON.stringify({value:JSON.stringify(payload)})});
  $("plan-status").textContent="Saved. One small start is enough.";
  const updated=await api("/mobile/context");state.context=updated.records||{};
 }catch(err){$("plan-status").textContent="Not saved: "+errorMessage(err);}
 finally{button.disabled=false;}
});
function paintTimer(){
 const button=$("focus-timer");
 if(state.timerEnd===null){button.textContent="Start 5 minutes";return;}
 const seconds=Math.max(0,Math.ceil((state.timerEnd-Date.now())/1000));
 if(!seconds){stopTimer();$("plan-status").textContent="Five minutes finished. You can stop, or choose to continue.";return;}
 button.textContent="Stop · "+pad(Math.floor(seconds/60))+":"+pad(seconds%60);
}
function stopTimer(){
 if(state.timerHandle)clearInterval(state.timerHandle);
 state.timerHandle=null;state.timerEnd=null;paintTimer();
}
$("focus-timer").addEventListener("click",()=>{
 if(state.timerEnd!==null){stopTimer();$("plan-status").textContent="Session stopped. Starting was still progress.";return;}
 state.timerEnd=Date.now()+300000;paintTimer();state.timerHandle=setInterval(paintTimer,1000);
 $("plan-status").textContent="Stay with one small action. Timer runs only while this page remains open.";
});
function clockTick(){
 renderClock();
 if(state.selected===null){state.selected=dayKey(now());renderCalendar();}
}
state.month=new Date(now().getFullYear(),now().getMonth(),1);
state.selected=dayKey(now());
clockTick();
setInterval(renderClock,30000);
const givenMode=new URLSearchParams(location.search).get("mode");
if(givenMode==="task"||givenMode==="thought"){location.replace("/capture?mode="+givenMode);}
else{api("/mobile/me").then(unlockView).catch(lockView);}

let _lastRefresh=Date.now();
function refreshIfNeeded(){
 if(state.unlocked&&Date.now()-_lastRefresh>90000){_lastRefresh=Date.now();loadDashboard();}
}
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshIfNeeded();});
window.addEventListener("focus",refreshIfNeeded);
setInterval(()=>{if(state.unlocked&&!document.hidden){_lastRefresh=Date.now();loadDashboard();}},180000);
