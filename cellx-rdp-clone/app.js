const modules = [
  { id: "dashboard", title: "首页", icon: "01", desc: "系统运行概览" },
  { id: "pageConfig", title: "配置管理", icon: "02", desc: "页面、字段、附属表配置" },
  { id: "mapConfig", title: "地图配置", icon: "03", desc: "地图页面与关联表" },
  { id: "reportConfig", title: "报表配置", icon: "04", desc: "可视化报表与筛选条件" },
  { id: "release", title: "发布记录", icon: "05", desc: "页面发布与版本回滚" },
  { id: "pageRuntime", title: "页面运行", icon: "06", desc: "动态表单、列表、详情" },
  { id: "authCenter", title: "授权中心", icon: "07", desc: "License、Token、设备绑定" },
  { id: "systemUser", title: "用户管理", icon: "08", desc: "账号、部门、角色分配" },
  { id: "systemRole", title: "角色管理", icon: "09", desc: "权限菜单与数据范围" },
  { id: "systemDict", title: "字典管理", icon: "10", desc: "字典类型与数据项" },
  { id: "systemMenu", title: "菜单管理", icon: "11", desc: "路由、按钮、图标配置" },
  { id: "monitorJob", title: "定时任务", icon: "12", desc: "调度任务和执行日志" },
  { id: "monitorServer", title: "服务监控", icon: "13", desc: "服务版本、数据库版本" },
  { id: "toolGen", title: "代码生成", icon: "14", desc: "导入表、生成配置、生成代码" },
  { id: "assistant", title: "小赖助手", icon: "15", desc: "自然语言创建页面和字段" },
  { id: "profile", title: "个人中心", icon: "16", desc: "资料、头像、密码" }
];

const groups = [
  { title: "首页", children: ["dashboard"] },
  { title: "页面生成器", children: ["pageConfig", "mapConfig", "reportConfig", "release", "pageRuntime", "assistant"] },
  { title: "系统管理", children: ["systemUser", "systemRole", "systemDict", "systemMenu"] },
  { title: "系统监控", children: ["monitorJob", "monitorServer"] },
  { title: "系统工具", children: ["toolGen"] },
  { title: "授权服务", children: ["authCenter"] },
  { title: "个人中心", children: ["profile"] }
];

const rows = {
  pages: [
    ["学生管理", "student", "列表页面", "已发布", "2026-08-18"],
    ["班级管理", "class", "树页面", "已发布", "2026-08-16"],
    ["商城订单", "shop_order", "单数据主页面", "草稿", "2026-08-12"],
    ["客户地图", "customer_map", "地图页面", "待发布", "2026-08-10"]
  ],
  users: [
    ["admin", "超级管理员", "研发中心", "正常", "2026-08-20"],
    ["cellx_ops", "运营人员", "三亚移动", "正常", "2026-08-19"],
    ["guest", "演示账号", "外部协作", "停用", "2026-08-09"]
  ],
  roles: [
    ["超级管理员", "admin", "全部数据权限", "启用"],
    ["页面设计师", "designer", "本部门数据", "启用"],
    ["只读访客", "viewer", "仅本人数据", "启用"]
  ],
  dict: [
    ["sys_normal_disable", "系统开关", "正常/停用", "正常"],
    ["cellx_field_type", "字段类型", "文本/数字/日期/字典", "正常"],
    ["page_show_type", "显示类型", "输入框/选择器/上传", "正常"]
  ],
  jobs: [
    ["授权到期扫描", "licenseExpireTask", "0 0 8 * * ?", "成功"],
    ["发布记录清理", "releaseHistoryClean", "0 0 2 ? * MON", "成功"],
    ["报表缓存刷新", "reportCacheRefresh", "0 */30 * * * ?", "失败"]
  ]
};

const state = {
  authed: localStorage.getItem("cellx-demo-login") === "yes",
  current: "dashboard",
  tabs: ["dashboard"],
  keyword: ""
};

function $(selector) { return document.querySelector(selector); }
function moduleById(id) { return modules.find(m => m.id === id) || modules[0]; }
function statusClass(text) {
  if (["正常", "启用", "已发布", "成功"].includes(text)) return "ok";
  if (["草稿", "待发布", "失败"].includes(text)) return "warn";
  return "off";
}
function toast(text) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = text;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 1800);
}

function render() {
  document.getElementById("app").innerHTML = state.authed ? shellTemplate() : loginTemplate();
  bindEvents();
}

function loginTemplate() {
  return `
    <main class="login-page">
      <section class="login-card">
        <div class="login-logo">
          <img src="./logo.png" alt="">
          <h1>“移”键适配平台</h1>
        </div>
        <div class="field"><label>账号*</label><input id="loginUser" placeholder="账号" value="admin"></div>
        <div class="field"><label>密码*</label><input id="loginPass" placeholder="密码" type="password" value="123456"></div>
        <div class="field">
          <label>验证码*</label>
          <div class="captcha-row"><input id="loginCode" placeholder="验证码" value="8K2F"><div class="captcha">8K2F</div></div>
        </div>
        <div class="login-options"><label><input type="checkbox" checked> 记住密码</label><span>克隆演示环境</span></div>
        <button class="primary-btn" data-login>登 录</button>
        <p class="login-copy">Copyright © 2021-2025 三亚移动 All Rights Reserved.</p>
      </section>
    </main>`;
}

function shellTemplate() {
  const current = moduleById(state.current);
  return `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand"><img src="./logo.png" alt=""><span>赛尔克斯基础平台</span></div>
        <nav class="menu">${groups.map(groupTemplate).join("")}</nav>
      </aside>
      <main class="main">
        <header class="topbar">
          <div><div class="crumb">首页 / ${current.title}</div><strong>${current.desc}</strong></div>
          <div class="top-actions">
            <button class="small-btn" data-action="theme">主题风格设置</button>
            <button class="small-btn" data-action="fullscreen">全屏</button>
            <div class="avatar">管</div>
            <button class="small-btn danger-btn" data-logout>退出</button>
          </div>
        </header>
        <div class="tabs">${state.tabs.map(id => `<button class="tab ${id === state.current ? "active" : ""}" data-route="${id}">${moduleById(id).title}</button>`).join("")}</div>
        <section class="content">${pageTemplate(state.current)}</section>
      </main>
    </div>`;
}

function groupTemplate(group) {
  const open = group.children.includes(state.current);
  return `
    <div class="menu-section ${open ? "open" : ""}">
      <button class="menu-title ${open ? "active" : ""}" data-toggle-menu><span class="ico">${moduleById(group.children[0]).icon}</span>${group.title}</button>
      <div class="submenu">${group.children.map(id => `<button class="${id === state.current ? "active" : ""}" data-route="${id}">${moduleById(id).title}</button>`).join("")}</div>
    </div>`;
}

function pageHead(title, desc, action = "新增") {
  return `<div class="page-head"><div><h2>${title}</h2><p>${desc}</p></div><button class="primary-btn small-btn" data-open-modal="${action}">${action}</button></div>`;
}

function pageTemplate(id) {
  const views = {
    dashboard, pageConfig, mapConfig, reportConfig, release, pageRuntime, authCenter,
    systemUser, systemRole, systemDict, systemMenu, monitorJob, monitorServer, toolGen,
    assistant, profile
  };
  return (views[id] || dashboard)();
}

function dashboard() {
  return `
    ${pageHead("首页", "系统资源、页面发布和服务状态总览", "系统布局配置")}
    <div class="grid cols-4">
      ${metric("页面总数", "128", "较上周新增 6 个")}
      ${metric("字段总数", "2,436", "导入更新字段 41 个")}
      ${metric("今日访问", "8,912", "接口平均 86 ms")}
      ${metric("License", "32 天", "授权即将过期提醒")}
    </div>
    <div class="grid cols-3" style="margin-top:14px">
      <section class="panel" style="grid-column:span 2">
        <h3>页面发布趋势</h3>
        <div class="chart">${[42, 68, 55, 88, 62, 96, 74].map(v => `<div class="bar" style="height:${v}%"></div>`).join("")}</div>
      </section>
      <section class="panel">
        <h3>快捷入口</h3>
        ${modules.slice(1, 7).map(m => `<button class="ghost-btn" style="width:100%;margin-bottom:9px;text-align:left" data-route="${m.id}">${m.title} - ${m.desc}</button>`).join("")}
      </section>
    </div>`;
}

function metric(label, value, desc) {
  return `<div class="card metric"><span>${label}</span><b>${value}</b><span>${desc}</span></div>`;
}

function table(headers, data, actions = true) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}${actions ? "<th>操作</th>" : ""}</tr></thead><tbody>
    ${data.map(row => `<tr>${row.map(cell => {
      const cls = statusClass(cell);
      return ["正常", "启用", "停用", "已发布", "草稿", "待发布", "成功", "失败"].includes(cell)
        ? `<td><span class="status ${cls}">${cell}</span></td>` : `<td>${cell}</td>`;
    }).join("")}${actions ? `<td><button class="small-btn" data-open-modal="查看">查看</button> <button class="small-btn" data-open-modal="编辑">编辑</button> <button class="small-btn danger-btn" data-open-modal="删除">删除</button></td>` : ""}</tr>`).join("")}
  </tbody></table></div>`;
}

function standardList(title, desc, headers, data, add = "新增") {
  return `
    ${pageHead(title, desc, add)}
    <section class="panel">
      <div class="toolbar">
        <input placeholder="搜索名称" data-search>
        <select><option>全部状态</option><option>正常</option><option>停用</option></select>
        <button class="ghost-btn" data-action="query">查询</button>
        <button class="ghost-btn" data-action="reset">重置</button>
        <button class="ghost-btn" data-action="export">导出</button>
      </div>
      ${table(headers, data)}
    </section>`;
}

function pageConfig() {
  return `
    ${pageHead("配置管理", "新增表、编辑字段、附属表、正则限制与页面复制", "新增表")}
    <div class="split">
      <section class="panel"><h3>数据库表</h3><ul class="tree"><li class="active">student 学生表</li><li>class 班级表</li><li>shop_order 商城订单</li><li>customer 客户信息</li></ul></section>
      <section class="panel">
        <div class="toolbar"><button class="ghost-btn" data-open-modal="新增字段">新增字段</button><button class="ghost-btn" data-open-modal="外键字段">外键字段</button><button class="ghost-btn" data-open-modal="复制页面">复制页面</button><button class="ghost-btn" data-open-modal="发布">发布</button></div>
        ${table(["中文标签", "字段名", "字段类型", "显示类型", "是否必填"], [["姓名", "name", "文本", "输入框", "正常"], ["年龄", "age", "数字", "数字输入", "正常"], ["班级", "class_id", "外键", "树选择", "正常"], ["头像", "avatar", "图片", "图片上传", "草稿"]])}
      </section>
    </div>`;
}

function mapConfig() {
  return standardList("地图配置", "编辑地图关联表、坐标字段和地图弹窗字段", ["地图名称", "关联主表", "经纬度字段", "状态", "更新时间"], [["客户分布地图", "customer", "lng/lat", "正常", "2026-08-21"], ["工单热力地图", "work_order", "longitude/latitude", "草稿", "2026-08-12"]], "新增地图");
}

function reportConfig() {
  return `
    ${pageHead("报表配置", "配置报表数据源、筛选条件、图表组件和发布", "新增报表")}
    <div class="builder">
      <section class="panel"><h3>组件面板</h3>${["折线图", "柱状图", "饼图", "指标卡", "日期筛选", "字典筛选"].map(x => `<div class="palette-item">${x}</div>`).join("")}</section>
      <section class="panel"><h3>报表画布</h3><div class="chart">${[73, 45, 92, 58, 76, 63].map(v => `<div class="bar" style="height:${v}%"></div>`).join("")}</div></section>
      <section class="panel"><h3>属性配置</h3><div class="field"><label>数据源</label><select><option>学生表</option><option>订单表</option></select></div><div class="field"><label>排序方式</label><select><option>按创建时间倒序</option><option>升序</option></select></div></section>
    </div>`;
}

function release() {
  return standardList("发布记录", "查看页面发布历史、发布状态和回滚版本", ["页面名称", "版本", "发布人", "状态", "发布时间"], [["学生管理", "v1.3.0", "admin", "成功", "2026-08-22 09:30"], ["班级管理", "v1.1.2", "cellx_ops", "成功", "2026-08-19 16:10"], ["客户地图", "v0.9.0", "admin", "失败", "2026-08-13 12:02"]], "发布页面");
}

function pageRuntime() {
  return standardList("页面运行", "动态列表、详情、编辑、导入、导出和软硬删除", ["页面名称", "表名", "页面类型", "状态", "更新时间"], rows.pages, "新增数据");
}

function authCenter() {
  return `
    ${pageHead("授权中心", "License、Token、订单记录、发票管理和设备重绑", "填写 API Key")}
    <div class="grid cols-4">${metric("License状态", "有效", "剩余 32 天")}${metric("Token余额", "18,400", "本月消耗 2,610")}${metric("绑定设备", "3 台", "允许重绑 1 次")}${metric("订单数量", "12", "待开票 2 单")}</div>
    <section class="panel" style="margin-top:14px">${table(["授权名称", "类型", "到期时间", "状态"], [["基础平台企业版", "License", "2026-09-25", "正常"], ["AI助手调用包", "Token", "长期", "正常"], ["测试授权", "License", "2026-08-29", "待发布"]])}</section>`;
}

function systemUser() {
  return standardList("用户管理", "用户增删改查、重置密码、分配角色", ["登录账号", "用户名称", "部门", "状态", "创建时间"], rows.users, "新增用户");
}

function systemRole() {
  return standardList("角色管理", "角色权限、菜单授权、分配用户与数据范围", ["角色名称", "权限字符", "数据范围", "状态"], rows.roles, "新增角色");
}

function systemDict() {
  return standardList("字典管理", "字典类型、字典数据项和标签样式", ["字典类型", "字典名称", "数据项", "状态"], rows.dict, "新增字典");
}

function systemMenu() {
  return standardList("菜单管理", "目录、菜单、按钮权限和路由配置", ["菜单名称", "路由地址", "组件路径", "图标", "状态"], [["系统管理", "/system", "Layout", "system", "正常"], ["用户管理", "/system/user", "system/user/index", "user", "正常"], ["页面生成器", "/pagegenerator", "Layout", "build", "正常"]], "新增菜单");
}

function monitorJob() {
  return standardList("定时任务", "任务调度、执行策略和调度日志", ["任务名称", "调用目标", "Cron表达式", "执行状态"], rows.jobs, "新增任务");
}

function monitorServer() {
  return `
    ${pageHead("服务监控", "服务版本、数据库版本、接口耗时和异常状态", "刷新")}
    <div class="grid cols-4">${metric("服务版本", "3.8.7", "运行 18 天")}${metric("数据库版本", "MySQL 8", "连接正常")}${metric("CPU使用率", "42%", "峰值 71%")}${metric("内存使用率", "63%", "剩余 5.8GB")}</div>
    <section class="panel" style="margin-top:14px">${table(["接口", "平均耗时", "调用次数", "状态"], [["/prod-api/system/user/list", "68 ms", "12,420", "正常"], ["/prod-api/pagegenerator/config", "92 ms", "7,804", "正常"], ["/prod-api/monitor/job/run", "146 ms", "421", "正常"]], false)}</section>`;
}

function toolGen() {
  return standardList("代码生成", "导入数据库表、修改生成配置、预览和下载代码", ["表名称", "表描述", "实体类", "生成模板", "状态"], [["sys_user", "用户信息表", "SysUser", "Vue3单表", "正常"], ["student", "学生管理", "Student", "主子表", "正常"], ["customer_map", "客户地图", "CustomerMap", "地图页面", "草稿"]], "导入表");
}

function assistant() {
  return `
    ${pageHead("小赖助手", "自然语言创建页面、字段、附属关系和筛选条件", "发送")}
    <div class="split">
      <section class="panel">
        <h3>会话</h3>
        <p class="muted">我是赛尔克斯小赖，可以帮你管理页面和字段。</p>
        <div class="field"><textarea class="textarea" placeholder="例如：创建学生管理页面，在学生表中新增姓名、年龄、班级字段"></textarea></div>
        <button class="primary-btn" data-action="assistant">发送</button>
      </section>
      <section class="panel">
        <h3>执行计划</h3>
        ${table(["步骤", "操作", "状态"], [["1", "匹配到学生表", "成功"], ["2", "新增姓名字段", "成功"], ["3", "创建列表页面", "待发布"], ["4", "生成字典数据", "草稿"]], false)}
      </section>
    </div>`;
}

function profile() {
  return `
    ${pageHead("个人中心", "用户资料、头像上传和密码重置", "保存")}
    <section class="panel">
      <div class="form-grid">
        <div class="field"><label>用户昵称</label><input value="系统管理员"></div>
        <div class="field"><label>手机号码</label><input value="13800000000"></div>
        <div class="field"><label>邮箱</label><input value="admin@cellx.com"></div>
        <div class="field"><label>所属部门</label><input value="研发中心"></div>
        <div class="field"><label>旧密码</label><input type="password"></div>
        <div class="field"><label>新密码</label><input type="password"></div>
      </div>
    </section>`;
}

function modalTemplate(title) {
  return `
    <div class="modal-backdrop">
      <div class="modal">
        <div class="modal-head"><strong>${title}</strong><button class="small-btn" data-close-modal>关闭</button></div>
        <div class="modal-body">
          <div class="form-grid">
            <div class="field"><label>名称</label><input value="${title}示例"></div>
            <div class="field"><label>状态</label><select><option>正常</option><option>停用</option><option>草稿</option></select></div>
            <div class="field"><label>排序</label><input value="1"></div>
            <div class="field"><label>显示类型</label><select><option>输入框</option><option>下拉选择</option><option>日期选择</option><option>上传文件</option></select></div>
          </div>
          <div class="field"><label>备注</label><textarea class="textarea">这是克隆演示中的${title}弹窗，模拟原系统的新增、编辑、详情、删除确认等操作。</textarea></div>
        </div>
        <div class="modal-foot"><button class="ghost-btn" data-close-modal>取消</button><button class="primary-btn small-btn" data-save-modal>确定</button></div>
      </div>
    </div>`;
}

function bindEvents() {
  document.querySelectorAll("[data-login]").forEach(btn => btn.addEventListener("click", () => {
    state.authed = true;
    localStorage.setItem("cellx-demo-login", "yes");
    render();
  }));
  document.querySelectorAll("[data-logout]").forEach(btn => btn.addEventListener("click", () => {
    state.authed = false;
    localStorage.removeItem("cellx-demo-login");
    render();
  }));
  document.querySelectorAll("[data-route]").forEach(btn => btn.addEventListener("click", () => {
    const id = btn.dataset.route;
    state.current = id;
    if (!state.tabs.includes(id)) state.tabs.push(id);
    render();
  }));
  document.querySelectorAll("[data-toggle-menu]").forEach(btn => btn.addEventListener("click", () => {
    btn.parentElement.classList.toggle("open");
  }));
  document.querySelectorAll("[data-action]").forEach(btn => btn.addEventListener("click", () => toast(`已执行：${btn.dataset.action}`)));
  document.querySelectorAll("[data-open-modal]").forEach(btn => btn.addEventListener("click", () => {
    document.body.insertAdjacentHTML("beforeend", modalTemplate(btn.dataset.openModal));
    bindModal();
  }));
}

function bindModal() {
  document.querySelectorAll("[data-close-modal]").forEach(btn => btn.onclick = () => btn.closest(".modal-backdrop").remove());
  document.querySelectorAll("[data-save-modal]").forEach(btn => btn.onclick = () => {
    btn.closest(".modal-backdrop").remove();
    toast("操作成功");
  });
}

render();
