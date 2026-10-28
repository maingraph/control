"use strict";
const $=id=>document.getElementById(id);
let mode=new URLSearchParams(location.search).get("mode")==="task"?"task":"thought";
let saving=false;
const ago=iso=>{const d=new Date(iso);return Number.isNaN(+d)?"":d.toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});};
function show(id,yes){$(id).classList.toggle("hidden",!yes);}
function setMessage(message,isError=false){const el=$("message");el.textContent=message;el.classList.toggle("error",isError);}
async function request(url,options={}){
 const config={credentials:"same-origin",...options};
 if(options.method&&options.method!=="GET") config.headers={"Content-Type":"application/json","X-Control-Mobile":"1",...options.headers};
 const r=await fetch(url,config);let data;
 try{data=await r.json();}catch{data={detail:"Unexpected response"};}
 if(r.status===401&&url!=="/mobile/login")lockView();
 if(!r.ok)throw Error(typeof data.detail==="string"?data.detail:"Request failed ("+r.status+")");
 return data;
}
function lockView(){show("workspace",false);show("locked",true);show("lock",false);}
function workspace(){show("locked",false);show("workspace",true);show("lock",true);$("access").value="";refresh();refreshMemory();refreshProcessing();refreshAIReviews();}
function selectMode(next){
 mode=next;
 $("thought-tab").classList.toggle("active",next==="thought");
 $("task-tab").classList.toggle("active",next==="task");
 $("thought-tab").setAttribute("aria-selected",String(next==="thought"));
 $("task-tab").setAttribute("aria-selected",String(next==="task"));
 show("task-fields",next==="task");
 $("draft-label").textContent=next==="thought"?"What's on your mind?":"What's the next action?";
 $("draft").placeholder=next==="thought"?"Anything. An idea, worry, question, memory, something you've been avoiding…":"Describe the task. The first line becomes its title.";
 $("save").textContent=next==="thought"?"Save thought ↗":"Create task ↗";
 $("save-hint").textContent=next==="thought"?"Saved to your raw inbox, unchanged.":"No deadline unless you set one later.";
 setMessage("");
 const url=new URL(location.href);url.searchParams.set("mode",next);history.replaceState(null,"",url.pathname+url.search);
}
function itemNode(text,meta,actionLabel,action,secondaryLabel=null,secondaryAction=null){
 const row=document.createElement("div");row.className="item";
 const content=document.createElement("div");content.className="text";
 const body=document.createElement("p");body.textContent=text;
 const details=document.createElement("small");details.textContent=meta;
 const button=document.createElement("button");button.type="button";button.textContent=actionLabel;button.addEventListener("click",async()=>{
  button.disabled=true;
  try{await action();await refresh();}catch(e){setMessage(e.message,true);button.disabled=false;}
 });
 const actions=document.createElement('div');actions.className='actions';actions.append(button);
 if(secondaryLabel&&secondaryAction){const secondary=document.createElement('button');secondary.type='button';secondary.className='secondary';secondary.textContent=secondaryLabel;secondary.addEventListener('click',async()=>{
  if(!confirm('Move this task into the thought inbox? The original task will remain in history as converted, not completed.'))return;
  secondary.disabled=true;
  try{await secondaryAction();setMessage('Moved to your thought inbox with its original wording.');await refresh();}
  catch(e){setMessage(e.message,true);secondary.disabled=false;}
 });actions.append(secondary);}
 content.append(body,details);row.append(content,actions);return row;
}
function analysisPrompt(captureId=null){
 const target=captureId
   ? "Find the capture with ID "+captureId+" in the raw Control inbox (including archived or reviewed items if needed)."
   : "Find the pending raw captures in my Control inbox that have not been analyzed.";
 return "Use my installed Control Connector. "+target+
 " Read the original thought and existing Control goals and knowledge before drawing conclusions. "+
 "Separate direct observations from possible interpretations, identify relevant goals and one optional next action, and explain any uncertainty. "+
 "Keep my original wording. Do NOT treat possible psychological patterns as diagnoses, confirm links, create or complete tasks, or set deadlines without my consent. "+
 "Save the draft in Control with update_control_context using ai_analysis_<capture ID without hyphens> and update ai_latest_review only when appropriate. "+
 "Show me a concise result and what needs my approval.";
}
function handoffToChatGPT(captureId=null){
 const prompt=analysisPrompt(captureId);
 // Open synchronously while this is a real button click, avoiding popup blockers.
 window.open("https://chatgpt.com/","_blank","noopener,noreferrer");
 if(navigator.clipboard&&navigator.clipboard.writeText){
  navigator.clipboard.writeText(prompt).then(()=>{
   setMessage("ChatGPT opened. Paste your copied Control review request there; it does not run automatically.");
  }).catch(()=>{
   setMessage("ChatGPT opened, but clipboard copy was blocked. Use the Ask ChatGPT to digest button below to copy, or ask ChatGPT to read your Control inbox.",true);
  });
 }else{
  setMessage("Open ChatGPT and ask it to analyze your Control captures via the connector.",true);
 }
}
$("analyze-inbox").addEventListener("click",()=>handoffToChatGPT());

async function refresh(){
 try{
  const [inbox,tasks]=await Promise.all([request("/mobile/inbox"),request("/mobile/tasks")]);
  $("inbox-count").textContent="("+inbox.length+")";$("task-count").textContent="("+tasks.length+")";
  $("inbox-list").replaceChildren();
  if(!inbox.length){const p=document.createElement("p");p.className="empty";p.textContent="Your inbox is clear. Capture anything to get started."; $("inbox-list").append(p);}
  inbox.forEach(x=>{
  const row=itemNode(x.original_text,(x.kind||"thought")+" · "+ago(x.created_at),"Reviewed",()=>request("/mobile/inbox/"+encodeURIComponent(x.id),{method:"PATCH",body:JSON.stringify({status:"reviewed"})}));
  const actions=row.querySelector(".actions");
  const ask=document.createElement("button");ask.type="button";ask.className="secondary";ask.textContent="Analyze now";
  ask.addEventListener("click",()=>handoffToChatGPT(x.id));
  actions.append(ask);$("inbox-list").append(row);
 });
  $("task-list").replaceChildren();
  if(!tasks.length){const p=document.createElement("p");p.className="empty";p.textContent="No open tasks yet."; $("task-list").append(p);}
  tasks.forEach(x=>$("task-list").append(itemNode(x.title,[x.project||"Unsorted",x.priority||"medium",x.due_at?"Due "+ago(x.due_at):"No deadline"].join(" · "),"Done",()=>request("/mobile/tasks/"+encodeURIComponent(x.id),{method:"PATCH",body:JSON.stringify({status:"done"})}),"Move to thoughts",()=>request("/mobile/tasks/"+encodeURIComponent(x.id)+"/move-to-thought",{method:"POST",body:"{}"}))));
 }catch(e){setMessage("Couldn't refresh: "+e.message,true);}
}
$("thought-tab").addEventListener("click",()=>selectMode("thought"));
$("task-tab").addEventListener("click",()=>selectMode("task"));
$("refresh").addEventListener("click",refresh);
$("unlock-form").addEventListener("submit",async event=>{
 event.preventDefault();$("login-error").textContent="";
 const submit=event.currentTarget.querySelector("button");submit.disabled=true;
 try{
  await request("/mobile/login",{method:"POST",body:JSON.stringify({access_key:$("access").value})});
  workspace();
 }catch(e){$("login-error").textContent=e.message;}
 finally{submit.disabled=false;}
});
$("lock").addEventListener("click",async()=>{try{await request("/mobile/logout",{method:"POST",body:"{}"});}catch{} lockView();});
$("capture-form").addEventListener("submit",async event=>{
 event.preventDefault();if(saving)return;
 const raw=$("draft").value;if(!raw.trim()){setMessage("Write something first.",true);return;}
 saving=true;$("save").disabled=true;setMessage("Saving…");
 try{
  if(mode==="thought")await request("/mobile/capture",{method:"POST",body:JSON.stringify({text:raw,kind:"thought",source:"galaxy_fold"})});
  else {
    const first=(raw.split("\n").find(line=>line.trim())||"").trim();
    const title=first.slice(0,200);
    const rawDeadline=$("due").value;
    let due_at=null;
    if(rawDeadline){
     const localTime=$("due-zone").value==="moscow"?new Date(rawDeadline+":00+03:00"):new Date(rawDeadline);
     if(Number.isNaN(localTime.getTime()))throw Error("Check the deadline date and time.");
     due_at=localTime.toISOString();
    }
    await request("/mobile/tasks",{method:"POST",body:JSON.stringify({title,notes:raw===first?"":raw,priority:$("priority").value,project:$("project").value.trim()||null,due_at})});
  }
  $("draft").value="";if(mode==="task")$("due").value="";setMessage(mode==="thought"?"✓ Saved as THOUGHT. Look for it in Thought inbox →":"✓ Saved as TASK. It appears in Open tasks below.");
  await refresh();await refreshProcessing();$("draft").focus();
 }catch(e){setMessage("Not saved: "+e.message,true);}
 finally{saving=false;$("save").disabled=false;}
});

async function refreshProcessing(){
 const box=$("processing-cards");if(!box)return;
 try{
  const data=await request("/mobile/automation");
  const jobCount=Object.fromEntries(data.status.jobs.map(j=>[j.state,j.count]));
  $("processing-state").textContent="Automatic local processing · "+(jobCount.pending||0)+" pending · "+(jobCount.retry||0)+" retries. No cloud AI model is called.";
  $("processing-count").textContent="("+data.cards.length+")";
  box.replaceChildren();
  if(!data.cards.length){const p=document.createElement("p");p.className="empty";p.textContent="No cards yet. Save a thought to generate a review card, or tap Process now for a planning snapshot.";box.append(p);}
  data.cards.forEach(card=>{
   const row=document.createElement("div");row.className="item processing-item";
   const inner=document.createElement("div");inner.className="text";
   const heading=document.createElement("p");heading.textContent=card.title;
   const desc=document.createElement("small");desc.textContent=card.kind.replaceAll("_"," ")+" · "+ago(card.updated_at);
   const content=document.createElement("div");content.className="card-detail";
   const payload=card.payload||{};
   if(card.kind==="capture_review"){
    const preview=document.createElement("p");preview.textContent=payload.preview||"";content.append(preview);
    const meta=document.createElement("small");meta.textContent=payload.related?.length
       ? payload.related.length+" potentially related memories; connections require review."
       : "No strong semantic neighbors found yet.";content.append(meta);
   }else{
    const counts=document.createElement("p");counts.textContent=
       (payload.open_task_count||0)+" open tasks · "+(payload.thoughts_awaiting_review||0)+" thoughts to review · "+(payload.links_awaiting_confirmation||0)+" links to decide";content.append(counts);
    if(payload.possible_focus?.length){
     const ul=document.createElement("ul");
     payload.possible_focus.forEach(task=>{const li=document.createElement("li");li.textContent=task.title;ul.append(li);});
     content.append(ul);
    }
   }
   inner.append(heading,desc,content);row.append(inner);box.append(row);
  });
 }catch(e){$("processing-state").textContent="Processing feed unavailable: "+e.message;}
}
$("process-refresh").addEventListener("click",refreshProcessing);
$("run-processing").addEventListener("click",async ()=>{
 const btn=$("run-processing");btn.disabled=true;$("processing-state").textContent="Processing pending items and generating today's overview…";
 try{const result=await request("/mobile/automation/run",{method:"POST",body:"{}"});
 $("processing-state").textContent="Processed "+result.processed+" entries. "+result.briefs_created.length+" new briefings.";
 await refreshProcessing();await refreshMemory();}
 catch(e){$("processing-state").textContent=e.message;}
 finally{btn.disabled=false;}
});

function memoryMessage(message,isError=false){
 const el=$("memory-notice");el.textContent=message;el.classList.toggle("error",isError);
}
async function refreshMemory(){
 try{
  const [state,pending]=await Promise.all([request("/mobile/memory/status"),request("/mobile/memory/links")]);
  $("vector-count").textContent="("+state.embeddings+" indexed)";
  $("link-count").textContent="("+pending.links.length+")";
  const nodes=new Map(pending.nodes.map(n=>[n.id,n]));
  const list=$("link-list");list.replaceChildren();
  if(!pending.links.length){const empty=document.createElement("p");empty.className="empty";empty.textContent="No links awaiting approval.";list.append(empty);}
  pending.links.forEach(link=>{
   const a=nodes.get(link.source_id),b=nodes.get(link.target_id);
   const aText=a?.content||link.source_id,bText=b?.content||link.target_id;
   const row=document.createElement("div");row.className="item link-item";
   const text=document.createElement("div");text.className="text";
   const title=document.createElement("p");title.textContent=aText.slice(0,160)+" ↔ "+bText.slice(0,160);
   const meta=document.createElement("small");meta.textContent=link.relation+" · "+link.source+" · unconfirmed";
   text.append(title,meta);
   const actions=document.createElement("div");actions.className="actions";
   for(const [label,status] of [["Confirm","confirmed"],["Reject","rejected"]]){
    const btn=document.createElement("button");btn.type="button";btn.textContent=label;
    btn.addEventListener("click",async()=>{
     btn.disabled=true;try{
      await request("/mobile/memory/links/"+encodeURIComponent(link.id),{method:"PATCH",body:JSON.stringify({status})});
      memoryMessage("Relationship "+status+".");await refreshMemory();
     }catch(e){memoryMessage(e.message,true);btn.disabled=false;}
    });
    actions.append(btn);
   }
   row.append(text,actions);list.append(row);
  });
 }catch(e){memoryMessage("Couldn't load memory links: "+e.message,true);}
}
$("refresh-memory").addEventListener("click",refreshMemory);
$("memory-search-form").addEventListener("submit",async event=>{
 event.preventDefault();
 const query=$("memory-query").value.trim();if(!query)return;
 const btn=$("memory-submit");btn.disabled=true;memoryMessage("Searching local semantic index…");
 try{
  const result=await request("/mobile/memory/search",{method:"POST",body:JSON.stringify({query,limit:8})});
  const list=$("memory-results");list.replaceChildren();
  $("vector-count").textContent="("+result.index.indexed+" newly indexed)";
  if(!result.matches.length){const empty=document.createElement("p");empty.className="empty";empty.textContent="No matching records yet.";list.append(empty);}
  result.matches.forEach(match=>{
   const row=itemNode(match.content,match.kind+" · similarity "+Math.round(match.similarity*100)+"% · "+match.id,
       "Suggest links",()=>request("/mobile/memory/suggest/"+encodeURIComponent(match.id),{method:"POST",body:"{}"}).then(refreshMemory));
   list.append(row);
  });
  memoryMessage("Found "+result.matches.length+" candidate matches. Similarity scores are not certainty.");
 }catch(e){memoryMessage("Search unavailable: "+e.message,true);}
 finally{btn.disabled=false;}
});


function renderAIReview(data){
 const records=data.records||{};
 const reviews=Object.entries(records).filter(([key])=>/^ai_analysis_[a-f0-9]{32}$/.test(key))
  .map(([key,record])=>{
   try{const analysis=JSON.parse(record.value);return {key,analysis,updated:record.updated_at};}
   catch{return null;}
  }).filter(Boolean).sort((a,b)=>b.updated.localeCompare(a.updated));
 const list=$("ai-review-list");list.replaceChildren();
 $("ai-review-count").textContent="("+reviews.length+")";
 if(!reviews.length){
  const placeholder=document.createElement("p");placeholder.className="empty";
  placeholder.textContent="No ChatGPT analysis saved yet. Captured thoughts remain available for scheduled review.";
  list.append(placeholder);return;
 }
 for(const {analysis,updated} of reviews.slice(0,30)){
  const row=document.createElement("article");row.className="item ai-review-item";
  const body=document.createElement("div");body.className="text";
  const heading=document.createElement("p");heading.className="ai-review-title";heading.textContent="Draft analysis · "+ago(updated);
  body.append(heading);
  const original=document.createElement("p");original.textContent=analysis.original_text||"Original thought (see inbox)";
  original.className="ai-review-original";body.append(original);
  for(const [label,value] of [["Observation",analysis.observed],["Possible interpretation",analysis.tentative_interpretation],
                              ["Suggested next step",analysis.proposed_next_step]]){
   if(!value)continue;const line=document.createElement("p");line.className="ai-review-detail";
   const strong=document.createElement("strong");strong.textContent=label+": ";
   line.append(strong,document.createTextNode(typeof value==="string"?value:JSON.stringify(value)));body.append(line);
  }
  const caveat=document.createElement("small");caveat.textContent="Not confirmed · Review before acting";body.append(caveat);
  row.append(body);list.append(row);
 }
}
async function refreshAIReviews(){
 try{
  const data=await request("/mobile/context");renderAIReview(data);
  $("ai-review-status").textContent="AI reasoning runs on a scheduled ChatGPT task, not in Railway. Manual review is required.";
 }catch(e){$("ai-review-status").textContent="Couldn't load AI reviews: "+e.message;}
}
$("ai-review-refresh").addEventListener("click",refreshAIReviews);

$("draft").addEventListener("keydown",e=>{if((e.metaKey||e.ctrlKey)&&e.key==="Enter"){$("capture-form").requestSubmit();}});
$("copy-digest").addEventListener("click",async()=>{
 const text="Use my Control Connector to read my Control context and the pending thought inbox. Help me clarify each thought without losing its original meaning, identify concrete next actions only with my agreement, and connect them to current goals. Do not invent deadlines.";
 try{await navigator.clipboard.writeText(text);setMessage("Prompt copied. Open ChatGPT and paste it.");}
 catch{setMessage("Open ChatGPT and ask it to read your Control context and inbox.",true);}
});
selectMode(mode);
request("/mobile/me").then(workspace).catch(lockView);
if("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/service-worker.js").catch(()=>{}));

if(["#memory-search-form","#ai-review-title","#processing-cards","#link-list"].includes(location.hash)){
 const advanced=document.getElementById("advanced-tools");
 if(advanced)advanced.open=true;
}
