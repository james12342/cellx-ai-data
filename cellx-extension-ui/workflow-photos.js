(() => {
  const button = document.getElementById("uploadPhotosBtn");
  const zh = () => window.CellI18n?.lang === "zh-CN";
  const t = (en, cn) => zh() ? cn : en;
  const isNode = node => node?.type === "trigger" &&
    (/upload/i.test(node.name) && /photo|image|picture/i.test(node.name) || /上传.*(图|照片)/.test(node.name));
  const uploadNode = () => {
    const selected=nodes.find(n=>n.id===selectedId);
    if(isNode(selected))return selected;
    const video=window.WorkflowVideo?.videoNode();
    return (video&&incomingNodes(video).find(isNode))||nodes.find(isNode);
  };
  const files = node => {
    try { const value = JSON.parse(node?.integrationSettings?.photoFilesJson || "[]");
      return Array.isArray(value) ? value.filter(f => /^[a-f0-9]{40}$/.test(f.id)) : [];
    } catch { return []; }
  };
  let target = null, workflowId = null, busy = false, generation = 0;
  const previews = new Map();
  const dialog = document.createElement("dialog");
  dialog.className = "photo-dialog";
  dialog.setAttribute("aria-labelledby", "photoDialogTitle");
  dialog.innerHTML = `<header><h2 id="photoDialogTitle"></h2><button type="button" class="photo-close"></button></header>
    <main><input type="file" multiple aria-label="Select product photos">
    <p class="photo-status" role="status" aria-live="polite"></p><div class="photo-list"></div></main>
    <footer><button type="button" class="photo-done"></button></footer>`;
  document.body.append(dialog);
  const picker = dialog.querySelector("input");
  const status = dialog.querySelector(".photo-status");
  const list = dialog.querySelector(".photo-list");
  const active = () => activeWorkflowId === workflowId && nodes.includes(target);
  const message = (text, error=false) => { status.textContent=text; status.dataset.error=String(error); };
  const setBusy = value => { busy=value; picker.disabled=value;
    list.querySelectorAll("button").forEach(b => { b.disabled=value; }); };
  function result(node) {
    const photos = files(node);
    const text = photos.length ? t(`${photos.length} photos uploaded.`, `已上传 ${photos.length} 张图片。`) :
      t("Upload product photos first.", "请先上传产品图片。");
    const state = photos.length ? "success" : "error";
    node.connection = { status:state, message:text };
    node.testResult = { status:state, message:text, input:{node:node.name},
      output:{ok:!!photos.length, event:"product.photos.uploaded", files:photos, rows:photos, count:photos.length} };
  }
  function save(photos) {
    if (!active()) throw new Error(t("The active workflow changed. Reopen Upload Photos.", "当前流程已切换，请重新打开上传窗口。"));
    target.integrationSettings = {...target.integrationSettings, photoFilesJson:JSON.stringify(photos)};
    result(target);
    saveWorkflowDraft();
    render();
    if (selectedId === target.id) renderIntegrationFields(target);
  }
  async function refresh() {
    const version = ++generation;
    list.replaceChildren();
    for (const file of files(target)) {
      const item=document.createElement("div"); item.className="photo-item";
      const img=document.createElement("img"); img.alt=file.name;
      const name=document.createElement("span"); name.textContent=file.name;
      const remove=document.createElement("button"); remove.type="button";
      remove.textContent=t("Remove", "移除"); remove.disabled=busy;
      remove.onclick=async () => {
        if (busy || !active()) return;
        setBusy(true);
        try {
          await workflowManagementFetch(`/photo-uploads/${file.id}`, {method:"DELETE"});
          previews.delete(file.id); save(files(target).filter(f=>f.id!==file.id));
          message(t("Photo removed.", "图片已移除。"));
        } catch(error) { message(error.message,true); }
        finally { setBusy(false); refresh(); }
      };
      item.append(img,name,remove); list.append(item);
      if (previews.has(file.id)) img.src=previews.get(file.id);
      else {
        workflowManagementFetch(`/photo-uploads/${file.id}`, {cache:"no-store"}).then(data => {
          if (version !== generation || !dialog.open) return;
          const url=`data:${data.file.mime_type};base64,${data.data}`;
          previews.set(file.id,url); img.src=url;
        }).catch(error => { if(version===generation) message(error.message,true); });
      }
    }
  }
  const read = file => new Promise((resolve,reject) => { const reader=new FileReader();
    reader.onload=()=>resolve(reader.result); reader.onerror=()=>reject(new Error("Could not read photo.")); reader.readAsDataURL(file); });
  picker.onchange=async () => {
    const selected=Array.from(picker.files || []); picker.value="";
    if (!selected.length || busy || !active()) return;
    setBusy(true);
    try {
      for (let i=0; i<selected.length; i++) {
        message(t(`Uploading ${i+1}/${selected.length}...`, `正在上传 ${i+1}/${selected.length}...`));
        const file=selected[i], url=await read(file);
        if (!active()) throw new Error("The active workflow changed.");
        const data=await workflowManagementFetch("/photo-uploads", {method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({name:file.name,mime_type:file.type,data:url.split(",")[1]})});
        previews.set(data.file.id,url); save([...files(target),data.file]);
      }
      message(t("Uploaded and saved. Close to continue.", "图片已上传并保存，可以关闭窗口继续。"));
    } catch(error) { message(error.message || t("Upload failed.", "上传失败。"),true); }
    finally { setBusy(false); refresh(); }
  };
  function close() { if(!busy) { dialog.close(); generation++; previews.clear(); } }
  dialog.querySelector(".photo-close").onclick=close;
  dialog.querySelector(".photo-done").onclick=close;
  dialog.addEventListener("cancel", event=>{ if(busy) event.preventDefault(); });
  dialog.addEventListener("close",()=>{ generation++; previews.clear(); });
  button.onclick=() => {
    target=uploadNode(); workflowId=activeWorkflowId; if(!target) return;
    if (!workflowManagementToken()) return;
    dialog.querySelector("h2").textContent=t("Product Photos", "产品图片");
    dialog.querySelector(".photo-close").textContent=t("Close", "关闭");
    dialog.querySelector(".photo-done").textContent=t("Done", "完成");
    message(t("Select product image files to upload.", "选择产品图片上传。"));
    dialog.showModal(); refresh();
  };
  window.WorkflowPhotos = {isNode, render() {
    const node=uploadNode(); button.hidden=!node;
    button.innerHTML=iconMarkup("lucide:upload", "Upload Photos", "photo-upload-icon");
    button.append(document.createTextNode(t("Upload Photos", "上传图片")+(files(node).length ? ` (${files(node).length})` : "")));
  }, async test(node) {
    if (!files(node).length) { result(node); return; }
    try {
      for (const file of files(node)) await workflowManagementFetch(`/photo-uploads/${file.id}`, {cache:"no-store"});
      result(node);
    } catch(error) {
      node.connection={status:"error",message:error.message};
      node.testResult={status:"error",message:error.message,input:{node:node.name},output:{ok:false,message:error.message}};
    }
  }};
  document.addEventListener("cell-language-change",()=>window.WorkflowPhotos.render());
  window.WorkflowPhotos.render();
})();
