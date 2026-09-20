const {chromium}=require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}});page.on('pageerror',e=>{throw e;});
  await page.setContent('<div><button id="uploadPhotosBtn"></button></div>');
  await page.evaluate(()=>{
   const ids=['b'.repeat(40),'c'.repeat(40),'d'.repeat(40)];
   const upload={id:'u',integrationSettings:{photoFilesJson:JSON.stringify(ids.map((id,i)=>({id,name:['经纪人.jpg','泳池.jpg','客厅.jpg'][i]})))}};
   const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:{mode:'portrait_storyboard',auto_analyze:false,voice:'zh-male',copy_language:'zh-CN',duration_seconds:55,portrait_photo_id:ids[0],portrait_narration:'独立纯人像原稿',narration:'当前开场口播\n当前泳池讲解\n当前客厅讲解',storyboard_scenes:ids.map(id=>({photo_id:id,narration:'不应显示的旧稿'})),product_info:'保留手写产品信息',brief_provider:'chatgpt'}})}};
   Object.assign(window,{nodes:[upload,node],selectedId:'v',activeWorkflowId:'test',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>window.nodes,iconMarkup:()=>'',CellI18n:{lang:'zh-CN'},saveWorkflowDraft:()=>{},render:()=>{},apiBase:'/ext-api',posts:[],draftCalls:0,
   workflowManagementFetch:async(path,opts={})=>{
    if(path.endsWith('/providers'))return {portrait:{online:true}};
    if(path.endsWith('/product-brief')){window.draftCalls++;const p=JSON.parse(opts.body);const scenes=p.photo_ids.map((id,i)=>({photo_id:id,narration:['AI开场','AI泳池','AI客厅'][i],visual_description:'照片可见描述'}));return {ok:true,photo_ids:p.photo_ids,scenes,narration:scenes.map(s=>s.narration).join('\n'),product_info:'AI产品信息',duration_seconds:p.duration_seconds,language:p.language,voice:p.voice,portrait_photo_id:p.portrait_photo_id,ai_draft_signature:'test-proof',timing:{verified:false,verification_location:'gpu-worker'}};}
    if(path==='/promo-videos'&&opts.method==='POST'){posts.push(JSON.parse(opts.body));throw Error('Test intercepted: no video generated');}
    if(path.startsWith('/photo-uploads/'))return {file:{mime_type:'image/jpeg'},data:''};
    return {ok:true};
   }});
  });
  await page.addStyleTag({path:'cellx-extension-ui/workflow-video.css'});
  for(const file of ['workflow-video.js','workflow-product-analysis.js'])await page.addScriptTag({path:'cellx-extension-ui/'+file});
  await page.click('#workflowVideoBtn');
  const inputs=page.locator('.presenter-narration .analysis-scenes textarea');
  assert.equal(await inputs.count(),3);
  assert.equal(await page.getByLabel('数字人开场口播',{exact:true}).inputValue(),'当前开场口播');
  assert.equal(await page.locator('.eco-script').isVisible(),false);
  assert.equal(await page.locator('.portrait-script').isVisible(),false);
  assert.equal(await page.locator('.portrait-panel').evaluate(el=>el.previousElementSibling.className),'video-options');
  assert.equal(await page.locator('.duration').getAttribute('max'),'300');
  assert.equal(await page.locator('.duration').inputValue(),'55','existing duration must not change to maximum');
  for(const seconds of [60,61,75,120,299,300,301]){
    await page.fill('.duration',String(seconds));
    assert.equal(await page.locator('.duration').evaluate(el=>el.validity.valid),seconds<=300);
    if(seconds<=300)assert.equal(await page.evaluate(()=>WorkflowProductAnalysis.read(nodes[1],true).duration_seconds),seconds);
  }
  await page.fill('.duration','300');
  await page.locator('.duration').press('Tab');
  await inputs.nth(1).fill('手动修改泳池讲解');
  await page.click('.video-save-brief');await page.click('.video-close');await page.click('#workflowVideoBtn');
  assert.equal(await inputs.nth(1).inputValue(),'手动修改泳池讲解');
  await page.selectOption('.mode','portrait');
  assert.equal(await page.locator('.portrait-script').inputValue(),'独立纯人像原稿');
  await page.locator('.portrait-script').fill('新的纯人像稿');
  await page.selectOption('.mode','portrait_storyboard');
  assert.equal(await page.locator('.duration').inputValue(),'300');
  assert.equal(await inputs.first().inputValue(),'当前开场口播');
  assert.equal(await inputs.nth(1).inputValue(),'手动修改泳池讲解');
  await page.click('.presenter-write');
  await page.waitForFunction(()=>window.draftCalls===1&&JSON.parse(nodes[1].integrationSettings.inputJson).options.product_analysis.state==='ready');
  assert.equal(await inputs.nth(1).inputValue(),'手动修改泳池讲解','unapplied AI must not replace manual speech');
  assert.equal(await page.locator('.presenter-use').isVisible(),true);
  assert.match(await page.locator('.presenter-draft-status').innerText(),/尚未应用/);
  await page.click('.presenter-use');
  assert.deepEqual(await inputs.evaluateAll(els=>els.map(e=>e.value)),['AI开场','AI泳池','AI客厅']);
  await inputs.nth(2).fill('用户改后的客厅稿\n第二句仍属于客厅');
  await page.click('.video-save-brief');await page.click('.video-close');await page.click('#workflowVideoBtn');
  assert.equal(await inputs.nth(2).inputValue(),'用户改后的客厅稿\n第二句仍属于客厅');
  await page.evaluate(()=>WorkflowVideo.test(nodes[1]));
  const payload=await page.evaluate(()=>posts[0]);
  assert.equal(payload.options.narration,'AI开场\nAI泳池\n用户改后的客厅稿\n第二句仍属于客厅');
  assert.deepEqual(payload.options.storyboard_scenes.map(s=>s.narration),['AI开场','AI泳池','用户改后的客厅稿\n第二句仍属于客厅']);
  assert.deepEqual(payload.options.storyboard_scenes.map(s=>s.photo_id),payload.photo_ids);
  assert.equal(payload.options.ai_draft_signature,'test-proof'); // server rejects after text change
  assert.equal(payload.options.narration_drafts,undefined,'render does not transmit other mode drafts');
  assert.equal(payload.options.product_analysis.draft.narration,undefined,'render does not duplicate AI narration');
  assert.equal(await page.locator('.chatgpt-open').isVisible(),true);
  await page.screenshot({path:'outputs/presenter-editor-fix/editor-ui.png',fullPage:true});
  console.log('PASS mixed editor existing script, single visible source, pending AI/apply, edits/save/reopen, mode isolation, exact submit mapping; no inference calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
