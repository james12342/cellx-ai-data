const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const context={window:{},setTimeout,clearTimeout};vm.createContext(context);
vm.runInContext(fs.readFileSync('cellx-extension-ui/workflow-product-analysis.js','utf8'),context);
const Queue=context.window.ProductAnalysisQueue;
const tick=()=>new Promise(r=>setTimeout(r,15));
(async()=>{
 let snapshot={photo_ids:['a'],key:'a'},requests=[],applied=[],statuses=[];
 const q=new Queue({delay:1,read:()=>snapshot,send:s=>new Promise((resolve,reject)=>requests.push({s,resolve,reject})),apply:(n,r)=>applied.push(r),status:(n,s)=>statuses.push(s)});
 const node={};q.schedule(node);q.schedule(node);await tick();assert.equal(requests.length,1);
 q.invalidate(node);snapshot={photo_ids:['a','b'],key:'ab'};requests[0].resolve('old');await tick();
 assert.equal(requests.length,1,'must not analyze partial upload');assert.equal(applied.length,0);
 snapshot={photo_ids:['a','b','c'],key:'abc'};q.schedule(node);await tick();assert.equal(requests.length,2);
 snapshot={photo_ids:['c','b','a'],key:'cba'};q.schedule(node);requests[1].resolve('stale');await tick();assert.equal(requests.length,3);assert.equal(applied.length,0);
 requests[2].reject(Error('test failure'));await tick();assert.equal(statuses.at(-1),'failed');
 q.schedule(node);await tick();requests[3].resolve('ordered');await tick();assert.deepEqual(applied,['ordered']);
 assert.equal(statuses.at(-1),'ready');console.log('PASS batch debounce, no partial upload call, stale response rejection, failure and retry.');
})().catch(e=>{console.error(e);process.exitCode=1;});
