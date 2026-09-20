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
   const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:{mode:'portrait',duration_seconds:30,product_info:'蓝色杯子',narration:'给生活留一点美好的时间。\n了解这只蓝色杯子。',voice:'zh-female'}})}};
   Object.assign(window,{nodes:[upload,node],selectedId:'v',activeWorkflowId:'test',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>window.nodes,
    iconMarkup:()=>'',CellI18n:{lang:'zh-CN'},saveWorkflowDraft:()=>{},render:()=>{},posts:[],confirm:()=>true,apiBase:'/ext-api',
    workflowManagementFetch:async(path,opts={})=>{if(path.endsWith('/providers'))return {portrait:{online:true}};
     if(opts.method==='POST'){const data=JSON.parse(opts.body);window.posts.push(data);if(path.endsWith('/product-brief'))return {product_info:'从一杯开始，发现生活的美好。\n查看商品详情。'};throw Error('Test stops before external generation');}
     return {ok:true};}});
  });
  await page.addStyleTag({path:'cellx-extension-ui/workflow-video.css'});
  await page.addScriptTag({path:'cellx-extension-ui/workflow-video.js'});
  await page.click('#workflowVideoBtn');
  assert.equal(await page.locator('.portrait-panel').isVisible(),true);
  assert.equal(await page.locator('.economy-panel').isVisible(),false);
  assert.equal(await page.locator('.video-apply-music').isVisible(),false);
  await page.selectOption('.portrait-photo','c'.repeat(40));
  await page.fill('.portrait-script','大家好，欢迎看房。');
  await page.selectOption('.portrait-voice','zh-male');
  await page.click('.video-save-brief');
  await page.evaluate(()=>window.WorkflowVideo.test(window.nodes[1]));
  const posts=await page.evaluate(()=>window.posts);
  assert.equal(posts.length,1);
  assert.deepEqual(posts[0].photo_ids,['c'.repeat(40)]);
  assert.equal(posts[0].options.mode,'portrait');
  assert.equal(posts[0].options.voice,'zh-male');
  assert.equal(posts[0].options.narration,'大家好，欢迎看房。');
  assert.match(posts[0].request_id,/^[a-f0-9]{40}$/);
  await page.selectOption('.mode','portrait_storyboard');
  await page.fill('.duration','20');
  await page.fill('.eco-script','大家好，欢迎一起看房。\n接下来看看这套房子的明亮客厅。');
  assert.equal(await page.locator('.portrait-script').isVisible(),false);
  assert.equal(await page.locator('.eco-script').isVisible(),true);
  assert.equal(await page.locator('.duration').isVisible(),true);
  await page.click('.video-save-brief');
  await page.evaluate(()=>{window.posts=[];delete nodes[1].integrationSettings.videoSubmissionId;});
  await page.evaluate(()=>window.WorkflowVideo.test(window.nodes[1]));
  const multi=await page.evaluate(()=>window.posts[0]);
  assert.equal(multi.options.mode,'portrait_storyboard');
  assert.deepEqual(multi.photo_ids,['c'.repeat(40),'b'.repeat(40)]);
  assert.deepEqual(multi.options.storyboard_scenes.map(s=>s.photo_id),multi.photo_ids);
  assert.equal(multi.options.duration_seconds,20);
  assert.equal(multi.options.portrait_narration,'大家好，欢迎看房。');
  console.log('PASS portrait selection, script, remote mode and idempotency payload.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
