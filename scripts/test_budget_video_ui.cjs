const {chromium}=require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
const assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage();
  page.on("pageerror",error=>console.error("BROWSER:",error.message));
  await page.setContent('<div><button id="uploadPhotosBtn"></button></div>');
  const catalog=JSON.parse(fs.readFileSync('outputs/video-catalog.json','utf8'));
  await page.evaluate(info=>{
   const upload={id:'u',integrationSettings:{photoFilesJson:JSON.stringify([{id:'b'.repeat(40)},{id:'c'.repeat(40)}])}};
   const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:{mode:'runway',model:'wan_turbo',duration_seconds:5,product_info:'Blue cup',style:'studio',aspect_ratio:'9:16'}})}};
   info.models.forEach(m=>m.configured=true);
   Object.assign(window,{nodes:[upload,node],selectedId:'v',activeWorkflowId:'test',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>window.nodes,
    iconMarkup:()=>'',CellI18n:{lang:'zh-CN'},saveWorkflowDraft:()=>{},render:()=>{},apiBase:'/ext-api',posts:[],confirm:()=>true,
    workflowManagementFetch:async(path,opts={})=>{if(path.endsWith('/providers'))return info;if(opts.method==='POST'){window.posts.push(JSON.parse(opts.body));throw Error('Test stops before paid call');}return {ok:true};}});
  },catalog);
  await page.addStyleTag({path:'cellx-extension-ui/workflow-video.css'});
  await page.addScriptTag({path:'cellx-extension-ui/workflow-video.js'});
  await page.click('#workflowVideoBtn');
  await page.waitForFunction(()=>document.querySelector('.model-note').textContent.includes('0.10'));
  assert.equal(await page.locator('.video-model option').count(),5);
  assert.equal(await page.locator('.chatgpt-open').getAttribute('href'),'https://chatgpt.com/');
  assert.equal(await page.locator('.duration').isVisible(),false);
  for(const [model,duration,cost] of [['hailuo_fast',6,'0.19'],['kling_turbo',5,'0.35'],['gen4_turbo',5,'0.25'],['product_ad',5,'2.36']]){
   await page.selectOption('.video-model',model);
   assert.equal(await page.inputValue('.duration'),String(duration));
   assert.ok((await page.locator('.model-note').textContent()).includes(cost));
  }
  await page.selectOption('.video-model','hailuo_fast');
  assert.equal(await page.locator('.aspect').isDisabled(),true);
  assert.equal(await page.locator('.ai-audio').isVisible(),false);
  await page.fill('.duration','10');await page.locator('.duration').dispatchEvent('change');
  assert.ok((await page.locator('.model-note').textContent()).includes('0.32'));
  await page.click('.video-save-brief');
  await page.evaluate(()=>window.WorkflowVideo.test(window.nodes[1]));
  const sent=await page.evaluate(()=>window.posts[0]);
  assert.equal(sent.options.model,'hailuo_fast');assert.equal(sent.approved_credits,32);assert.equal(sent.photo_ids.length,1);assert.equal(sent.options.audio,false);
  await page.screenshot({path:'outputs/budget-video-ui.png',fullPage:true});
  console.log('PASS: all 5 models, price updates, duration restrictions, photo selection, silent audio and paid payload; no external generation.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
