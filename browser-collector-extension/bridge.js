// Only the Agent origin receives this content script; page selection happens in the extension popup.
window.addEventListener('message',async(event)=>{
 const m=event.data;
 if(event.source!==window||event.origin!=='https://app.cellaidata.com'||m?.channel!=='cell-browser-collector-request'||typeof m.id!=='string'||m.id.length>100)return;
 if(!['status','capture','next'].includes(m.action))return;
 try{
  const result=await chrome.runtime.sendMessage({action:m.action});
  window.postMessage({channel:'cell-browser-collector-response',id:m.id,...result},event.origin);
 }catch(e){window.postMessage({channel:'cell-browser-collector-response',id:m.id,ok:false,message:e.message},event.origin);}
});
