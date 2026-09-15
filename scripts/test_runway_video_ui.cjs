const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<div><button id="uploadPhotosBtn"></button></div>',{runScripts:'outside-only',url:'https://app.test'});
 const w=dom.window;
 Object.defineProperty(w,'crypto',{value:require('node:crypto').webcrypto});
 w.HTMLMediaElement.prototype.pause=function(){};
 const upload={id:'u',type:'trigger',integrationSettings:{photoFilesJson:JSON.stringify([{id:'b'.repeat(40)}])}};
 const opts={mode:'runway',duration_seconds:10,aspect_ratio:'9:16',style:'studio',product_info:'Ceramic mug',audio:true};
 const node={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:JSON.stringify({options:opts})}};
 let configured=false,approve=false,fail=false,posts=[],prompts=[];
 const job={ok:true,id:'a'.repeat(40),provider:'runway',status:'completed'};
 Object.assign(w,{nodes:[upload,node],activeWorkflowId:'w',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>w.nodes,
 iconMarkup:()=>'',CellI18n:{lang:'en'},saveWorkflowDraft:()=>{},render:()=>{},apiBase:'/ext-api',
 confirm:s=>{prompts.push(s);return approve;},workflowManagementFetch:async(path,options={})=>{
  if(path.endsWith('/providers'))return {runway_configured:configured,base_credits:200,extra_second_credits:36,credit_usd:.01};
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(fail)throw Error('Network interrupted');}
  return {...job};
 }});
 w.eval(fs.readFileSync('cellx-extension-ui/workflow-video.js','utf8'));
 await w.WorkflowVideo.test(node);assert.equal(posts.length,0);assert.match(node.connection.message,/not configured/);
 configured=true;await w.WorkflowVideo.test(node);assert.equal(posts.length,0);assert.match(prompts[0],/4.16/);
 approve=true;fail=true;await w.WorkflowVideo.test(node);const id=posts[0].request_id;
 assert.match(id,/^[a-f0-9]{40}$/);assert.equal(node.integrationSettings.videoSubmissionId,id);
 fail=false;await w.WorkflowVideo.test(node);assert.equal(posts[1].request_id,id);
 assert.equal(posts[1].approved_credits,416);assert.equal(posts[1].confirm_paid,true);assert.equal(posts[1].options.audio,true);
 assert.equal(node.integrationSettings.videoSubmissionId,undefined);
 assert.equal(node.integrationSettings.videoJobId,job.id);
 assert.equal(node.testResult.input.confirm_paid,undefined);
 const count=posts.length;await w.WorkflowVideo.test(node);assert.equal(posts.length,count);
 await w.WorkflowVideo.test(node,true);assert.equal(posts.length,count+1);assert.notEqual(posts.at(-1).request_id,id);
 assert.ok(w.document.querySelector('.video-ai-fields'));
 dom.window.close();console.log('Runway UI: missing key, cost confirmation, cancellation, retry deduplication, resume and new generation passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
