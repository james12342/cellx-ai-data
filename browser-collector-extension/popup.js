const status=document.getElementById('status');
document.getElementById('choose').onclick=async()=>{
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const u=new URL(tab.url);if(!['http:','https:'].includes(u.protocol)||u.hostname==='app.cellaidata.com')throw Error('Open the website you want to collect, then choose this page.');
  await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>document.title});
  await chrome.storage.session.set({chosen:{tabId:tab.id,origin:u.origin,url:tab.url,title:tab.title,expires:Date.now()+60*60*1000}});
  status.textContent='Page selected. Return to Web Collector or Voice Builder to specify fields.';
 }catch(e){status.textContent=e.message;}
};
document.getElementById('clear').onclick=async()=>{await chrome.storage.session.remove('chosen');status.textContent='Page disconnected.';};
