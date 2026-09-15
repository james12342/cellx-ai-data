const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const dom=new JSDOM('<button id="uploadPhotosBtn"></button>',{runScripts:'outside-only',url:'https://app.test'});
  const w=dom.window;
  w.Element.prototype.replaceChildren=function(...children){this.textContent=''; this.append(...children);};
  const node={id:'upload',type:'trigger',name:'User Uploads Product Photos',integrationSettings:{}};
  Object.assign(w,{nodes:[node],activeWorkflowId:'a',selectedId:'upload',CellI18n:{lang:'en'},
    iconMarkup:()=>'<img alt="" src="upload.svg">',renderIntegrationFields:()=>{},
    workflowManagementToken:()=> 'test',saved:0,saveWorkflowDraft:()=>w.saved++,
    render:()=>w.WorkflowPhotos.render()});
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.Image=class {naturalWidth=100; naturalHeight=100; async decode(){} };
  const stored=new Map(); let counter=0, fail=false;
  w.workflowManagementFetch=async(path,options={})=>{
    if(fail) throw Error('Upload unavailable');
    if(options.method==='POST') {
      const payload=JSON.parse(options.body), id=String(++counter).padStart(40,'0');
      const file={id,name:payload.name,mime_type:'image/png',size:10};
      stored.set(id,{ok:true,file,data:payload.data}); return {ok:true,file};
    }
    const id=path.split('/').pop();
    if(options.method==='DELETE') { stored.delete(id); return {ok:true}; }
    if(!stored.has(id)) throw Error('Photo not found');
    return stored.get(id);
  };
  w.eval(fs.readFileSync('cellx-extension-ui/workflow-photos.js','utf8'));
  const button=w.document.querySelector('button');
  assert.equal(button.hidden,false);
  await w.WorkflowPhotos.test(node); assert.equal(node.testResult.status,'error');
  button.click();
  const picker=w.document.querySelector('input');
  const select=async files=>{Object.defineProperty(picker,'files',{value:files,configurable:true});await picker.onchange();};
  await select([new w.File(['photo'],'product.png',{type:'image/png'})]);
  assert.equal(stored.size,1); assert.equal(w.saved,1);
  assert.match(button.textContent,/\(1\)/);
  assert.equal(w.document.querySelectorAll('.photo-item').length,1);
  assert.equal(node.testResult.output.files[0].name,'product.png');
  assert.equal(node.testResult.output.count,1);
  assert.equal(node.testResult.output.files[0].data,undefined);
  await w.WorkflowPhotos.test(node); assert.equal(node.testResult.status,'success');
  const restored=JSON.parse(JSON.stringify(node)); await w.WorkflowPhotos.test(restored);
  assert.equal(restored.testResult.output.count,1);
  await select([new w.File(['svg'],'bad.svg',{type:'image/svg+xml'})]); assert.equal(stored.size,1);
  assert.equal(w.document.querySelector('.photo-status').dataset.error,'true');
  fail=true;
  await select([new w.File(['photo'],'fail.png',{type:'image/png'})]); assert.equal(stored.size,1);
  assert.equal(picker.disabled,false); fail=false;
  await w.document.querySelector('.photo-item button').onclick();
  assert.equal(stored.size,0); assert.equal(node.testResult.output.count,0);
  w.nodes=[{type:'trigger',name:'Schedule'}]; w.WorkflowPhotos.render(); assert.equal(button.hidden,true);
  w.nodes=[node]; w.CellI18n.lang='zh-CN'; w.WorkflowPhotos.render(); assert.match(button.textContent,/上传图片/);
  dom.window.close();
  console.log('Photo UI: upload, preview, draft restore, node output, invalid type, failure recovery, remove, scope and language passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
