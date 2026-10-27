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
function workspace(){show("locked",false);show("workspace",true);show("lock",true);$("access").value="";refresh();refreshMemory();}
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
async function refresh(){
 try{
  const [inbox,tasks]=await Promise.all([request("/mobile/inbox"),request("/mobile/tasks")]);
  $("inbox-count").textContent="("+inbox.length+")";$("task-count").textContent="("+tasks.length+")";
  $("inbox-list").replaceChildren();
  if(!inbox.length){const p=document.createElement("p");p.className="empty";p.textContent="Your inbox is clear. Capture anything to get started."; $("inbox-list").append(p);}
  inbox.forEach(x=>$("inbox-list").append(itemNode(x.original_text,(x.kind||"thought")+" · "+ago(x.created_at),"Reviewed",()=>request("/mobile/inbox/"+encodeURIComponent(x.id),{method:"PATCH",body:JSON.stringify({status:"reviewed"})}))));
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
    await request("/mobile/tasks",{method:"POST",body:JSON.stringify({title,notes:raw===first?"":raw,priority:$("priority").value,project:$("project").value.trim()||null})});
  }
  $("draft").value="";setMessage(mode==="thought"?"✓ Saved as THOUGHT. Look for it in Thought inbox →":"✓ Saved as TASK. It appears in Open tasks below.");
  await refresh();$("draft").focus();
 }catch(e){setMessage("Not saved: "+e.message,true);}
 finally{saving=false;$("save").disabled=false;}
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

$("draft").addEventListener("keydown",e=>{if((e.metaKey||e.ctrlKey)&&e.key==="Enter"){$("capture-form").requestSubmit();}});
$("copy-digest").addEventListener("click",async()=>{
 const text="Use my Control Connector to read my Control context and the pending thought inbox. Help me clarify each thought without losing its original meaning, identify concrete next actions only with my agreement, and connect them to current goals. Do not invent deadlines.";
 try{await navigator.clipboard.writeText(text);setMessage("Prompt copied. Open ChatGPT and paste it.");}
 catch{setMessage("Open ChatGPT and ask it to read your Control context and inbox.",true);}
});
selectMode(mode);
request("/mobile/me").then(workspace).catch(lockView);
if("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/service-worker.js").catch(()=>{}));
