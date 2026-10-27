'use strict';
// Public edition: all progress stays in this browser's IndexedDB.
(()=>{
 const base=new URL('.',document.currentScript.src),get=async name=>{const r=await fetch(new URL(name,base));if(!r.ok)throw Error('Could not load lessons. Reload to retry.');return r.json();};
 let resources;
 function load(){return resources||(resources=Promise.all([get('lessons.json'),get('catalog.json')]).catch(e=>{resources=null;throw e;}));}
 const opened=new Promise((resolve,reject)=>{const r=indexedDB.open('maths-universe-public-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('save');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Browser storage unavailable. Allow site storage to save your progress.'));});
 const fresh=()=>({stars:0,settings:{auto:true,per_correct:1},runs:{},active:null,history:[],activity_audit:[],adjustments:[],receipts:[]});
 const copy=x=>structuredClone(x),fail=message=>{const e=Error(message);e.status=409;throw e;},uid=()=>crypto.randomUUID();
 function instance(){const order=[0,1,2,3];for(let i=3;i>0;i--){const j=crypto.getRandomValues(new Uint32Array(1))[0]%(i+1);[order[i],order[j]]=[order[j],order[i]];}return {id:uid(),order,status:'open',feedback:null};}
 function output(s,bank,meta){
  const progress={};for(const [tid,r] of Object.entries(s.runs)){if(r.status!=='complete')continue;const current=r.version===meta.get(tid)?.version;progress[tid]={practice_complete:current,activity_verified:current&&r.observed,complete:current&&(!bank.get(tid).parent_activity||r.observed),earlier_completion:!current};}
  const r=s.runs[s.active];let active=null;
  if(r&&r.version===meta.get(r.topic)?.version){const l=bank.get(r.topic),m=meta.get(r.topic);active={id:r.id,topic_id:r.topic,title:m.title,domain:m.domain,index:r.index,total:3,status:r.status,parent_activity:l.parent_activity,problem:null};if(r.status!=='complete'){const p=r.problem,q=l.questions[r.index],terminal=p.status!=='open';active.problem={id:p.id,prompt:q.prompt,choices:p.order.map(i=>q.choices[i]),visual:q.visual,status:p.status,feedback:p.feedback,correct:terminal?p.order.indexOf(q.correct):null,rationale:terminal?q.rationale:null};}}
  return {stars:s.stars,settings:s.settings,active,progress,notice:'Public browser edition: progress is saved only in this browser, not on a server or your other devices. Clearing site data removes it. Parent controls are device-local, not password-protected.'};
 }
 async function api(path,body){
  const [data,cat]=await load(),bank=new Map(data.lessons.map(l=>[l.topic_id,l])),meta=new Map(cat.domains.flatMap(d=>d.topics.map(t=>[t.id,{...t,domain:d.name}]))),url=new URL(path,location.origin);
  if(path==='/api/quests/catalog')return copy(cat);
  if(path.startsWith('/api/quests/lesson/')){const tid=decodeURIComponent(url.pathname.split('/').pop()),l=bank.get(tid);if(!l)fail('Unknown topic');const {questions,...lesson}=l;return {...copy(lesson),title:meta.get(tid).title,domain:meta.get(tid).domain,description:meta.get(tid).description};}
  const db=await opened;
  return new Promise((resolve,reject)=>{
   const tx=db.transaction('save',body?'readwrite':'readonly'),store=tx.objectStore('save'),req=store.get('state');let result,problem;
   tx.oncomplete=()=>resolve(copy(result));tx.onabort=()=>reject(problem||Error('Could not save progress. Check browser storage and retry.'));tx.onerror=()=>{};
   req.onsuccess=()=>{try{
    const s=req.result||fresh(),state=()=>output(s,bank,meta);
    if(!body){if(url.pathname==='/api/quests/state')result=state();else if(url.pathname==='/api/quests/history'){const before=Number(url.searchParams.get('before'))||Infinity,items=s.history.filter(h=>h.id<before).slice(-50).reverse();result={history:items,next_before:items.length===50?items.at(-1).id:null,activity_audit:s.activity_audit.slice().reverse(),control_audit:s.adjustments.slice().reverse()};}else fail('Unknown local operation');return;}
    const signature=JSON.stringify([path,body]),receipt=body.request_id&&s.receipts.find(r=>r.id===body.request_id);
    if(receipt){if(receipt.signature!==signature)fail('Request identity already used');result=state();return;}
    const r=s.runs[s.active],l=r&&bank.get(r.topic),p=r?.problem;
    const current=()=>{if(!r||r.status==='complete'||r.version!==meta.get(r.topic)?.version||p.id!==body.problem_id)fail('This question changed. Refresh your saved progress.');};
    if(path==='/api/quests/start'){
     const tid=body.topic_id;if(!bank.has(tid))fail('Unknown topic');let run=s.runs[tid];if(!run||body.replay===true||run.version!==meta.get(tid).version){run={id:uid(),topic:tid,version:meta.get(tid).version,index:0,status:'playing',problem:instance(),observed:false};s.runs[tid]=run;}s.active=tid;
    }else if(path==='/api/quests/event'){
     current();if(p.status!=='open')fail('This question is already finished');const q=l.questions[r.index];let correct=false;
     if(body.action==='answer'){if(!Number.isInteger(body.choice)||body.choice<0||body.choice>3)fail('Invalid answer');correct=p.order[body.choice]===q.correct;if(correct){p.status='correct';p.feedback=null;if(s.settings.auto)s.stars+=s.settings.per_correct;}else p.feedback='incorrect';}
     else if(body.action==='reveal')p.status='revealed';else if(body.action==='skip')p.status='skipped';else fail('Invalid action');
     s.history.push({id:s.history.length+1,topic:r.topic,slot:r.index,action:body.action,correct,created:new Date().toISOString(),problem:p.id,question:copy(q),choices:p.order.map(i=>q.choices[i]),choice:body.choice,outcome:p.status});
    }else if(path==='/api/quests/next'){
     current();if(p.status==='open')fail('Answer the question first');if(p.status==='correct'){r.index++;if(r.index===3){r.status='complete';r.problem=null;}else r.problem=instance();}else r.problem=instance();
    }else if(path==='/api/quests/verify'){
     const run=s.runs[body.topic_id],lesson=bank.get(body.topic_id);if(!run||run.status!=='complete'||run.version!==meta.get(body.topic_id)?.version||!lesson.parent_activity)fail('Complete the current digital practice first');if(!Array.isArray(body.checks)||body.checks.length!==lesson.parent_activity.checklist.length||!body.checks.every(v=>v===true)||!String(body.reason||'').trim())fail('Check each observed skill and add an observation note');if(!run.observed){run.observed=true;s.activity_audit.push({topic:body.topic_id,run:run.id,activity:copy(lesson.parent_activity),activity_reason:String(body.reason).slice(0,160),activity_at:new Date().toISOString()});}
    }else if(path==='/api/earning'){
     if(typeof body.auto!=='boolean'||!Number.isInteger(body.per_correct)||body.per_correct<0||body.per_correct>5||!String(body.reason||'').trim())fail('Enter valid settings and a reason');s.settings={auto:body.auto,per_correct:body.per_correct};s.adjustments.push({type:'settings',...body,at:new Date().toISOString()});
    }else if(path==='/api/stars'){
     if(!Number.isSafeInteger(body.delta)||Math.abs(body.delta)>10000||s.stars+body.delta<0||!String(body.reason||'').trim())fail('Enter a whole-number adjustment and reason; stars cannot be negative');s.stars+=body.delta;s.adjustments.push({type:'stars',...body,at:new Date().toISOString()});
    }else fail('Unknown local operation');
    if(body.request_id){s.receipts.push({id:body.request_id,signature});if(s.receipts.length>500)s.receipts.shift();}
    store.put(s,'state');result=state();
   }catch(e){problem=e;tx.abort();}};
  });
 }
 window.MathsPublic={api};
})();
