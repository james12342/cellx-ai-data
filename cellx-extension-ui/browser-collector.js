(() => {
 const ACTION='/ext-api/browser-collector',pending=new Map();let busy=false,stopped=false,activeJob=null;
 window.addEventListener('message',event=>{const m=event.data;if(event.source!==window||event.origin!==location.origin||m?.channel!=='cell-browser-collector-response')return;const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.ok?p.resolve(m):p.reject(Error(m.message||'Browser helper failed'));}});
 const bridge=action=>new Promise((resolve,reject)=>{const id=crypto.randomUUID();const timer=setTimeout(()=>{pending.delete(id);reject(Error('Browser helper is not connected. Choose the target page in the Chrome helper, then return here.'));},action==='next'?35000:5000);pending.set(id,{resolve,reject,timer});window.postMessage({channel:'cell-browser-collector-request',id,action},location.origin);});
 const isNode=node=>node?.action===ACTION;
 const fieldsOf=node=>String(node.integrationSettings?.fields||'').split(/[,，\n]/).map(v=>v.trim()).filter(Boolean);
 const save=()=>{saveWorkflowDraft();};
 const englishMessage=s=>String(s||'').replace(/已采集 (\d+) 页、(\d+) 条。/g,'Collected $1 page(s), $2 records. ');
 function settings(node,host){
  node.integrationSettings ||= {};host.replaceChildren(); if(node.name==='网页采集 / Web Collector')node.name='Web Collector'; if(node.testResult)node.testResult.message=englishMessage(node.testResult.message);
  const title=document.createElement('h3');title.textContent='Web Collector';
  const help=document.createElement('p');help.textContent='Choose the target page in the Chrome helper, then specify fields here. Page text is sent to your server and OpenAI; API usage is billed. Up to 5 pages and 100 records per page. Keep this page open. Background schedules are not supported.';
  const download=document.createElement('a');download.href='./browser-collector-extension.zip';download.textContent='Download Chrome helper';download.download='cell-ai-browser-collector.zip';
  const instructions=document.createElement('p');instructions.textContent='First-time setup: extract the helper, open Chrome Extensions, enable Developer mode, and select Load unpacked. Skip this if already installed.';
  const label=document.createElement('label');label.textContent='Fields (separate with commas or new lines)';const input=document.createElement('textarea');input.rows=4;input.value=node.integrationSettings.fields||'';input.placeholder='Name, Price, URL';input.onchange=()=>{node.integrationSettings.fields=input.value;save();};label.append(input);
  const pl=document.createElement('label');pl.textContent='Max pages (1 = current page)';const pages=document.createElement('input');pages.type='number';pages.min='1';pages.max='5';pages.step='1';pages.value=node.integrationSettings.maxPages||'1';pages.onchange=()=>{node.integrationSettings.maxPages=pages.value;save();};pl.append(pages);
  const message=document.createElement('p');message.setAttribute('role','status');message.textContent=node.testResult?.message||'No collection yet.';
  const run=document.createElement('button');run.type='button';run.textContent='Collect';run.disabled=busy;run.onclick=async()=>{node.integrationSettings.fields=input.value;node.integrationSettings.maxPages=pages.value;save();run.disabled=true;message.textContent="Collecting...";await test(node);settings(node,host);render();};
  const stop=document.createElement('button');stop.type='button';stop.textContent='Stop';stop.onclick=()=>{stopped=true;message.textContent='Stop requested. The current page request will finish; completed rows will be kept.';};
  const csv=document.createElement('button');csv.type='button';csv.textContent='Export CSV';csv.disabled=!node.testResult?.output?.rows?.length;csv.onclick=()=>exportCsv(node);
  const modeLabel=document.createElement('label');modeLabel.textContent='Execution mode';
  const mode=document.createElement('select');
  for(const [value,text] of [['selenium','Automatic Chrome (no extension)'],['browser','Chrome helper (selected tab)']]){const o=document.createElement('option');o.value=value;o.textContent=text;mode.append(o);}
  mode.value=node.integrationSettings.mode||'selenium';mode.onchange=()=>{node.integrationSettings.mode=mode.value;save();settings(node,host);};modeLabel.append(mode);
  const extra=[];
  function setting(key,text,placeholder,type='text'){const l=document.createElement('label');l.textContent=text;const v=document.createElement('input');v.type=type;v.value=node.integrationSettings[key]||'';v.placeholder=placeholder;if(type==='number'){v.min='0';v.max='10';v.value=node.integrationSettings[key]||'0';}v.onchange=()=>{node.integrationSettings[key]=v.value;save();};l.append(v);extra.push(l);}
  if(mode.value==='selenium'){
   help.textContent='An isolated server browser opens this URL. No extension is needed. Up to 5 list pages and 10 detail pages, one link level on the same host. Extraction uses OpenAI and is billed. Login or verification pauses the task. Results are retained for one hour on the server; saved results remain in this browser.';
   setting('url','Website URL','https://example.com/resources');
   setting('nextSelector','Next-page CSS selector (optional)','a[rel="next"]');
   setting('maxDetails','Maximum detail pages (0 = skip)','0','number');
   setting('detailSelector','Detail-link CSS selector (required for details)','a[href*="Problems"]');
   pl.firstChild.textContent='Maximum list pages (1–5)';
  }
  stop.onclick=async()=>{try{await stopCollection(node);message.textContent='Stop requested. Completed rows will be kept.';}catch(e){message.textContent=e.message;}};
  const resume=document.createElement('button');resume.type='button';resume.textContent='Check last automatic task';resume.disabled=busy||!node.integrationSettings.jobId;resume.onclick=async()=>{busy=true;try{await poll(node,node.integrationSettings.jobId);}catch(e){message.textContent=e.message;}finally{busy=false;settings(node,host);render();}};
  host.append(title,modeLabel,help,...extra);
  if(mode.value==='browser')host.append(download,instructions);
  host.append(label,pl,run,stop,csv,resume,message);
 }
 async function test(node){
  if(busy)throw Error('A collection is already running.');
  if((node.integrationSettings?.mode||'selenium')==='selenium')return automatic(node);
  const fields=fieldsOf(node),max=Number(node.integrationSettings?.maxPages||1);
  const previous=node.testResult?.output;const rows=[];const seenRows=new Set(),seenPages=new Set();const sources=[];let warning='';
  if(!fields.length||fields.length>12||new Set(fields).size!==fields.length||fields.some(f=>f.length>60)||!Number.isInteger(max)||max<1||max>5){node.testResult={status:'error',message:'Enter 1-12 unique fields and a whole number of pages from 1 to 5.',output:previous};return;}
  busy=true;stopped=false;
  try{
   for(let i=0;i<max&&!stopped;i++){
    const {page}=await bridge('capture');if(stopped)break;
    if(page.blocked)throw Error('The website requires verification. Complete it on the target page and retry.');
    const fingerprint=page.text;if(seenPages.has(fingerprint)){warning='Repeated page detected; pagination stopped.';break;}seenPages.add(fingerprint);
    node.connection={status:'testing',message:`Collecting page ${i+1}...`};
    const result=await workflowManagementFetch('/ai/browser-extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields,page})});
    if(!result.ok)throw Error(result.message||'Extraction failed');sources.push(page.url);
    for(const row of result.rows){const key=JSON.stringify(fields.map(f=>row[f]));if(!seenRows.has(key)){seenRows.add(key);rows.push(row);}}
    const limited=result.truncated||result.rows.length>=100;
    if(result.warning||limited){warning=result.warning||'Page content or record limit reached. Results may be incomplete.';break;}
    if(stopped||i+1>=max)break;
    const next=await bridge('next');if(!next.advanced){warning=next.message||'No next page found. Collection ended.';break;}
   }
   const message=stopped?`Stopped. Kept ${rows.length} records.`:`Collected ${sources.length} page(s), ${rows.length} records. ${warning}`;
   node.connection={status:rows.length?'success':'error',message};
   node.testResult={status:rows.length?'success':'error',message,input:{fields,maxPages:max},output:{ok:!!rows.length,rows,fields,sources,warning,stopped,browser_assisted:true}};
  }catch(e){const message=`Collection paused: ${e.message}`;node.connection={status:'error',message};node.testResult={status:'error',message,output:rows.length?{ok:false,rows,fields,sources,partial:true}:previous||{ok:false,rows:[],fields,sources:[]}};
  }finally{busy=false;save();}
  return node.testResult;
 }
 async function stopCollection(node){stopped=true;const jobId=activeJob||node?.integrationSettings?.jobId;if(jobId)await workflowManagementFetch('/ai/selenium-collector/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId})});return {ok:true,message:'Stop requested; completed rows will be kept.'};}
 async function poll(node,jobId){
  activeJob=jobId;
  try{for(;;){
   const r=await workflowManagementFetch('/ai/selenium-collector/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId})});
   const done=['completed','stopped','failed','paused'].includes(r.state);
   const message=r.message+(r.warnings?.length?' '+r.warnings.join(' '):'');
   node.connection={status:done?(r.state==='completed'?'success':'error'):'testing',message};
   node.testResult={status:done?(r.state==='completed'?'success':'error'):'testing',message,output:{ok:r.state==='completed',rows:r.rows,fields:r.fields,sources:r.sources,warnings:r.warnings,state:r.state,partial:r.state!=='completed',automatic:true}};
   save();render();
   const statusEl=document.querySelector('#integrationFields [role="status"]');if(statusEl)statusEl.textContent=message;
   if(done)return node.testResult;
   await new Promise(resolve=>setTimeout(resolve,1800));
  }}finally{activeJob=null;}
 }
 async function automatic(node){
  busy=true;stopped=false;const settings=node.integrationSettings||{};const previous=node.testResult?.output;
  try{
   const r=await workflowManagementFetch('/ai/selenium-collector/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:settings.url,fields:fieldsOf(node),maxPages:Number(settings.maxPages||1),maxDetails:Number(settings.maxDetails||0),nextSelector:settings.nextSelector||'',detailSelector:settings.detailSelector||''})});
   settings.jobId=r.jobId;activeJob=r.jobId;save();
   if(stopped)await stopCollection(node);
   return await poll(node,r.jobId);
  }catch(e){node.testResult={status:'error',message:e.message,output:node.testResult?.output||previous};node.connection={status:'error',message:e.message};return node.testResult;}
  finally{busy=false;activeJob=null;save();}
 }
 function exportCsv(node){const output=node.testResult.output;const fields=output.fields||Object.keys(output.rows[0]);const cell=v=>'"'+String(/^[=+\-@\t\r]/.test(String(v))?"'"+v:v??'').replaceAll('"','""')+'"';const csv='\uFEFF'+[fields,...output.rows.map(r=>fields.map(f=>r[f]))].map(row=>row.map(cell).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='web-collection.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 async function voice(args){const node=nodes.find(n=>n.id===selectedId&&isNode(n));if(!node)throw Error('Add and select Web Collector from Agent Skills & Tools first.');node.integrationSettings||={};node.integrationSettings.fields=args.fields.join(',');node.integrationSettings.maxPages=String(args.max_pages);const result=await test(node);render();renderIntegrationFields(node);return {ok:result.status==='success',message:result.message,rows:result.output?.rows?.length||0};}
 window.BrowserCollector={isNode,settings,test,voice,stop:()=>stopCollection(nodes.find(n=>n.id===selectedId&&isNode(n)))};
})();
