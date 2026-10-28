"use strict";
/* Control dashboard: browser-only presentation of the existing private Control database.
 * Never put auth secrets, private thoughts, or access tokens in browser storage.
 */
const $=id=>document.getElementById(id);
const state={tasks:[],captures:[],context:{},month:new Date(),selected:null,timerEnd:null,timerHandle:null,unlocked:false};
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
 $("today-long").textContent=dateLong(d)+" · One step at a time.";
}
function taskDue(task){if(!task.due_at)return null;const date=new Date(task.due_at);return Number.isNaN(+date)?null:date;}
function taskPriority(task){return task.priority==="high"?0:task.priority==="medium"?1:2;}
function taskSort(a,b){
 const da=taskDue(a),db=taskDue(b);
 if(da&&db)return +da-+db||taskPriority(a)-taskPriority(b);
 if(da)return -1;
 if(db)return 1;
 return taskPriority(a)-taskPriority(b)||(a.created_at||"").localeCompare(b.created_at||"");
}
function dueLabel(task){
 const due=taskDue(task);if(!due)return "No deadline";
 const delta=+due-Date.now();
 const label=delta<0?"Overdue":dayKey(due)===dayKey(now())?"Today":dayKey(due)===dayKey(new Date(Date.now()+86400000))?"Tomorrow":dateShort(due);
 return label+" · "+hhmm(due);
}
function taskCard(task,highlight=false){
 const row=element("div","task-card"+(highlight?" warning":""));
 const complete=element("button","done-button","✓");
 complete.type="button";complete.title="Mark task done";complete.setAttribute("aria-label","Mark "+task.title+" complete");
 complete.addEventListener("click",async()=>{
  complete.disabled=true;
  try{await api("/mobile/tasks/"+encodeURIComponent(task.id),{method:"PATCH",body:JSON.stringify({status:"done"})});await loadDashboard();message("Task marked complete.");}
  catch(e){complete.disabled=false;message("Couldn't complete task: "+errorMessage(e));}
 });
 const info=element("div","task-info");
 info.append(element("span","task-title",task.title));
 info.append(element("small","task-meta",[task.project||"Unsorted",dueLabel(task)].join(" · ")));
 const due=taskDue(task);
 const tag=element("span","pill"+(due&&(+due-Date.now())<0?" alert":""),due?"Due":(task.priority==="high"?"High":task.priority==="low"?"Low":"Normal"));
 row.append(complete,info,tag);return row;
}
function renderTaskGroup(target,tasks,empty,highlight=false){
 const parent=$(target);parent.replaceChildren();
 if(!tasks.length){parent.append(element("p","empty",empty));return;}
 tasks.forEach(t=>parent.append(taskCard(t,highlight)));
}
function renderTasks(){
 const current=Date.now();
 const ordered=[...state.tasks].sort(taskSort);
 const urgent=ordered.filter(t=>{const d=taskDue(t);return d&&(d.getTime()-current)<=86400000;});
 const undatedHigh=ordered.filter(t=>!taskDue(t)&&t.priority==="high");
 const alternatives=ordered.filter(t=>!taskDue(t));
 const suggested=undatedHigh.length?undatedHigh:alternatives.slice(0,1);
 $("stat-due").textContent=urgent.length;
 $("stat-open").textContent=state.tasks.length;
 $("urgent-count").textContent=urgent.length+" items";
 $("undated-count").textContent=suggested.length+" items";
 $("undated-heading").textContent=undatedHigh.length?"Important, no set time":"Choose one when ready";
 display("urgent-section",urgent.length>0);
 display("undated-section",suggested.length>0);
 renderTaskGroup("urgent-list",urgent.slice(0,4),"",true);
 renderTaskGroup("undated-list",suggested.slice(0,3),"",false);
 renderTaskGroup("all-task-list",ordered,"Nothing left to do. You're up to date.");
 if(!urgent.length&&!suggested.length){
   $("urgent-section").classList.remove("hidden");
   renderTaskGroup("urgent-list",[],"No immediate commitments. Your day is yours to plan.");
 }
 const select=$("focus-task");const previous=select.value;select.replaceChildren();
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
function renderCalendar(){
 const root=$("calendar-grid");root.replaceChildren();
 const base=new Date(state.month.getFullYear(),state.month.getMonth(),1);
 const year=base.getFullYear(),month=base.getMonth();
 $("calendar-month").textContent=base.toLocaleDateString(undefined,{month:"long",year:"numeric"});
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
 const outcomes=await Promise.allSettled([api("/mobile/tasks"),api("/mobile/inbox"),api("/mobile/context")]);
 const failures=[];
 if(outcomes[0].status==="fulfilled")state.tasks=outcomes[0].value;else failures.push("tasks");
 if(outcomes[1].status==="fulfilled")state.captures=outcomes[1].value;else failures.push("inbox");
 if(outcomes[2].status==="fulfilled")state.context=outcomes[2].value.records||{};else failures.push("context");
 renderTasks();renderThoughts();renderCalendar();renderGoals();renderAnalyses();restoreDayPlan();
 message(failures.length?"Some Control data is temporarily unavailable: "+failures.join(", "):"");
}
function setTheme(theme){
 document.documentElement.dataset.theme=theme;
 $("theme-toggle").textContent=theme==="dark"?"☼":"◐";
 $("theme-toggle").setAttribute("aria-label",theme==="dark"?"Switch to light mode":"Switch to dark mode");
 try{localStorage.setItem("control_theme",theme);}catch{}
}
try{setTheme(localStorage.getItem("control_theme")==="dark"?"dark":"light");}catch{setTheme("light");}
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
