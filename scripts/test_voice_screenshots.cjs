const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<textarea id="prompt"></textarea><button id="voiceScreenshotBtn"></button><button id="voiceSendBtn"></button><div id="voiceScreenshots"></div>',{runScripts:'outside-only',url:'https://test.local'});
 const w=dom.window;
 w.Element.prototype.replaceChildren=function(...c){this.textContent='';this.append(...c);};
 w.HTMLCanvasElement.prototype.getContext=()=>({fillRect(){},drawImage(){}});
 w.HTMLCanvasElement.prototype.toDataURL=()=> 'data:image/jpeg;base64,/9j/fixture';
 w.Image=class{naturalWidth=100;naturalHeight=50;async decode(){}};
 let status='', sent=[], requests=[], failed=false;
 const prompt=w.document.querySelector('textarea');prompt.value='What should I change?';
 Object.assign(w,{CellI18n:{lang:'en'},iconMarkup:()=>'',realtimeVoice:null,
 aiVoicePromptEl:prompt,apiBase:'/ext-api',aiVoiceHeaders:()=>({'X-Workflow-Admin-Token':'test'}),
 setAiVoiceStatus:x=>status=x,voiceLine:(role,text)=>sent.push({role,text}),voiceSend:(_s,event)=>sent.push(event),
 fetch:async(url,options)=>{requests.push(JSON.parse(options.body));return {ok:!failed,json:async()=>failed?{ok:false,message:'Failed'}:{ok:true,analysis:'The screenshot shows a workflow.'}};},
 AbortSignal:{timeout:()=>null}});
 w.eval(fs.readFileSync('cellx-extension-ui/voice-screenshots.js','utf8'));
 const picker=w.document.querySelector('input');
 const select=async(files)=>{Object.defineProperty(picker,'files',{value:files,configurable:true});await picker.onchange();};
 const file=()=>new w.File(['png'],'screen.png',{type:'image/png'});
 assert.equal(w.document.querySelector('#voiceSendBtn').disabled,true);
 await select([file()]);
 assert.equal(w.VoiceScreenshots.images().length,1);assert.equal(w.document.querySelectorAll('.voice-screenshot').length,1);
 assert.equal(w.document.querySelector('#voiceSendBtn').disabled,false);
 assert.equal(requests.length,0);
 await w.VoiceScreenshots.send();
 assert.equal(requests[0].screenshots.length,1);assert.equal(requests[0].prompt,'What should I change?');assert.equal(prompt.value,'');
 assert.equal(sent[1].role,'AI');assert.equal(w.VoiceScreenshots.images().length,1);
 failed=true;prompt.value='Retry question';await w.VoiceScreenshots.send();assert.equal(prompt.value,'Retry question');assert.equal(status,'Failed');failed=false;
 w.realtimeVoice={channel:{readyState:'open'}};await w.VoiceScreenshots.send();
 assert(sent.some(e=>e.type==='conversation.item.create'));assert(sent.some(e=>e.type==='response.create'));
 await select([file(),file(),file()]);assert.equal(w.VoiceScreenshots.images().length,1);
 await select([new w.File(['svg'],'bad.svg',{type:'image/svg+xml'})]);assert.equal(w.VoiceScreenshots.images().length,1);
 w.document.querySelector('.voice-screenshot button').click();assert.equal(w.VoiceScreenshots.images().length,0);
 const paste=(files,text='')=>{
   const event=new w.Event('paste',{bubbles:true,cancelable:true});
   Object.defineProperty(event,'clipboardData',{value:{items:files.map(f=>({kind:'file',type:f.type,getAsFile:()=>f})),getData:()=>text}});
   prompt.dispatchEvent(event);return event;
 };
 assert.equal(paste([],'normal text').defaultPrevented,false);
 prompt.value='question: ';prompt.setSelectionRange(prompt.value.length,prompt.value.length);
 const pasted=paste([file()],'see this');assert.equal(pasted.defaultPrevented,true);
 await new Promise(resolve=>setTimeout(resolve,40));
 assert.equal(w.VoiceScreenshots.images().length,1);assert.equal(prompt.value,'question: see this');
 assert.equal(w.document.querySelector('.voice-composer #voiceScreenshotBtn')!==null,true);
 assert.equal(w.document.querySelector('#voiceScreenshotBtn').textContent,'');
 w.CellI18n.lang='zh-CN';w.VoiceScreenshots.render();assert.match(w.document.querySelector('#voiceScreenshotBtn').getAttribute('aria-label'),/添加截图/);
 dom.window.close();console.log('Screenshot UI: attach, preview, no auto-send, offline analysis, voice context, retry, remove, limits and Chinese passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
