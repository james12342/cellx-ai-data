const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<div><button id="uploadPhotosBtn"></button></div>',{runScripts:'outside-only',url:'https://app.test'});
 const w=dom.window;
 w.HTMLMediaElement.prototype.pause=function(){};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 const upload={id:'u',type:'trigger',integrationSettings:{photoFilesJson:JSON.stringify([{id:'a'.repeat(40)},{id:'b'.repeat(40)}])}};
 const video={id:'v',name:'Video Generation',type:'script',integrationSettings:{scriptName:'video_generator.py',inputJson:'{"options":{"duration_seconds":10,"aspect_ratio":"9:16"}}'}};
 const publish={id:'p',type:'communication'};
 let requests=[],saved=0;
 Object.assign(w,{nodes:[upload,video,publish],activeWorkflowId:'w',WorkflowPhotos:{isNode:n=>n===upload},incomingNodes:()=>[upload],workflowOrder:()=>w.nodes,
 iconMarkup:()=>'',CellI18n:{lang:'en'},saveWorkflowDraft:()=>saved++,render:()=>w.WorkflowVideo?.render(),
 workflowManagementFetch:async(path,options={})=>{requests.push({path,options});return {ok:true,id:'c'.repeat(40),status:'completed',progress:100};},
 workflowManagementToken:()=> 'fixture',apiBase:'/ext-api',confirm:()=>true});
 w.eval(fs.readFileSync('cellx-extension-ui/workflow-video.js','utf8'));
 assert.equal(w.document.querySelector('#workflowVideoBtn').hidden,false);
 await w.WorkflowVideo.test(video);
 assert.deepEqual(JSON.parse(requests[0].options.body).photo_ids,['a'.repeat(40),'b'.repeat(40)]);
 assert.equal(video.testResult.status,'success');assert.ok(saved>=1);
 assert.match(w.document.querySelector('#workflowVideoBtn').textContent,/Preview Video/);
 w.WorkflowVideo.pauseFollowing(video);assert.equal(publish.testResult.output.skipped,true);
 upload.integrationSettings.photoFilesJson='[]';await w.WorkflowVideo.test(video);assert.equal(video.testResult.status,'error');
 assert.equal(requests.length,1);assert.equal(requests.some(r=>/facebook|instagram/.test(r.path)),false);
 w.nodes=[upload];w.WorkflowVideo.render();assert.equal(w.document.querySelector('#workflowVideoBtn').hidden,true);
 const before=JSON.stringify(upload);w.WorkflowVideo.pauseFollowing(video);assert.equal(JSON.stringify(upload),before);
 dom.window.close();console.log('Video UI: photo mapping, completed output, preview entry, no auto-publish, missing photos and scope passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
