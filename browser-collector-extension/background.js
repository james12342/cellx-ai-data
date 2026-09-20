function collectVisiblePage(){
 const visible=el=>!!(el.getClientRects().length)&&getComputedStyle(el).visibility!=='hidden'&&getComputedStyle(el).display!=='none';
 const root=document.querySelector('main,[role="main"]')||document.body;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const parts=[];let count=0,n;
 while((n=walker.nextNode())&&count<60000){const p=n.parentElement;if(!p||p.closest('script,style,noscript,input,textarea,select,[contenteditable],nav,header,footer')||!visible(p))continue;const t=n.textContent.trim();if(t){parts.push(t);count+=t.length+1;}}
 const text=parts.join('\n').slice(0,60000);
 const links=Array.from(root.querySelectorAll('a[href]')).filter(visible).slice(0,500).map(a=>({text:a.innerText.trim().slice(0,200),url:a.href})).filter(a=>/^https?:/.test(a.url));
 const next=Array.from(document.querySelectorAll('a[href]')).filter(visible).filter(a=>!a.hasAttribute('download')&&a.getAttribute('aria-disabled')!=='true').find(a=>a.rel.split(/\s+/).includes('next')||/^(next(?:\s+page)?|下一页|下页)\s*[›»→>]?$/.test((a.getAttribute('aria-label')||a.innerText).trim().toLowerCase()));
 const blocked=/verify (you are|that you are) human|checking your browser|complete the captcha|验证您是人类|人机验证/i.test(text);
 return {url:location.href,title:document.title,text,links,truncated:count>=60000,blocked,next:next?next.href:null};
}
let navigating=false;
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 (async()=>{
  if(sender.id!==chrome.runtime.id||!sender.url?.startsWith('https://app.cellaidata.com/agent/'))throw Error('Only the Agent page can request collection.');
  const {chosen}=await chrome.storage.session.get('chosen');
  if(!chosen||chosen.expires<Date.now())throw Error('Open the helper on the target website and choose this page. Page access expires after one hour.');
  const tab=await chrome.tabs.get(chosen.tabId);
  if(tab.url&&new URL(tab.url).origin!==chosen.origin)throw Error('The page moved to another site. Choose the target page again.');
  if(message.action==='status')return {ok:true,title:chosen.title,url:tab.url||chosen.url};
  if(!['capture','next'].includes(message.action))throw Error('Unsupported operation');
  const [{result:page}]=await chrome.scripting.executeScript({target:{tabId:chosen.tabId},func:collectVisiblePage});
  if(new URL(page.url).origin!==chosen.origin)throw Error('Page origin changed.');
  if(message.action==='capture')return {ok:true,page};
  if(navigating)throw Error('Pagination is in progress.');
  if(page.blocked)throw Error('The website requires verification. Complete it in your browser and retry.');
  if(!page.next)return {ok:true,advanced:false,message:'No next-page link found. Collection stopped.'};
  const next=new URL(page.next);
  if(next.origin!==chosen.origin||!['http:','https:'].includes(next.protocol)||next.username||next.password||/logout|signout|delete|remove|checkout|purchase|unsubscribe/i.test(next.pathname))throw Error('The next-page link could not be validated. Navigate manually.');
  if(next.href===page.url)return {ok:true,advanced:false};
  navigating=true;
  try{
   await chrome.tabs.update(chosen.tabId,{url:next.href});
   for(let i=0;i<60;i++){await new Promise(r=>setTimeout(r,500));const t=await chrome.tabs.get(chosen.tabId);if(t.status==='complete'){if(t.url&&new URL(t.url).origin!==chosen.origin)throw Error('Pagination left the original website. Collection stopped.');await new Promise(r=>setTimeout(r,1000));return {ok:true,advanced:true};}}
   throw Error('Page loading timed out. Check the target tab.');
  }finally{navigating=false;}
 })().then(respond,e=>respond({ok:false,message:e.message}));return true;
});
