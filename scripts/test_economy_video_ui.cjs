const {chromium}=require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1100}});
  page.on('pageerror',e=>{throw e;});
  await page.setContent('<div><button id="uploadPhotosBtn"></button></div>');
  await page.evaluate(()=>{
   const upload={id:'u',integrationSettings:{photoFilesJson:JSON.stringify([{id:'b'.repeat(40)},{id:'c'.repeat(40)}])}};
   const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:{mode:'economy',duration_seconds:30,product_info:'蓝色杯子',narration:'给生活留一点美好的时间。\n了解这只蓝色杯子。',voice:'zh-female'}})}};
   Object.assign(window,{nodes:[upload,node],selectedId:'v',activeWorkflowId:'test',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>window.nodes,
    iconMarkup:()=>'',CellI18n:{lang:'zh-CN'},saveWorkflowDraft:()=>{},render:()=>{},posts:[],confirm:()=>true,apiBase:'/ext-api',
    workflowManagementFetch:async(path,opts={})=>{if(path.endsWith('/providers'))return {economy:{voice:true,renderer:true}};
     if(opts.method==='POST'){const data=JSON.parse(opts.body);window.posts.push(data);if(path.endsWith('/product-brief'))return {product_info:'从一杯开始，发现生活的美好。\n查看商品详情。'};throw Error('Test stops before external generation');}
     return {ok:true};}});
  });
  await page.addStyleTag({path:'cellx-extension-ui/workflow-video.css'});
  await page.addScriptTag({path:'cellx-extension-ui/workflow-video.js'});
  await page.click('#workflowVideoBtn');
  assert.equal(await page.locator('.economy-panel').isVisible(),true);
  assert.equal(await page.locator('.video-model').isVisible(),false);
  assert.equal(await page.locator('.ad-preset').isVisible(),false);
  assert.equal(await page.locator('.eco-scenes li').count(),2);
  await page.selectOption('.eco-voice','en-female');
  assert.equal(await page.inputValue('.eco-voice'),'zh-female');
  await page.click('.eco-write');
  await page.waitForSelector('.eco-draft:not([hidden])');
  assert.equal(await page.inputValue('.eco-script'),'给生活留一点美好的时间。\n了解这只蓝色杯子。');
  await page.click('.eco-use');
  await page.fill('.eco-brand','CELL AI');await page.fill('.eco-cta','查看商品详情');
  await page.click('.video-save-brief');
  const saved=await page.evaluate(()=>JSON.parse(window.nodes[1].integrationSettings.inputJson).options);
  assert.equal(saved.mode,'economy');assert.equal(saved.voice,'zh-female');assert.equal(saved.brand,'CELL AI');
  await page.evaluate(()=>window.WorkflowVideo.test(window.nodes[1]));
  const posts=await page.evaluate(()=>window.posts);
  assert.equal(posts[0].purpose,'narration');assert.equal(posts[0].duration_seconds,30);
  assert.equal(posts[1].options.mode,'economy');assert.equal(posts[1].photo_ids.length,2);
  assert.match(posts[1].request_id,/^[a-f0-9]{40}$/);
  await page.screenshot({path:'outputs/economy-video-ui.png',fullPage:true});
  console.log('PASS economy editor, draft review, storyboard mapping, persistence, request deduplication ID and payload. No paid calls.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
