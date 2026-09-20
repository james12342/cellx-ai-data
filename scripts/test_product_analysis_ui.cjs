const {chromium}=require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage();page.on('pageerror',e=>{throw e;});
  await page.setContent('<div><button id="uploadPhotosBtn"></button></div>');
  await page.evaluate(()=>{
   const upload={id:'u',name:'Upload Product Photos',type:'trigger',integrationSettings:{photoFilesJson:'[]'}};
   const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:{mode:'economy',voice:'zh-male',duration_seconds:30}})}};
   Object.assign(window,{nodes:[upload,node],selectedId:'v',activeWorkflowId:'test',incomingNodes:n=>n===node?[upload]:[],workflowOrder:()=>window.nodes,
    iconMarkup:()=>'',CellI18n:{lang:'zh-CN'},saveWorkflowDraft:()=>{},render:()=>{},renderIntegrationFields:()=>{},workflowManagementToken:()=>true,requests:[],pending:[],apiBase:'/ext-api'});
   let count=0;
   window.workflowManagementFetch=async(path,opts={})=>{
    if(path.endsWith('/providers'))return {economy:{voice:true},portrait:{online:true}};
    if(path==='/photo-uploads')return {file:{id:String(++count).padStart(40,'a'),name:JSON.parse(opts.body).name,mime_type:'image/jpeg'}};
    if(path.startsWith('/photo-uploads/'))return {file:{mime_type:'image/jpeg'},data:''};
    if(path.endsWith('/product-brief')){const payload=JSON.parse(opts.body);window.requests.push(payload);return new Promise((resolve,reject)=>window.pending.push({payload,resolve,reject}));}
    throw Error('Unexpected API call: '+path);
   };
   window.respond=(index,fail=false)=>{const p=window.pending[index];if(fail)return p.reject(Error('simulated failure'));p.resolve({ok:true,photo_ids:p.payload.photo_ids,product_info:'AI visible product details',scenes:p.payload.photo_ids.map((id,i)=>({photo_id:id,visual_description:'Visual '+id,narration:'自动口播'+(i+1)})),narration:'unused',language:p.payload.language,voice:p.payload.voice,duration_seconds:p.payload.duration_seconds,timing:{verified:true,matched:true,target_seconds:p.payload.duration_seconds,measured_seconds:p.payload.duration_seconds,tempo:1}});};
  });
  for(const file of ['workflow-photos.js','workflow-video.js','workflow-product-analysis.js'])await page.addScriptTag({path:'cellx-extension-ui/'+file});
  await page.click('#uploadPhotosBtn');
  await page.locator('.photo-dialog input[type=file]').setInputFiles(['one','two','three'].map(name=>({name:name+'.jpg',mimeType:'image/jpeg',buffer:Buffer.from('test image')})));
  await page.waitForFunction(()=>window.requests.length===1);
  assert.equal(await page.evaluate(()=>requests[0].photo_ids.length),3);
  await page.click('.photo-done');await page.click('#workflowVideoBtn');
  await page.fill('.product-info','我的手动产品描述');
  await page.locator('.analysis-scenes textarea').nth(1).fill('第二张人工口播');
  await page.evaluate(()=>respond(0));await page.waitForFunction(()=>JSON.parse(nodes[1].integrationSettings.inputJson).options.product_analysis.state==='ready');
  assert.equal(await page.inputValue('.product-info'),'我的手动产品描述');
  assert.match(await page.inputValue('.eco-script'),/第二张人工口播/);
  assert.equal(await page.locator('.analysis-scenes textarea').count(),3);
  assert.equal(await page.evaluate(()=>requests.length),1);
  await page.click('.video-close');await page.click('#uploadPhotosBtn');
  await page.locator('.photo-item').nth(1).getByRole('button',{name:'前移',exact:true}).click();
  await page.waitForFunction(()=>requests.length===2);
  const orders=await page.evaluate(()=>requests.map(r=>r.photo_ids));
  assert.equal(orders[1][0],orders[0][1]);
  await page.evaluate(()=>respond(1));await page.click('.photo-done');await page.click('#workflowVideoBtn');
  assert.equal(await page.locator('.analysis-scenes textarea').first().inputValue(),'第二张人工口播');
  await page.click('.video-close');await page.click('#uploadPhotosBtn');
  await page.locator('.photo-item').last().getByRole('button',{name:'移除',exact:true}).click();
  await page.waitForFunction(()=>requests.length===3);assert.equal(await page.evaluate(()=>requests[2].photo_ids.length),2);
  await page.evaluate(()=>respond(2,true));await page.click('.photo-done');await page.click('#workflowVideoBtn');
  await page.waitForFunction(()=>document.querySelector('.analysis-status').textContent.includes('分析失败'));
  await page.click('.analysis-retry');await page.waitForFunction(()=>requests.length===4);await page.evaluate(()=>respond(3));
  await page.selectOption('.brief-provider','chatgpt').catch(async()=>{
   await page.locator('select').filter({has:page.locator('option[value=chatgpt]')}).selectOption('chatgpt');
  });
  assert.equal(await page.locator('.chatgpt-open').isVisible(),true);
  assert.equal(await page.inputValue('.product-info'),'我的手动产品描述');
  await page.locator('select').filter({has:page.locator('option[value=api]')}).selectOption('api');
  await page.uncheck('.analysis-auto');
  await page.click('.ai-generate-brief');await page.waitForFunction(()=>requests.length===5);
  assert.equal(await page.evaluate(()=>requests[4].purpose),'storyboard');
  assert.equal(await page.evaluate(()=>requests[4].photo_ids.length),2);
  await page.evaluate(()=>respond(4));await page.waitForFunction(()=>JSON.parse(nodes[1].integrationSettings.inputJson).options.product_analysis.state==='ready');
  assert.equal(await page.isChecked('.analysis-auto'),false);
  assert.equal(await page.inputValue('.product-info'),'我的手动产品描述');
  assert.equal(await page.locator('.brief-billing').innerText().then(t=>t.includes('前 3')),false);
  await page.check('.analysis-auto');
  await page.fill('.duration','40');await page.locator('.duration').press('Tab');await page.waitForFunction(()=>requests.length===6);
  assert.equal(await page.evaluate(()=>requests[5].duration_seconds),40);
  assert.equal(await page.evaluate(()=>requests[5].voice),'zh-male');
  await page.fill('.duration','55');await page.locator('.duration').press('Tab');
  await page.evaluate(()=>respond(5));await page.waitForFunction(()=>requests.length===7);
  assert.equal(await page.evaluate(()=>JSON.parse(nodes[1].integrationSettings.inputJson).options.product_analysis.draft.duration_seconds),30,'stale 40s response must not apply');
  await page.evaluate(()=>respond(6));await page.waitForFunction(()=>JSON.parse(nodes[1].integrationSettings.inputJson).options.product_analysis.draft.duration_seconds===55);
  assert.equal(await page.inputValue('.duration'),'55');
  assert.equal(await page.inputValue('.product-info'),'我的手动产品描述');
  assert.equal(await page.locator('.analysis-scenes textarea').first().inputValue(),'第二张人工口播');
  assert.equal(await page.evaluate(()=>WorkflowProductAnalysis.hasTiming(nodes[1])),false,'manual text must not inherit AI speech measurement');
  const staleChecks=await page.evaluate(()=>{
    const n=nodes[1],opts=JSON.parse(n.integrationSettings.inputJson).options;
    const ids=opts.storyboard_scenes.map(s=>s.photo_id);
    opts.mode='portrait_storyboard';opts.portrait_photo_id=ids[0];opts.duration_seconds=55;opts.voice='zh-male';opts.copy_language='zh-CN';opts.storyboard_linked=true;
    opts.narration=opts.storyboard_scenes.map(s=>s.narration).join('\n');
    opts.product_analysis.draft={...opts.product_analysis.draft,narration:opts.narration,photo_ids:ids,portrait_photo_id:ids[0],duration_seconds:55,voice:'zh-male'};
    const check=()=>{n.integrationSettings.inputJson=JSON.stringify({options:opts});try{WorkflowProductAnalysis.validate(n);return false;}catch{return true;}};
    const valid=check();opts.duration_seconds=40;const duration=check();opts.duration_seconds=55;opts.voice='zh-female';const voice=check();opts.narration+='人工改稿';const manual=check();
    return {valid,duration,voice,manual};
  });
  assert.deepEqual(staleChecks,{valid:false,duration:true,voice:true,manual:false},'stale AI duration/voice rejected; manual text preserved');
  console.log('PASS one analysis per multi-photo batch, manual edits, image reorder/remove associations, failure/retry, ChatGPT preserved; no video calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
