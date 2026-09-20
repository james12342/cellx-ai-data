(() => {
  // Debounce whole batches and serialize updates per video node. Old responses never apply.
  class ProductAnalysisQueue {
    constructor({read,send,apply,status,delay=650}){Object.assign(this,{read,send,apply,status,delay});this.states=new Map();this.requests=new Map();}
    invalidate(node){const s=this.states.get(node)||{version:0,running:false};s.version++;s.ready=false;clearTimeout(s.timer);this.states.set(node,s);return s;}
    schedule(node){const s=this.invalidate(node);s.ready=true;s.timer=setTimeout(()=>this.run(node),this.delay);}
    async run(node){
      const s=this.states.get(node);if(!s||s.running||!s.ready)return;
      const snapshot=this.read(node);if(!snapshot||!snapshot.photo_ids.length)return;
      const version=s.version;s.running=true;s.ready=false;this.status(node,'loading');
      try{
        const requestKey=snapshot.request_key||snapshot.key;
        let pending=this.requests.get(requestKey);
        if(!pending){pending=this.send(snapshot);this.requests.set(requestKey,pending);pending.finally(()=>this.requests.delete(requestKey)).catch(()=>{});}
        const result=await pending,current=this.read(node);
        if(s.version===version&&current?.key===snapshot.key){this.apply(node,result,snapshot);this.status(node,'ready');}
      }catch(error){if(s.version===version&&this.read(node)?.key===snapshot.key)this.status(node,'failed',error.message);}
      finally{s.running=false;if(s.version!==version&&s.ready)s.timer=setTimeout(()=>this.run(node),this.delay);}
    }
  }
  window.ProductAnalysisQueue=ProductAnalysisQueue;
  if(!window.WorkflowVideo||typeof document==='undefined')return;
  const video=window.WorkflowVideo,dialog=document.querySelector('.video-dialog');
  const t=(en,cn)=>window.CellI18n?.lang==='zh-CN'?cn:en;
  const options=n=>{try{return JSON.parse(n.integrationSettings?.inputJson||'{}').options||{};}catch{return {};}};
  const setOptions=(n,value)=>{n.integrationSettings={...n.integrationSettings,inputJson:JSON.stringify({options:value})};if(nodes.includes(n))saveWorkflowDraft();};
  const photos=n=>{const upstream=incomingNodes(n).find(p=>window.WorkflowPhotos?.isNode(p));try{const all=JSON.parse(upstream?.integrationSettings?.photoFilesJson||'[]'),opts=options(n);return opts.mode==='portrait_storyboard'&&opts.portrait_photo_id?[...all.filter(p=>p.id===opts.portrait_photo_id),...all.filter(p=>p.id!==opts.portrait_photo_id)]:all;}catch{return [];}};
  const current=()=>dialog.open?video.editorNode():null;
  const manualRequests=new WeakSet();
  const field=dialog.querySelector('.product-info'),eco=dialog.querySelector('.eco-script');
  const panel=document.createElement('section');panel.className='product-analysis-panel';
  panel.innerHTML='<h3>图片分析与分镜 / Image analysis & storyboard</h3><label><input class="analysis-auto" type="checkbox" checked> 上传后自动分析整批图片 / Auto-analyze uploads</label><label>文案语言 / Copy language<select class="analysis-language"><option value="auto">跟随配音或界面 / Follow voice or interface</option><option value="zh-CN">中文</option><option value="en">English</option></select></label><p class="analysis-status" role="status" aria-live="polite"></p><button class="analysis-retry" type="button">分析 / 重试 · Analyze / Retry</button><button class="analysis-apply" type="button" hidden>使用这份AI草稿 / Use AI draft</button><button class="analysis-economy" type="button" hidden>用于经济广告分镜 / Use in Economy Ad</button><small>OpenAI 图片分析按用量计费。每次整批调用，结果可编辑；不会自动启动视频。多图分镜用于经济广告，5090数字人口播仍只使用一张人像。</small><details class="analysis-draft" hidden><summary>查看生成的产品详情 / View generated details</summary><pre></pre></details><ol class="analysis-scenes"></ol>';
  dialog.querySelector('.economy-panel').before(panel);
  panel.querySelector('small').textContent='按目标时长生成并用所选声线配音测时；必要时最多修订一次文案、小幅调整语速。OpenAI按用量收费，口播文本会发送到Edge配音服务。不会自动生成视频。5090单人像口播仍限20秒。 / Targets the selected duration and measures synthesized speech; up to one copy revision. No automatic video generation.';
  const timingStatus=document.createElement('p');timingStatus.className='analysis-timing';timingStatus.setAttribute('role','status');panel.querySelector('.analysis-status').after(timingStatus);
  const status=panel.querySelector('.analysis-status'),sceneList=panel.querySelector('.analysis-scenes');
  const label=s=>({loading:t('Analyzing all images once…','正在整批分析图片并生成分镜……'),pending:t('Photos changed; preparing analysis…','图片已变化，正在准备分析……'),ready:t('Draft ready; review the visible facts and narration.','文案已生成，请核对产品事实和口播。'),failed:t('Analysis failed. Your edits were kept. Click Retry.','分析失败，已保留你的编辑，请点击重试。'),stale:t('Photos changed. Analyze again or edit the matching scenes.','图片已变化，请重新分析或编辑对应分镜。'),off:t('Automatic analysis is off. Manual editing is available.','已关闭自动分析，可手动编辑。')})[s]||t('Upload photos to generate details and ordered narration.','上传图片后自动生成产品详情及有序口播。');
  function update(n,state,message){
    if(['ready','failed'].includes(state))manualRequests.delete(n);
    const opts=options(n);opts.product_analysis={...opts.product_analysis,state,message:message||''};setOptions(n,opts);
    document.dispatchEvent(new CustomEvent('cell-photo-analysis-status',{detail:{node:incomingNodes(n).find(p=>window.WorkflowPhotos?.isNode(p)),message:message||label(state)}}));
    if(current()===n)render(n);
  }
  function read(n,manual=false){
    if(!nodes.includes(n))return null;
    const opts=options(n);if(opts.auto_analyze===false&&!manual&&!manualRequests.has(n))return null;
    const ids=photos(n).map(p=>p.id);
    const language=opts.copy_language&&opts.copy_language!=='auto'?opts.copy_language:opts.voice&&opts.voice!=='none'?(opts.voice.startsWith('zh')?'zh-CN':'en'):(window.CellI18n?.lang==='zh-CN'?'zh-CN':'en');
    const duration=Math.max(15,Math.min(opts.mode==='portrait_storyboard'?300:60,Math.round(Number(opts.duration_seconds)||30)));
    const voice=opts.voice==='none'?'none':(language==='zh-CN'?'zh':'en')+'-'+(opts.voice?.endsWith('male')&&!opts.voice?.endsWith('female')?'male':'female');
    const portrait=opts.mode==='portrait_storyboard'?(opts.portrait_photo_id||''):'';
    const notes=opts.product_info===opts.product_analysis?.appliedProduct?(opts.product_analysis?.source_notes||''):(opts.product_info||'');
    return {photo_ids:ids,language,voice,portrait_photo_id:portrait,product_notes:notes,duration_seconds:duration,key:JSON.stringify([ids,language,duration,voice,portrait]),request_key:JSON.stringify([ids,language,duration,voice,portrait,notes]),product_info:opts.product_info||'',product_revision:opts.product_revision||0,
      narration:opts.narration||'',narration_revision:opts.narration_revision||0};
  }
  function apply(n,result,snapshot,force=false){
    const opts=options(n),previous=opts.product_analysis||{};
    if(JSON.stringify(result.photo_ids)!==JSON.stringify(photos(n).map(p=>p.id)))return;
    const now=read(n,true);if((result.portrait_photo_id||'')!==now.portrait_photo_id||result.duration_seconds!==now.duration_seconds||result.language!==now.language||(result.voice&&result.voice!==now.voice))return;
    const copySafe=force||((opts.product_info||'')===snapshot.product_info&&(opts.product_revision||0)===snapshot.product_revision&&(!opts.product_info||opts.product_info===previous.appliedProduct));
    if(copySafe)opts.product_info=result.product_info;
    const old=new Map((opts.storyboard_scenes||[]).map(s=>[s.photo_id,s]));
    opts.storyboard_scenes=result.scenes.map(s=>!force&&old.get(s.photo_id)?.edited?old.get(s.photo_id):{...s,edited:false});
    opts.storyboard_narration=opts.storyboard_scenes.map(s=>s.narration).join('\n');
    const speechSafe=force||((opts.narration||'')===snapshot.narration&&(opts.narration_revision||0)===snapshot.narration_revision&&(!opts.narration||opts.narration===previous.appliedNarration));
    const useSpeech=['economy','portrait_storyboard'].includes(opts.mode)&&(speechSafe||(opts.mode!=='portrait_storyboard'&&opts.storyboard_linked))&&!opts.clip_id;
    if(useSpeech){opts.narration=opts.storyboard_narration;opts.storyboard_linked=true;if(result.voice)opts.voice=result.voice;}
    opts.product_analysis={...previous,state:'ready',draft:result,key:snapshot.key,message:'',source_notes:snapshot.product_notes||'',
      appliedProduct:copySafe?result.product_info:previous.appliedProduct,
      appliedNarration:useSpeech?opts.narration:previous.appliedNarration,
      keptEdits:!copySafe||(['economy','portrait_storyboard'].includes(opts.mode)&&!useSpeech)};
    setOptions(n,opts);sync(n);
  }
  const queue=new ProductAnalysisQueue({read,apply,status:update,send:snapshot=>workflowManagementFetch('/promo-videos/product-brief',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({purpose:'storyboard',photo_ids:snapshot.photo_ids,language:snapshot.language,voice:snapshot.voice,portrait_photo_id:snapshot.portrait_photo_id,product_info:snapshot.product_notes,duration_seconds:snapshot.duration_seconds})})});
  function sync(n){if(current()!==n)return;const opts=options(n);field.value=opts.product_info||'';if(['economy','portrait_storyboard'].includes(opts.mode)){eco.value=opts.narration||'';if(opts.voice){dialog.querySelector('.eco-voice').value=opts.voice;if(opts.mode==='portrait_storyboard')dialog.querySelector('.portrait-voice').value=opts.voice;}}video.scenePreview();render(n);}
  function render(n){
    if(!n)return;const opts=options(n),analysis=opts.product_analysis||{};
    const combined=opts.mode==='portrait_storyboard',presenter=dialog.querySelector('.presenter-narration');
    const listPhotos=photos(n),saved=opts.storyboard_scenes||[];
    const aligned=JSON.stringify(saved.map(s=>s.photo_id))===JSON.stringify(listPhotos.map(p=>p.id))&&saved.map(s=>s.narration).join('\n')===(opts.narration||'');
    const lines=aligned?saved.map(s=>s.narration):(opts.narration||'').split('\n').map(s=>s.trim());
    const malformed=combined&&lines.length>listPhotos.length&&listPhotos.length>0;
    if(combined&&!malformed){
      const old=new Map((opts.storyboard_scenes||[]).map(s=>[s.photo_id,s]));
      opts.storyboard_scenes=listPhotos.map((p,i)=>{const s=old.get(p.id)||{};return {...s,photo_id:p.id,narration:lines[i]||'',edited:!!s.edited||(!!s.narration&&s.narration!==(lines[i]||''))};});
      opts.storyboard_narration=opts.storyboard_scenes.map(s=>s.narration).join('\n');opts.storyboard_linked=true;
      setOptions(n,opts);
    }
    if(presenter){
      presenter.hidden=!combined;
      (combined?presenter.querySelector('.presenter-scene-editor'):panel).append(sceneList);
      sceneList.hidden=malformed;
      const rawLabel=eco.closest('label');
      if(malformed){presenter.querySelector('.presenter-scene-editor').append(rawLabel);rawLabel.hidden=false;}
      else {dialog.querySelector('.eco-write').before(rawLabel);rawLabel.hidden=false;}
      presenter.querySelector('.presenter-editor-help').textContent=malformed?'口播行数多于图片数。请在下面保留原文的口播框中调整为每张图片一行，再保存；当前没有删除任何文字。':'第1镜是选定人像的开场口播；后面的讲解按图片顺序播放。这里的文字就是生成时提交的口播。';
      dialog.querySelector('.economy-panel').hidden=combined||opts.mode!=='economy';
    }
    panel.querySelector('small').textContent=opts.mode==='portrait_storyboard'?'按所选时长生成草稿；点击生成视频后，由5090实际配音测时。未修改的AI稿必要时最多自动修订两次，并小幅调整语速；手写稿不自动改写。OpenAI按用量收费，文字发送到Edge配音服务。':'按目标时长生成并用所选声线配音测时；必要时最多修订一次文案、小幅调整语速。OpenAI按用量收费，口播文本会发送到Edge配音服务。不会自动生成视频。';
    panel.querySelector('.analysis-auto').checked=opts.auto_analyze!==false;
    panel.querySelector('.analysis-language').value=opts.copy_language||'auto';
    status.textContent=label(analysis.state)+(analysis.message?' '+analysis.message:'')+(analysis.keptEdits?t(' Your manual edits were kept; the new draft is available below.',' 已保留手动编辑，可查看或采用新草稿。'):'');
    panel.querySelector('.analysis-retry').disabled=analysis.state==='loading'&&!!queue.states.get(n)?.running;
    const ids=photos(n).map(p=>p.id),draftResult=analysis.draft,snapshot=read(n,true),valid=draftResult&&JSON.stringify(draftResult.photo_ids)===JSON.stringify(ids)&&(draftResult.portrait_photo_id||'')===snapshot.portrait_photo_id&&draftResult.duration_seconds===snapshot.duration_seconds&&draftResult.language===snapshot.language&&(!draftResult.voice||draftResult.voice===snapshot.voice);
    const timing=draftResult?.timing;
    const edited=(opts.storyboard_scenes||[]).some(s=>s.edited)||opts.storyboard_narration!==draftResult?.narration||(['economy','portrait_storyboard'].includes(opts.mode)&&opts.narration!==draftResult?.narration);
    timingStatus.textContent=!valid&&draftResult?t('Duration, voice, language or photos changed. Regenerate to measure the new narration.','时长、声线、语言或图片已变化，请重新生成并测时。'):timing?(edited?t('Narration was edited; the previous measured duration no longer applies.','口播已手动修改，之前的配音实测时长不再适用。'):(timing.verified?t(`Target ${timing.target_seconds}s · measured speech ${timing.measured_seconds}s · speed ${timing.tempo.toFixed(2)}×. `,`目标 ${timing.target_seconds} 秒 · 配音实测 ${timing.measured_seconds} 秒 · 语速 ${timing.tempo.toFixed(2)} 倍。`):(timing.verification_location==='gpu-worker'?t('Speech will be measured and matched on the 5090. ','配音将在5090上测时并匹配目标时长。 '):t('Silent mode: speech duration is only estimated. ','无配音模式：只有时长估算。 ')))+(draftResult.timing_warning||'')):t('Speech timing will be measured after generation.','生成后将实际合成配音并测量时长。');
    panel.querySelector('.analysis-apply').hidden=!valid||combined;
    if(presenter){
      const pending=valid&&opts.narration!==draftResult.narration;
      presenter.querySelector('.presenter-use').hidden=!pending;
      presenter.querySelector('.presenter-draft-status').textContent=pending?'有一份AI草稿尚未应用。下面编辑框仍是本次要提交的原文；点击“使用这份AI草稿”才会替换。':analysis.state==='loading'?'正在起草，当前口播保持不变。':opts.narration?.trim()?'下方显示本次将提交的口播，可逐镜修改并保存。':'尚未填写口播。可直接在下方输入，或点击“AI 写分镜口播”。';
      const preview=presenter.querySelector('.presenter-draft-preview');preview.hidden=!pending;
      preview.querySelector('pre').textContent=pending?draftResult.scenes.map((s,i)=>`${i===0?'开场口播':`第${i+1}镜讲解`}：${s.narration}`).join('\n\n'):'';
    }
    panel.querySelector('.analysis-economy').hidden=opts.mode==='portrait_storyboard'||!valid||!ids.length||(opts.storyboard_scenes||[]).length!==ids.length;
    const draft=panel.querySelector('.analysis-draft');draft.hidden=!valid;draft.querySelector('pre').textContent=valid?analysis.draft.product_info:'';
    sceneList.replaceChildren();const byId=new Map((opts.storyboard_scenes||[]).map(s=>[s.photo_id,s]));
    photos(n).forEach((photo,index)=>{
      const scene=byId.get(photo.id),li=document.createElement('li');
      const title=document.createElement('strong');title.textContent=(combined?(index===0?'第1镜 · 数字人开场口播':'第'+(index+1)+'镜 · 图片讲解')+' — ':`${index+1}. `)+(photo.name||'Photo');
      const desc=document.createElement('p');desc.textContent=(scene?.visual_description||t('Waiting for image analysis.','等待图片分析。'))+(valid&&!scene?.edited&&scene?.duration_seconds?t(` · planned ${scene.duration_seconds}s`,` · 分镜计划 ${scene.duration_seconds} 秒`):'');
      const input=document.createElement('textarea');input.rows=3;input.maxLength=combined?(index===0?100:6000):1200;input.value=scene?.narration||'';input.setAttribute('aria-label',combined?(index===0?'数字人开场口播':`第${index+1}镜图片讲解`):t(`Photo ${index+1} narration`,`第${index+1}镜口播`));
      input.oninput=()=>{
        const latest=options(n),map=new Map((latest.storyboard_scenes||[]).map(s=>[s.photo_id,s]));
        map.set(photo.id,{...(map.get(photo.id)||{photo_id:photo.id,visual_description:''}),narration:input.value,edited:true});
        latest.storyboard_scenes=photos(n).map(p=>map.get(p.id)).filter(Boolean);
        latest.storyboard_narration=latest.storyboard_scenes.map(s=>s.narration).join('\n');
        latest.narration_revision=(latest.narration_revision||0)+1;
        if(['economy','portrait_storyboard'].includes(latest.mode)&&!latest.clip_id){latest.narration=latest.storyboard_narration;latest.storyboard_linked=true;eco.value=latest.narration;}
        setOptions(n,latest);video.scenePreview();timingStatus.textContent=t('Narration was edited; regenerate to remeasure.','口播已修改，需要重新测时。');
        if(combined)presenter.querySelector('.presenter-draft-status').textContent='已更新本次要提交的口播；点击“保存广告方案”可保存，生成前会在5090重新测时。';
      };
      li.append(title,desc,input);sceneList.append(li);
    });
  }
  function changed(n,phase){
    manualRequests.delete(n);
    queue.invalidate(n);
    if(phase==='begin'){update(n,'pending');return;}
    const opts=options(n),ids=photos(n).map(p=>p.id),map=new Map((opts.storyboard_scenes||[]).map(s=>[s.photo_id,s]));
    opts.storyboard_scenes=ids.map(id=>map.get(id)).filter(Boolean);
    opts.storyboard_narration=opts.storyboard_scenes.map(s=>s.narration).join('\n');
    if(['economy','portrait_storyboard'].includes(opts.mode)&&!opts.clip_id&&(opts.storyboard_linked||opts.narration===opts.product_analysis?.appliedNarration)){opts.narration=opts.storyboard_narration;if(opts.product_analysis)opts.product_analysis.appliedNarration=opts.narration;}
    setOptions(n,opts);sync(n);
    update(n,opts.auto_analyze===false?'off':ids.length?'pending':'stale');
    if(opts.auto_analyze!==false&&ids.length)queue.schedule(n);
  }
  document.addEventListener('cell-photos-changed',event=>{
    if(event.detail.workflowId!==activeWorkflowId)return;
    nodes.filter(n=>video.isNode(n)&&incomingNodes(n).includes(event.detail.node)).forEach(n=>changed(n,event.detail.phase));
  });
  field.addEventListener('input',()=>{const n=current();if(!n)return;video.saveOptions();const opts=options(n);opts.product_revision=(opts.product_revision||0)+1;setOptions(n,opts);});
  eco.addEventListener('input',()=>{
    const n=current();if(!n)return;video.saveOptions();const opts=options(n);opts.narration_revision=(opts.narration_revision||0)+1;
    const lines=eco.value.split('\n').map(s=>s.trim()).filter(Boolean),ids=photos(n).map(p=>p.id);
    opts.storyboard_linked=lines.length===ids.length;
    if(opts.storyboard_linked){const map=new Map((opts.storyboard_scenes||[]).map(s=>[s.photo_id,s]));opts.storyboard_scenes=ids.map((id,i)=>({...map.get(id),photo_id:id,narration:lines[i],edited:true}));opts.storyboard_narration=eco.value;}
    setOptions(n,opts);timingStatus.textContent=t('Narration was edited; regenerate to remeasure.','口播已修改，需要重新测时。');
  });
  panel.querySelector('.analysis-auto').onchange=event=>{const n=current();if(!n)return;const opts=options(n);opts.auto_analyze=event.target.checked;setOptions(n,opts);queue.invalidate(n);update(n,opts.auto_analyze?'stale':'off');};
  panel.querySelector('.analysis-language').onchange=event=>{const n=current();if(!n)return;const opts=options(n);opts.copy_language=event.target.value;setOptions(n,opts);changed(n,'commit');};
  function request(n){if(!n)return;manualRequests.add(n);queue.schedule(n);update(n,'pending');(options(n).mode==='portrait_storyboard'?dialog.querySelector('.presenter-narration'):panel).scrollIntoView({block:'nearest'});}
  panel.querySelector('.analysis-retry').onclick=()=>request(current());
  panel.querySelector('.analysis-apply').onclick=()=>{const n=current(),snapshot=n&&read(n,true),draft=n&&options(n).product_analysis?.draft;if(snapshot&&draft)apply(n,draft,snapshot,true);};
  panel.querySelector('.analysis-economy').onclick=()=>{
    const n=current();if(!n)return;const opts=options(n),ids=photos(n).map(p=>p.id);
    if(JSON.stringify((opts.storyboard_scenes||[]).map(s=>s.photo_id))!==JSON.stringify(ids))return;
    const snapshot=read(n,true),draft=opts.product_analysis?.draft;if(!draft||draft.duration_seconds!==snapshot.duration_seconds)return;
    opts.mode='economy';opts.narration=opts.storyboard_narration;opts.storyboard_linked=true;opts.clip_id='';
    if(opts.product_analysis)opts.product_analysis.appliedNarration=opts.narration;
    const language=read(n,true)?.language||'en';if(!opts.voice||opts.voice==='none'||!opts.voice.startsWith(language==='zh-CN'?'zh':'en'))opts.voice=language==='zh-CN'?'zh-male':'en-male';
    setOptions(n,opts);dialog.querySelector('.mode').value='economy';dialog.querySelector('.duration').value=opts.duration_seconds;dialog.querySelector('.eco-voice').value=opts.voice;dialog.querySelector('.eco-clip').checked=false;video.modeChanged();sync(n);
  };
  document.getElementById('workflowVideoBtn').addEventListener('click',()=>{const n=current();if(n){render(n);if(['pending','loading'].includes(options(n).product_analysis?.state)&&!queue.states.get(n)?.running)queue.schedule(n);}});
  document.addEventListener('cell-language-change',()=>{const n=current();if(n){render(n);const opts=options(n);if(!opts.copy_language||opts.copy_language==='auto'){queue.invalidate(n);update(n,'stale');}}});
  for(const selector of ['.eco-voice','.portrait-voice','.portrait-photo','.duration'])dialog.querySelector(selector).addEventListener('change',()=>{const n=current();if(n){video.saveOptions();changed(n,'commit');}});
  dialog.querySelector('.mode').addEventListener('change',()=>{const n=current();if(n){video.saveOptions();queue.invalidate(n);render(n);if(options(n).mode==='portrait_storyboard')changed(n,'commit');}});
  dialog.querySelector('.duration').addEventListener('input',()=>{const n=current();if(n){video.saveOptions();queue.invalidate(n);update(n,'stale',t('Duration changed; new narration needs timing verification.','时长已更改，新口播需要重新测时。'));}});
  function hasTiming(n){const opts=options(n),draft=opts.product_analysis?.draft,snapshot=read(n,true);return !!(['economy','portrait_storyboard'].includes(opts.mode)&&draft?.timing?.matched&&(draft.portrait_photo_id||'')===snapshot.portrait_photo_id&&draft.voice===snapshot.voice&&draft.duration_seconds===snapshot.duration_seconds&&opts.narration===draft.narration&&JSON.stringify(draft.photo_ids)===JSON.stringify(photos(n).map(p=>p.id)));}
  window.WorkflowProductAnalysis={queue,changed,read,apply,render,request,hasTiming,validate(n){
    const opts=options(n);if(!['economy','portrait_storyboard'].includes(opts.mode)||!opts.storyboard_linked)return;
    const ids=photos(n).map(p=>p.id),scenes=opts.storyboard_scenes||[];
    if(JSON.stringify(scenes.map(s=>s.photo_id))!==JSON.stringify(ids)||scenes.some(s=>!s.narration?.trim()))throw Error(t('Wait for every photo to have matching narration, or finish editing the scenes.','请等待每张图片的分镜口播生成，或补齐缺少的口播。'));
    const draft=opts.product_analysis?.draft;
    if(opts.mode==='portrait_storyboard'&&draft&&opts.narration===draft.narration){const snapshot=read(n,true);if(draft.voice!==snapshot.voice||draft.duration_seconds!==snapshot.duration_seconds||(draft.portrait_photo_id||'')!==snapshot.portrait_photo_id||JSON.stringify(draft.photo_ids)!==JSON.stringify(ids))throw Error('时长、声线或图片已更改。请点击“AI 写分镜口播”，检查并使用新草稿后生成；原稿已保留。');}
    if(opts.mode!=='portrait_storyboard'&&draft?.timing&&opts.narration===draft.narration&&read(n,true).voice!=='none'&&!hasTiming(n))throw Error(t('Regenerate narration for the selected duration and voice before rendering.','请按当前时长和声线重新生成并校验口播后再合成。'));
  }};
})();
