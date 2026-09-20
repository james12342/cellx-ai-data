const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
let listener,chosen={tabId:7,origin:'https://example.com',expires:Date.now()+60000},page={url:'https://example.com/list',text:'items',next:null},injected=0,updates=0;
const chrome={runtime:{id:'test',onMessage:{addListener:fn=>listener=fn}},storage:{session:{get:async()=>({chosen})}},tabs:{get:async()=>({url:'https://example.com/list'}),update:async()=>{updates++;}},scripting:{executeScript:async()=>{injected++;return [{result:page}];}}};
vm.runInNewContext(fs.readFileSync('browser-collector-extension/background.js','utf8'),{chrome,URL,Date,Error,setTimeout,console});
const call=(action,url='https://app.cellaidata.com/agent/')=>new Promise(resolve=>listener({action},{id:'test',url},resolve));
(async()=>{
 assert.equal((await call('capture','https://evil.example/agent/')).ok,false);assert.equal(injected,0);
 assert.equal((await call('capture')).ok,true);
 assert.equal((await call('next')).advanced,false);
 page.next='https://other.example/page/2';assert.equal((await call('next')).ok,false);assert.equal(updates,0);
 page.next='https://example.com/delete?id=1';assert.equal((await call('next')).ok,false);assert.equal(updates,0);
 chosen.expires=0;assert.equal((await call('capture')).ok,false);
 console.log('PASS chosen-page scope, sender checks, expiry, missing next, and unsafe navigation rejection.');
})().catch(e=>{console.error(e);process.exitCode=1;});
