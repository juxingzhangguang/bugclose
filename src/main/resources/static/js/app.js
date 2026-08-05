/* BugClose 前端逻辑 */
const API = '/api/bugs';
const PROJECT_API = '/api/projects';
const DOC_API = '/api/docs';
const CASE_API = '/api/testcases';
const REQ_API = '/api/requirements';
const AUTH_API = '/api/auth';
const USER_API = '/api/users';

const TOKEN_KEY = 'bugclose_token';

/* ===== 当前登录用户信息 ===== */
let currentUser = null; // {id, username, displayName, role, allProjects, allowedProjectIds}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

const SEVERITY_TEXT = { CRITICAL: '致命', HIGH: '严重', MEDIUM: '一般', LOW: '轻微' };
const PRIORITY_TEXT = { URGENT: '紧急', HIGH: '高', MEDIUM: '中', LOW: '低' };
const STATUS_TEXT = { NEW: '新建', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭' };
const CASE_STATUS_TEXT = { NOT_RUN: '未执行', PASS: '通过', FAIL: '失败', BLOCKED: '阻塞' };
const CASE_PRIORITY_TEXT = { P0: 'P0 冒烟', P1: 'P1 核心', P2: 'P2 一般', P3: 'P3 边缘' };
const REQ_STATUS_TEXT = { DRAFT: '草稿', REVIEWING: '评审中', APPROVED: '已确认', IN_PROGRESS: '开发中', COMPLETED: '已完成', REJECTED: '已拒绝' };
const REQ_PRIORITY_TEXT = { P0: 'P0 必须', P1: 'P1 核心', P2: 'P2 一般', P3: 'P3 边缘' };
/* 需求状态堆叠图配色，与列表状态标签色系一致 */
const REQ_STATUS_COLOR = { DRAFT: '#94a3b8', REVIEWING: '#c2710c', APPROVED: '#1a56db', IN_PROGRESS: '#7e22ce', COMPLETED: '#05803c', REJECTED: '#c81e1e' };
/* 用例执行状态堆叠图配色，与列表状态标签色系一致 */
const CASE_STATUS_COLOR = { NOT_RUN: '#94a3b8', PASS: '#05803c', FAIL: '#c81e1e', BLOCKED: '#c2710c' };
const DOC_CATEGORY_TEXT = {
  REQUIREMENT: '需求文档',
  DESIGN: '设计文档',
  TEST: '测试文档',
  MANUAL: '操作手册',
  MEETING: '会议纪要',
  OTHER: '其他',
};
/* 文档分类堆叠图配色，与列表分类标签色系一致 */
const DOC_CATEGORY_COLOR = {
  REQUIREMENT: '#1a56db',
  DESIGN: '#7e22ce',
  TEST: '#05803c',
  MANUAL: '#c2710c',
  MEETING: '#e8705f',
  OTHER: '#64748b',
};
/* 堆叠图配色，与列表标签色系一致 */
const STATUS_COLOR = { NEW: '#1a56db', IN_PROGRESS: '#c2710c', RESOLVED: '#05803c', CLOSED: '#94a3b8' };
const SEVERITY_COLOR = { CRITICAL: '#c81e1e', HIGH: '#e8705f', MEDIUM: '#1a56db', LOW: '#94a3b8' };
/* 与后端 BugService.isValidTransition 保持一致 */
const NEXT_STATUS = {
  NEW: ['IN_PROGRESS', 'CLOSED'],
  IN_PROGRESS: ['RESOLVED', 'CLOSED'],
  RESOLVED: ['CLOSED', 'IN_PROGRESS'],
  CLOSED: ['IN_PROGRESS'],
};

const $ = (id) => document.getElementById(id);

/* ===== 弹窗动画辅助 ===== */
function openModal(maskEl) {
  maskEl.classList.remove('hidden');
  // 强制重排以确保 transition 能触发
  void maskEl.offsetHeight;
  maskEl.classList.add('modal-visible');
}
function closeModal(maskEl) {
  maskEl.classList.remove('modal-visible');
  setTimeout(() => maskEl.classList.add('hidden'), 280);
}

/* ===== 视图切换 ===== */
const viewMap = {
  list: 'viewList',
  dashboard: 'viewDashboard',
  docs: 'viewDocs',
  cases: 'viewCases',
  requirements: 'viewRequirements',
  admin: 'viewAdmin',
};
let currentViewId = 'viewList';
let viewSwitching = false;

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (viewSwitching) return;
    const view = btn.dataset.view;
    const newViewId = viewMap[view];
    if (newViewId === currentViewId) return;

    document.querySelectorAll('.nav-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');

    const oldView = $(currentViewId);
    const newView = $(newViewId);
    viewSwitching = true;

    // 隐藏旧视图，显示新视图并触发淡入动画
    oldView.classList.add('hidden');
    newView.classList.remove('hidden');
    newView.classList.add('view-animate-in');

    setTimeout(() => {
      newView.classList.remove('view-animate-in');
      viewSwitching = false;
    }, 250);

    currentViewId = newViewId;
    if (view === 'dashboard') loadStatistics();
    else if (view === 'docs') loadDocs();
    else if (view === 'cases') loadCases();
    else if (view === 'requirements') loadRequirements();
    else if (view === 'admin') loadUsers();
    else loadBugs();
  });
});

/* ===== 请求封装 ===== */
async function request(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(url, { ...options, headers });
  if (resp.status === 401) {
    setToken(null);
    showLogin();
    throw new Error('登录已过期，请重新登录');
  }
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new Error((data && data.error) || `请求失败 (${resp.status})`);
  }
  return data;
}

/* 带 token 的 multipart 上传（不能带 JSON Content-Type） */
async function uploadRequest(url, formData) {
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(url, { method: 'POST', body: formData, headers });
  if (resp.status === 401) {
    setToken(null);
    showLogin();
    throw new Error('登录已过期，请重新登录');
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new Error((data && data.error) || `上传失败 (${resp.status})`);
  }
  return data;
}

/* ===== Toast ===== */
let toastTimer = null;
function showToast(msg, isError = false) {
  const toast = $('toast');
  toast.textContent = msg;
  toast.classList.toggle('error', isError);
  toast.classList.add('toast-show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('toast-show'), 2200);
}

/* ===== 项目数据 ===== */
let projects = []; // 项目列表缓存，供侧栏/表单下拉/名称映射使用
let selectedProjectId = ''; // 当前选中的项目 ID，'' 表示全部 Bug

function projectName(projectId) {
  if (projectId == null) return '';
  const p = projects.find((x) => x.id === projectId);
  return p ? p.name : `项目#${projectId}`;
}

/* Bug 展示编号：项目编号-项目内序号（如 MALL-1），无项目编号时退回 #序号 */
function bugNo(bug) {
  const no = bug.seq ?? bug.id;
  const p = projects.find((x) => x.id === bug.projectId);
  return p && p.code ? `${p.code}-${no}` : `#${no}`;
}

/* 刷新项目缓存，并同步左侧项目栏与表单下拉选项（保留当前选中值） */
async function refreshProjects() {
  projects = await request(PROJECT_API);
  // 选中的项目已被删除时回退到全部 Bug
  if (selectedProjectId && !projects.some((p) => String(p.id) === selectedProjectId)) {
    selectedProjectId = '';
  }
  renderProjectSidebar();
  renderDocSidebar();
  renderCaseSidebar();
  renderReqSidebar();
  fillProjectSelect($('bugProject'), '未关联项目');
  fillProjectSelect($('docProject'), '未关联项目');
  fillProjectSelect($('dProject'), '全部项目');
  fillProjectSelect($('caseProject'), '未关联项目');
  fillProjectSelect($('cProject'), '全部项目');
  fillProjectSelect($('reqProject'), '全部项目');
  fillProjectSelect($('rProject'), '未关联项目');
}

function fillProjectSelect(select, emptyText) {
  const current = select.value;
  select.innerHTML = `<option value="">${emptyText}</option>`;
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    select.appendChild(opt);
  }
  // 无项目时给出提示，避免误以为下拉加载失败
  if (!projects.length) {
    const opt = document.createElement('option');
    opt.disabled = true;
    opt.textContent = '（暂无项目，可在 Bug 列表左侧＋创建）';
    select.appendChild(opt);
  }
  if ([...select.options].some((o) => o.value === current)) select.value = current;
}

/* ===== 左侧项目栏 ===== */
let projPage = 1;
let projPageSize = 10;

function renderProjectSidebar() {
  const list = $('projList');
  const totalPages = Math.max(1, Math.ceil(projects.length / projPageSize));
  if (projPage > totalPages) projPage = totalPages;
  const pageProjects = projects.slice((projPage - 1) * projPageSize, projPage * projPageSize);
  const items = [
    `<li class="proj-item ${selectedProjectId === '' ? 'active' : ''}" data-id="">
      <span class="proj-item-name">📋 全部项目</span>
    </li>`,
  ];
  for (const p of pageProjects) {
    const active = selectedProjectId === String(p.id);
    items.push(`
      <li class="proj-item ${active ? 'active' : ''}" data-id="${p.id}" title="${escapeHtml(p.description || p.name)}">
        <span class="proj-item-name">${escapeHtml(p.name)}</span>
        <span class="proj-item-count ${p.bugCount === 0 ? 'zero' : ''}">${p.bugCount}</span>
        <span class="proj-item-ops">
          <button data-op="edit" data-id="${p.id}" title="编辑项目">✎</button>
          <button data-op="del" data-id="${p.id}" title="删除项目">×</button>
        </span>
      </li>`);
  }
  if (!projects.length) {
    items.push('<li class="proj-list-empty">暂无项目，点上方＋创建</li>');
  }
  list.innerHTML = items.join('');
  // 不满一页时也保持固定高度（1 个「全部 Bug」+ 每页项目位）
  list.style.minHeight = `${(projPageSize + 1) * 37 + 16}px`;
  $('projPageInfo').textContent = `${projPage}/${totalPages}`;
  $('projPrev').disabled = projPage <= 1;
  $('projNext').disabled = projPage >= totalPages;
}

$('projPrev').addEventListener('click', () => {
  projPage--;
  renderProjectSidebar();
});
$('projNext').addEventListener('click', () => {
  projPage++;
  renderProjectSidebar();
});
$('projPageSize').addEventListener('change', (e) => {
  projPageSize = Number(e.target.value);
  projPage = 1;
  renderProjectSidebar();
});

$('projList').addEventListener('click', async (e) => {
  const opBtn = e.target.closest('button[data-op]');
  if (opBtn) {
    const id = Number(opBtn.dataset.id);
    if (opBtn.dataset.op === 'edit') {
      openProjectEditModal(id);
    } else if (opBtn.dataset.op === 'del') {
      const p = projects.find((x) => x.id === id);
      if (!confirm(`确定删除项目「${p ? p.name : '#' + id}」吗？`)) return;
      try {
        await request(`${PROJECT_API}/${id}`, { method: 'DELETE' });
        showToast('删除成功');
        await refreshProjects();
        loadBugs();
      } catch (err) {
        showToast(err.message, true);
      }
    }
    return;
  }
  // 点击项目项 → 切换筛选
  const item = e.target.closest('.proj-item');
  if (!item) return;
  selectedProjectId = item.dataset.id;
  renderProjectSidebar();
  loadBugs();
});

/* 回填项目编辑弹窗（Bug 列表与文档库侧栏共用） */
function openProjectEditModal(id) {
  const p = projects.find((x) => x.id === id);
  if (!p) return;
  $('projModalTitle').textContent = `编辑项目 #${id}`;
  $('projId').value = p.id;
  $('projName').value = p.name;
  $('projCode').value = p.code || '';
  $('projDesc').value = p.description || '';
  openModal($('projMask'));
}

/* ===== 列表 ===== */
let allBugs = []; // 当前筛选条件下的全部 Bug，前端分页
let bugPage = 1;
let bugPageSize = 10;

async function loadBugs() {
  const params = new URLSearchParams();
  if (selectedProjectId) params.set('projectId', selectedProjectId);
  if ($('fStatus').value) params.set('status', $('fStatus').value);
  if ($('fSeverity').value) params.set('severity', $('fSeverity').value);
  if ($('fPriority').value) params.set('priority', $('fPriority').value);
  if ($('fAssignee').value.trim()) params.set('assignee', $('fAssignee').value.trim());
  if ($('fKeyword').value.trim()) params.set('keyword', $('fKeyword').value.trim());

  try {
    allBugs = await request(`${API}?${params.toString()}`);
    // 按项目分组、项目内按序号从 1 往下排（未关联排最后）
    allBugs.sort((a, b) => {
      const pa = a.projectId ?? Number.MAX_SAFE_INTEGER;
      const pb = b.projectId ?? Number.MAX_SAFE_INTEGER;
      return pa - pb || (a.seq ?? a.id) - (b.seq ?? b.id);
    });
    renderBugs();
  } catch (e) {
    showToast(e.message, true);
  }
  loadProjectSummary(); // 同步刷新页面下方的项目汇总图表
}

function renderBugs() {
  const tbody = $('bugTbody');
  tbody.innerHTML = '';
  const totalPages = Math.max(1, Math.ceil(allBugs.length / bugPageSize));
  if (bugPage > totalPages) bugPage = totalPages;
  const pageBugs = allBugs.slice((bugPage - 1) * bugPageSize, bugPage * bugPageSize);

  for (const bug of pageBugs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${bugNo(bug)}</td>
      <td class="bug-title-cell" title="${escapeHtml(bug.description || '')}">${escapeHtml(bug.title)}</td>
      <td>${bug.projectId != null ? `<span class="tag proj-tag">${escapeHtml(projectName(bug.projectId))}</span>` : '<span class="detail-empty">未关联</span>'}</td>
      <td><span class="tag sev-${bug.severity}">${SEVERITY_TEXT[bug.severity]}</span></td>
      <td><span class="tag pri-${bug.priority}">${PRIORITY_TEXT[bug.priority]}</span></td>
      <td><span class="tag st-${bug.status}">${STATUS_TEXT[bug.status]}</span></td>
      <td>${escapeHtml(bug.assignee || '-')}</td>
      <td>${escapeHtml(bug.reporter || '-')}</td>
      <td>${formatTime(bug.createdAt)}</td>
      <td class="op-cell">
        <button class="btn btn-sm" data-op="detail" data-id="${bug.id}">详情</button>
        <button class="btn btn-sm" data-op="trans" data-id="${bug.id}">流转</button>
        <button class="btn btn-sm" data-op="edit" data-id="${bug.id}">编辑</button>
        <button class="btn btn-sm btn-danger" data-op="del" data-id="${bug.id}">删除</button>
      </td>`;
    tbody.appendChild(tr);
  }

  // 无数据提示行
  if (!allBugs.length) {
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    tr.innerHTML = '<td colspan="10">暂无数据</td>';
    tbody.appendChild(tr);
  }
  // 不满一页时用空行补齐，保持表格高度固定
  const rendered = pageBugs.length + (allBugs.length ? 0 : 1);
  for (let i = rendered; i < bugPageSize; i++) {
    const tr = document.createElement('tr');
    tr.className = 'filler-row';
    tr.innerHTML = '<td colspan="10">&nbsp;</td>';
    tbody.appendChild(tr);
  }

  renderBugPager(totalPages);
}

/* Bug 列表分页栏 */
function renderBugPager(totalPages) {
  const nums = pageNumbers(bugPage, totalPages)
    .map((n) =>
      n === '…'
        ? '<span class="pager-ellipsis">…</span>'
        : `<button class="pager-btn ${n === bugPage ? 'active' : ''}" data-page="${n}">${n}</button>`
    )
    .join('');
  $('bugPager').innerHTML = `
    <span class="pager-total">共 ${allBugs.length} 条</span>
    <select id="bugPageSize" class="pager-size">
      ${[10, 20, 50].map((s) => `<option value="${s}" ${s === bugPageSize ? 'selected' : ''}>${s} 条/页</option>`).join('')}
    </select>
    <button class="pager-btn" data-page="${bugPage - 1}" ${bugPage <= 1 ? 'disabled' : ''}>上一页</button>
    ${nums}
    <button class="pager-btn" data-page="${bugPage + 1}" ${bugPage >= totalPages ? 'disabled' : ''}>下一页</button>`;
}

/* 页码序列：首尾 + 当前页附近，其余用省略号 */
function pageNumbers(page, totalPages) {
  const nums = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || Math.abs(i - page) <= 1) nums.push(i);
    else if (nums[nums.length - 1] !== '…') nums.push('…');
  }
  return nums;
}

$('bugPager').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-page]');
  if (!btn || btn.disabled) return;
  bugPage = Number(btn.dataset.page);
  renderBugs();
});
$('bugPager').addEventListener('change', (e) => {
  if (e.target.id === 'bugPageSize') {
    bugPageSize = Number(e.target.value);
    bugPage = 1;
    renderBugs();
  }
});

/* ===== 项目 Bug 汇总分析（页面下方图表） ===== */
async function loadProjectSummary() {
  try {
    const bugs = await request(API); // 全量 Bug，不受筛选影响
    renderProjectSummary(bugs);
  } catch {
    /* 汇总失败不影响列表 */
  }
}

function renderProjectSummary(bugs) {
  // 按项目分桶，未关联的单独一桶
  const rows = bucketByProject(bugs, '未关联');

  if (!rows.length) {
    ['chartProjCount', 'chartProjStatus', 'chartProjSeverity'].forEach((id) => {
      $(id).innerHTML = '<p class="chart-empty">暂无数据</p>';
    });
    return;
  }

  const countMap = {};
  for (const r of rows) countMap[r.name] = r.items.length;
  renderBarChart('chartProjCount', countMap, null);
  renderStackChart('chartProjStatus', rows, 'status', STATUS_TEXT, STATUS_COLOR);
  renderStackChart('chartProjSeverity', rows, 'severity', SEVERITY_TEXT, SEVERITY_COLOR);
}

/* 把一组带 projectId 的记录按项目分桶，未关联的单独一桶 */
function bucketByProject(list, unassignedName) {
  const buckets = new Map();
  for (const p of projects) buckets.set(p.id, { name: p.name, items: [] });
  const unassigned = { name: unassignedName, items: [] };
  for (const item of list) {
    const b = buckets.get(item.projectId);
    if (b) b.items.push(item);
    else unassigned.items.push(item);
  }
  const rows = [...buckets.values()];
  if (unassigned.items.length) rows.push(unassigned);
  return rows;
}

/* 堆叠条形图：条长按项目记录总量，条内按维度占比分段着色 */
function renderStackChart(containerId, rows, field, textMap, colorMap) {
  const keys = Object.keys(textMap);
  const maxTotal = Math.max(...rows.map((r) => r.items.length), 1);
  const legend = `<div class="stack-legend">${keys
    .map((k) => `<span><i class="legend-dot" style="background:${colorMap[k]}"></i>${textMap[k]}</span>`)
    .join('')}</div>`;
  const body = rows
    .map((r) => {
      const total = r.items.length;
      const fillPct = ((total / maxTotal) * 100).toFixed(1);
      const segs = keys
        .map((k) => {
          const n = r.items.filter((b) => b[field] === k).length;
          if (!n) return '';
          return `<span class="stack-seg" style="width:${((n / total) * 100).toFixed(2)}%;background:${colorMap[k]}" title="${textMap[k]}：${n}"></span>`;
        })
        .join('');
      return `<div class="bar-row">
        <span class="bar-label" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</span>
        <div class="bar-track">${total ? `<div class="stack-fill" style="width:${fillPct}%">${segs}</div>` : ''}</div>
        <span class="bar-count">${total}</span>
      </div>`;
    })
    .join('');
  $(containerId).innerHTML = legend + body;
}

$('bugTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const op = btn.dataset.op;
  if (op === 'edit') openEditModal(id);
  else if (op === 'detail') openDetailModal(id);
  else if (op === 'trans') openTransModal(id);
  else if (op === 'del') {
    const bug = allBugs.find((b) => b.id === id);
    if (!confirm(`确定删除 Bug ${bug ? bugNo(bug) : '#' + id}「${bug ? bug.title : ''}」吗？`)) return;
    try {
      await request(`${API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
      refreshProjects().catch(() => {}); // 同步侧栏 Bug 计数
      loadBugs();
    } catch (err) {
      showToast(err.message, true);
    }
  }
});

$('btnSearch').addEventListener('click', loadBugs);
$('btnReset').addEventListener('click', () => {
  ['fKeyword', 'fAssignee'].forEach((id) => ($(id).value = ''));
  ['fStatus', 'fSeverity', 'fPriority'].forEach((id) => ($(id).value = ''));
  loadBugs();
});
$('fKeyword').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadBugs();
});

/* ===== 新建 / 编辑 ===== */
$('btnNew').addEventListener('click', () => {
  $('modalTitle').textContent = '新建 Bug';
  $('bugForm').reset();
  $('bugId').value = '';
  // 新建时默认带入当前侧栏选中的项目
  $('bugProject').value = selectedProjectId;
  setFormImages([]);
  openModal($('modalMask'));
});

async function openEditModal(id) {
  try {
    const bug = await request(`${API}/${id}`);
    $('modalTitle').textContent = `编辑 Bug ${bugNo(bug)}`;
    $('bugId').value = bug.id;
    $('bugTitle').value = bug.title;
    $('bugProject').value = bug.projectId != null ? String(bug.projectId) : '';
    $('bugDesc').value = bug.description || '';
    $('bugSeverity').value = bug.severity;
    $('bugPriority').value = bug.priority;
    $('bugAssignee').value = bug.assignee || '';
    $('bugReporter').value = bug.reporter || '';
    $('bugEnvironment').value = bug.environment || '';
    $('bugModule').value = bug.module || '';
    setFormImages(parseImages(bug.images));
    openModal($('modalMask'));
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnCancel').addEventListener('click', () => closeModal($('modalMask')));

$('bugForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('bugId').value;
  const payload = {
    title: $('bugTitle').value.trim(),
    projectId: $('bugProject').value ? Number($('bugProject').value) : null,
    description: $('bugDesc').value.trim(),
    severity: $('bugSeverity').value,
    priority: $('bugPriority').value,
    assignee: $('bugAssignee').value.trim(),
    reporter: $('bugReporter').value.trim(),
    environment: $('bugEnvironment').value.trim(),
    module: $('bugModule').value.trim(),
    images: JSON.stringify(formImages),
  };
  try {
    if (id) {
      await request(`${API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      await request(API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('创建成功');
    }
    closeModal($('modalMask'));
    refreshProjects().catch(() => {}); // 同步侧栏 Bug 计数
    loadBugs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* ===== Bug 图片上传 ===== */
let formImages = []; // 当前表单已上传图片的 URL 列表

function parseImages(imagesJson) {
  try {
    const arr = JSON.parse(imagesJson || '[]');
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function setFormImages(urls) {
  formImages = [...urls];
  renderImageGrid();
}

function renderImageGrid() {
  const grid = $('imageGrid');
  grid.querySelectorAll('.image-item').forEach((el) => el.remove());
  const addBox = $('imageAddBox');
  for (const url of formImages) {
    const item = document.createElement('div');
    item.className = 'image-item';
    item.innerHTML = `
      <img src="${url}" alt="bug图片">
      <button type="button" class="image-remove" data-url="${url}" title="移除">×</button>`;
    grid.insertBefore(item, addBox);
  }
}

$('imageAddBox').addEventListener('click', () => $('bugImageInput').click());

$('bugImageInput').addEventListener('change', async (e) => {
  const files = [...e.target.files];
  e.target.value = ''; // 允许重复选同一文件
  for (const file of files) {
    if (file.size > 5 * 1024 * 1024) {
      showToast(`「${file.name}」超过 5MB，已跳过`, true);
      continue;
    }
    // 先插入本地预览占位，上传完成后替换为服务器 URL
    const item = document.createElement('div');
    item.className = 'image-item uploading';
    item.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="上传中">`;
    $('imageGrid').insertBefore(item, $('imageAddBox'));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const upHeaders = {};
      const tok = getToken();
      if (tok) upHeaders['Authorization'] = `Bearer ${tok}`;
      const resp = await fetch('/api/uploads', { method: 'POST', body: fd, headers: upHeaders });
      const data = await resp.json().catch(() => null);
      if (!resp.ok) throw new Error((data && data.error) || `上传失败 (${resp.status})`);
      formImages.push(data.url);
      renderImageGrid();
    } catch (err) {
      item.remove();
      showToast(err.message, true);
    }
  }
});

$('imageGrid').addEventListener('click', (e) => {
  const removeBtn = e.target.closest('.image-remove');
  if (removeBtn) {
    formImages = formImages.filter((u) => u !== removeBtn.dataset.url);
    renderImageGrid();
    return;
  }
  const img = e.target.closest('.image-item:not(.uploading) img');
  if (img) {
    $('imgPreviewLarge').src = img.src;
    openModal($('imgPreviewMask'));
  }
});

$('imgPreviewMask').addEventListener('click', () => {
  closeModal($('imgPreviewMask'));
  $('imgPreviewLarge').src = '';
});

/* ===== Bug 详情 ===== */
let detailBugId = null;

async function openDetailModal(id) {
  try {
    const bug = await request(`${API}/${id}`);
    detailBugId = bug.id;
    $('detailTitle').textContent = `Bug ${bugNo(bug)} 详情`;
    const images = parseImages(bug.images);
    const imagesHtml = images.length
      ? `<div class="image-grid">${images
          .map((url) => `<div class="image-item"><img src="${url}" alt="bug图片"></div>`)
          .join('')}</div>`
      : '<span class="detail-empty">无</span>';
    $('detailBody').innerHTML = `
      <div class="detail-row"><span class="detail-label">标题</span><span class="detail-value">${escapeHtml(bug.title)}</span></div>
      <div class="detail-row"><span class="detail-label">所属项目</span><span class="detail-value">${bug.projectId != null ? escapeHtml(projectName(bug.projectId)) : '<span class="detail-empty">未关联</span>'}</span></div>
      <div class="detail-row"><span class="detail-label">状态</span><span class="detail-value">
        <span class="tag st-${bug.status}">${STATUS_TEXT[bug.status]}</span>
        <span class="tag sev-${bug.severity}">${SEVERITY_TEXT[bug.severity]}</span>
        <span class="tag pri-${bug.priority}">优先级：${PRIORITY_TEXT[bug.priority]}</span>
      </span></div>
      <div class="detail-row"><span class="detail-label">影响环境</span><span class="detail-value">${bug.environment ? escapeHtml(bug.environment) : '<span class="detail-empty">未填写</span>'}</span></div>
      <div class="detail-row"><span class="detail-label">影响模块</span><span class="detail-value">${bug.module ? escapeHtml(bug.module) : '<span class="detail-empty">未填写</span>'}</span></div>
      <div class="detail-row"><span class="detail-label">处理人</span><span class="detail-value">${escapeHtml(bug.assignee || '未指派')}</span></div>
      <div class="detail-row"><span class="detail-label">报告人</span><span class="detail-value">${escapeHtml(bug.reporter || '-')}</span></div>
      <div class="detail-row"><span class="detail-label">创建时间</span><span class="detail-value">${formatTime(bug.createdAt)}</span></div>
      <div class="detail-row"><span class="detail-label">更新时间</span><span class="detail-value">${formatTime(bug.updatedAt)}</span></div>
      <div class="detail-row"><span class="detail-label">详细描述</span><span class="detail-value detail-desc">${bug.description ? escapeHtml(bug.description) : '<span class="detail-empty">无</span>'}</span></div>
      <div class="detail-row"><span class="detail-label">Bug 图片</span><span class="detail-value">${imagesHtml}</span></div>`;
    openModal($('detailMask'));
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnDetailClose').addEventListener('click', () => closeModal($('detailMask')));

$('btnDetailEdit').addEventListener('click', () => {
  closeModal($('detailMask'));
  if (detailBugId != null) openEditModal(detailBugId);
});

/* 详情内点击缩略图查看大图 */
$('detailBody').addEventListener('click', (e) => {
  const img = e.target.closest('.image-item img');
  if (img) {
    $('imgPreviewLarge').src = img.src;
    openModal($('imgPreviewMask'));
  }
});

/* ===== 状态流转 ===== */
async function openTransModal(id) {
  try {
    const bug = await request(`${API}/${id}`);
    $('transBugId').value = bug.id;
    $('transInfo').textContent =
      `Bug ${bugNo(bug)}「${bug.title}」当前状态：${STATUS_TEXT[bug.status]}`;
    const select = $('transStatus');
    select.innerHTML = '';
    for (const next of NEXT_STATUS[bug.status]) {
      const opt = document.createElement('option');
      opt.value = next;
      opt.textContent = STATUS_TEXT[next];
      select.appendChild(opt);
    }
    $('transAssignee').value = '';
    openModal($('transMask'));
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnTransCancel').addEventListener('click', () => closeModal($('transMask')));

$('transForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('transBugId').value;
  const payload = {
    status: $('transStatus').value,
    assignee: $('transAssignee').value.trim(),
  };
  try {
    await request(`${API}/${id}/status`, { method: 'PUT', body: JSON.stringify(payload) });
    showToast('流转成功');
    closeModal($('transMask'));
    loadBugs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* ===== 项目新建/编辑弹窗 ===== */
$('btnNewProject').addEventListener('click', () => {
  $('projModalTitle').textContent = '新建项目';
  $('projForm').reset();
  $('projId').value = '';
  openModal($('projMask'));
});

$('btnProjCancel').addEventListener('click', () => closeModal($('projMask')));

$('projForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('projId').value;
  const payload = {
    name: $('projName').value.trim(),
    code: $('projCode').value.trim(),
    description: $('projDesc').value.trim(),
  };
  try {
    if (id) {
      await request(`${PROJECT_API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      await request(PROJECT_API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('创建成功');
    }
    closeModal($('projMask'));
    await refreshProjects();
    loadBugs();
    // 文档库视图打开时同步刷新文档列表（项目名、侧栏计数）
    if (!$('viewDocs').classList.contains('hidden')) loadDocs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* ===== 统计看板 ===== */
async function loadStatistics() {
  try {
    const stat = await request(`${API}/statistics`);
    renderStatCards(stat);
    renderBarChart('chartStatus', stat.byStatus, STATUS_TEXT);
    renderBarChart('chartSeverity', stat.bySeverity, SEVERITY_TEXT);
    renderBarChart('chartAssignee', stat.byAssignee, null);
  } catch (e) {
    showToast(e.message, true);
  }
}

function renderStatCards(stat) {
  const cards = [
    { label: '全部 Bug', num: stat.total, color: '#333' },
    { label: '新建', num: stat.byStatus.NEW, color: '#1a56db' },
    { label: '处理中', num: stat.byStatus.IN_PROGRESS, color: '#c2710c' },
    { label: '已解决', num: stat.byStatus.RESOLVED, color: '#05803c' },
    { label: '已关闭', num: stat.byStatus.CLOSED, color: '#64748b' },
  ];
  $('statCards').innerHTML = cards
    .map(
      (c) => `<div class="stat-card">
        <div class="num" style="color:${c.color}">${c.num}</div>
        <div class="label">${c.label}</div>
      </div>`
    )
    .join('');
}

function renderBarChart(containerId, dataMap, textMap) {
  const container = $(containerId);
  const entries = Object.entries(dataMap);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  container.innerHTML = entries
    .map(([key, val]) => {
      const label = textMap ? textMap[key] || key : key;
      const pct = ((val / max) * 100).toFixed(1);
      return `<div class="bar-row">
        <span class="bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        <div class="bar-track"><div class="bar-fill ${val === 0 ? 'zero' : ''}" style="width:${pct}%"></div></div>
        <span class="bar-count">${val}</span>
      </div>`;
    })
    .join('');
}

/* ===== 文档库 ===== */
let allDocs = []; // 当前筛选条件下的文档列表，前端分页
let docPage = 1;
let docPageSize = 10;

async function loadDocs() {
  const params = new URLSearchParams();
  if ($('dProject').value) params.set('projectId', $('dProject').value);
  if ($('dCategory').value) params.set('category', $('dCategory').value);
  if ($('dKeyword').value.trim()) params.set('keyword', $('dKeyword').value.trim());
  try {
    allDocs = await request(`${DOC_API}?${params.toString()}`);
    renderDocs();
  } catch (e) {
    showToast(e.message, true);
  }
  loadDocSummary();
}

/* 文档汇总分析（文档列表下方图表，全量数据不受筛选影响） */
async function loadDocSummary() {
  try {
    const docs = await request(DOC_API);
    renderDocSummary(docs);
  } catch {
    /* 汇总失败不影响列表 */
  }
}

function renderDocSummary(docs) {
  // 按分类汇总，六类全部列出便于对比
  const catMap = {};
  for (const k of Object.keys(DOC_CATEGORY_TEXT)) catMap[k] = 0;
  for (const d of docs) catMap[d.category] = (catMap[d.category] || 0) + 1;
  renderBarChart('chartDocCategory', catMap, DOC_CATEGORY_TEXT);

  // 同步左侧项目栏的文档计数
  docCountByProject = new Map();
  for (const d of docs) {
    docCountByProject.set(d.projectId, (docCountByProject.get(d.projectId) || 0) + 1);
  }
  renderDocSidebar();

  // 按项目汇总
  const rows = bucketByProject(docs, '未关联');
  if (!rows.length) {
    ['chartDocProjCount', 'chartDocProjCategory'].forEach((id) => {
      $(id).innerHTML = '<p class="chart-empty">暂无数据</p>';
    });
    return;
  }
  const countMap = {};
  for (const r of rows) countMap[r.name] = r.items.length;
  renderBarChart('chartDocProjCount', countMap, null);
  renderStackChart('chartDocProjCategory', rows, 'category', DOC_CATEGORY_TEXT, DOC_CATEGORY_COLOR);
}

/* ===== 文档库左侧项目栏（与 Bug 列表同款布局，计数为文档数） ===== */
let docProjPage = 1;
let docProjPageSize = 10;
let docCountByProject = new Map(); // projectId -> 文档数

function renderDocSidebar() {
  const list = $('docProjList');
  const totalPages = Math.max(1, Math.ceil(projects.length / docProjPageSize));
  if (docProjPage > totalPages) docProjPage = totalPages;
  const pageProjects = projects.slice((docProjPage - 1) * docProjPageSize, docProjPage * docProjPageSize);
  const selected = $('dProject').value;
  const items = [
    `<li class="proj-item ${selected === '' ? 'active' : ''}" data-id="">
      <span class="proj-item-name">📋 全部项目</span>
    </li>`,
  ];
  for (const p of pageProjects) {
    const active = selected === String(p.id);
    const count = docCountByProject.get(p.id) || 0;
    items.push(`
      <li class="proj-item ${active ? 'active' : ''}" data-id="${p.id}" title="${escapeHtml(p.description || p.name)}">
        <span class="proj-item-name">${escapeHtml(p.name)}</span>
        <span class="proj-item-count ${count === 0 ? 'zero' : ''}">${count}</span>
        <span class="proj-item-ops">
          <button data-op="edit" data-id="${p.id}" title="编辑项目">✎</button>
          <button data-op="del" data-id="${p.id}" title="删除项目">×</button>
        </span>
      </li>`);
  }
  if (!projects.length) {
    items.push('<li class="proj-list-empty">暂无项目，点上方＋创建</li>');
  }
  list.innerHTML = items.join('');
  // 不满一页时也保持固定高度（1 个「全部项目」+ 每页项目位）
  list.style.minHeight = `${(docProjPageSize + 1) * 37 + 16}px`;
  $('docProjPageInfo').textContent = `${docProjPage}/${totalPages}`;
  $('docProjPrev').disabled = docProjPage <= 1;
  $('docProjNext').disabled = docProjPage >= totalPages;
}

$('docProjPrev').addEventListener('click', () => {
  docProjPage--;
  renderDocSidebar();
});
$('docProjNext').addEventListener('click', () => {
  docProjPage++;
  renderDocSidebar();
});
$('docProjPageSize').addEventListener('change', (e) => {
  docProjPageSize = Number(e.target.value);
  docProjPage = 1;
  renderDocSidebar();
});

$('btnDocNewProject').addEventListener('click', () => {
  $('projModalTitle').textContent = '新建项目';
  $('projForm').reset();
  $('projId').value = '';
  openModal($('projMask'));
});

$('docProjList').addEventListener('click', async (e) => {
  const opBtn = e.target.closest('button[data-op]');
  if (opBtn) {
    const id = Number(opBtn.dataset.id);
    if (opBtn.dataset.op === 'edit') {
      openProjectEditModal(id);
    } else if (opBtn.dataset.op === 'del') {
      const p = projects.find((x) => x.id === id);
      if (!confirm(`确定删除项目「${p ? p.name : '#' + id}」吗？`)) return;
      try {
        await request(`${PROJECT_API}/${id}`, { method: 'DELETE' });
        showToast('删除成功');
        await refreshProjects();
        loadDocs();
      } catch (err) {
        showToast(err.message, true);
      }
    }
    return;
  }
  // 点击项目项 → 切换文档筛选（与筛选栏下拉联动）
  const item = e.target.closest('.proj-item');
  if (!item) return;
  $('dProject').value = item.dataset.id;
  docPage = 1;
  renderDocSidebar();
  loadDocs();
});

function renderDocs() {
  const tbody = $('docTbody');
  tbody.innerHTML = '';
  const totalPages = Math.max(1, Math.ceil(allDocs.length / docPageSize));
  if (docPage > totalPages) docPage = totalPages;
  const pageDocs = allDocs.slice((docPage - 1) * docPageSize, docPage * docPageSize);
  pageDocs.forEach((doc, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="seq-col">${(docPage - 1) * docPageSize + idx + 1}</td>
      <td class="bug-title-cell" title="${escapeHtml(doc.description || '')}">📄 ${escapeHtml(doc.title)}</td>
      <td>${doc.projectId != null ? `<span class="tag proj-tag">${escapeHtml(doc.projectName || projectName(doc.projectId))}</span>` : '<span class="detail-empty">未关联</span>'}</td>
      <td><span class="tag doc-cat-${doc.category}">${DOC_CATEGORY_TEXT[doc.category] || doc.category}</span></td>
      <td>v${doc.latestVersionNo}</td>
      <td>${formatSize(doc.latestFileSize)}</td>
      <td>${escapeHtml(doc.latestUploader || doc.uploader || '-')}</td>
      <td>${formatTime(doc.updatedAt)}</td>
      <td class="op-cell">
        <button class="btn btn-sm" data-op="download" data-id="${doc.id}">下载</button>
        <button class="btn btn-sm" data-op="newver" data-id="${doc.id}">更新版本</button>
        <button class="btn btn-sm" data-op="history" data-id="${doc.id}">历史</button>
        <button class="btn btn-sm" data-op="edit" data-id="${doc.id}">编辑</button>
        <button class="btn btn-sm btn-danger" data-op="del" data-id="${doc.id}">删除</button>
      </td>`;
    tbody.appendChild(tr);
  });
  if (!allDocs.length) {
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    tr.innerHTML = '<td colspan="9">暂无文档，点右上方「+ 上传文档」归档</td>';
    tbody.appendChild(tr);
  }
  // 不满一页时用空行补齐，保持表格高度固定
  const rendered = pageDocs.length + (allDocs.length ? 0 : 1);
  for (let i = rendered; i < docPageSize; i++) {
    const tr = document.createElement('tr');
    tr.className = 'filler-row';
    tr.innerHTML = '<td colspan="9">&nbsp;</td>';
    tbody.appendChild(tr);
  }

  renderDocPager(totalPages);
}

/* 文档列表分页栏 */
function renderDocPager(totalPages) {
  const nums = pageNumbers(docPage, totalPages)
    .map((n) =>
      n === '…'
        ? '<span class="pager-ellipsis">…</span>'
        : `<button class="pager-btn ${n === docPage ? 'active' : ''}" data-page="${n}">${n}</button>`
    )
    .join('');
  $('docPager').innerHTML = `
    <span class="pager-total">共 ${allDocs.length} 条</span>
    <select id="docPageSize" class="pager-size">
      ${[10, 20, 50].map((s) => `<option value="${s}" ${s === docPageSize ? 'selected' : ''}>${s} 条/页</option>`).join('')}
    </select>
    <button class="pager-btn" data-page="${docPage - 1}" ${docPage <= 1 ? 'disabled' : ''}>上一页</button>
    ${nums}
    <button class="pager-btn" data-page="${docPage + 1}" ${docPage >= totalPages ? 'disabled' : ''}>下一页</button>`;
}

$('docPager').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-page]');
  if (!btn || btn.disabled) return;
  docPage = Number(btn.dataset.page);
  renderDocs();
});
$('docPager').addEventListener('change', (e) => {
  if (e.target.id === 'docPageSize') {
    docPageSize = Number(e.target.value);
    docPage = 1;
    renderDocs();
  }
});

$('btnDocSearch').addEventListener('click', loadDocs);
$('btnDocReset').addEventListener('click', () => {
  $('dKeyword').value = '';
  $('dProject').value = '';
  $('dCategory').value = '';
  loadDocs();
});
$('dKeyword').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadDocs();
});

/* 文档列表操作 */
$('docTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const doc = allDocs.find((d) => d.id === id);
  if (!doc) return;
  const op = btn.dataset.op;
  if (op === 'download') {
    if (doc.latestVersionId == null) return showToast('暂无可下载文件', true);
    window.open(`${DOC_API}/${id}/versions/${doc.latestVersionId}/download`, '_blank');
  } else if (op === 'newver') {
    $('docVerDocId').value = id;
    $('docVerInfo').textContent = `「${doc.title}」当前版本：v${doc.latestVersionNo}，上传后将升级为 v${doc.latestVersionNo + 1}`;
    $('docVerForm').reset();
    openModal($('docVerMask'));
  } else if (op === 'history') {
    openDocHistory(doc);
  } else if (op === 'edit') {
    $('docModalTitle').textContent = `编辑文档「${doc.title}」`;
    $('docForm').reset();
    $('docId').value = doc.id;
    $('docTitle').value = doc.title;
    $('docProject').value = doc.projectId != null ? String(doc.projectId) : '';
    $('docCategory').value = doc.category;
    $('docDesc').value = doc.description || '';
    // 编辑仅改元信息，隐藏文件与上传人项（换文件请走「更新版本」）
    $('docFileLabel').classList.add('hidden');
    $('docUploaderLabel').classList.add('hidden');
    openModal($('docMask'));
  } else if (op === 'del') {
    if (!confirm(`确定删除文档「${doc.title}」及其全部 ${doc.latestVersionNo} 个版本吗？`)) return;
    try {
      await request(`${DOC_API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
      loadDocs();
    } catch (err) {
      showToast(err.message, true);
    }
  }
});

/* 上传文档弹窗 */
$('btnDocNew').addEventListener('click', () => {
  $('docModalTitle').textContent = '上传文档';
  $('docForm').reset();
  $('docId').value = '';
  $('docProject').value = $('dProject').value; // 默认带入当前筛选的项目
  $('docFileLabel').classList.remove('hidden');
  $('docUploaderLabel').classList.remove('hidden');
  openModal($('docMask'));
});

$('btnDocCancel').addEventListener('click', () => closeModal($('docMask')));

/* 选文件后自动带入文件名作为文档名称 */
$('docFile').addEventListener('change', () => {
  const file = $('docFile').files[0];
  if (file && !$('docTitle').value.trim()) {
    $('docTitle').value = file.name.replace(/\.[^.]+$/, '');
  }
});

$('docForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('docId').value;
  try {
    if (id) {
      // 编辑元信息
      const payload = {
        title: $('docTitle').value.trim(),
        category: $('docCategory').value,
        projectId: $('docProject').value ? Number($('docProject').value) : null,
        description: $('docDesc').value.trim(),
      };
      await request(`${DOC_API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      // 新上传：multipart
      const file = $('docFile').files[0];
      if (!file) return showToast('请选择文档文件', true);
      if (file.size > 50 * 1024 * 1024) return showToast('文件不能超过 50MB', true);
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', $('docTitle').value.trim());
      fd.append('category', $('docCategory').value);
      if ($('docProject').value) fd.append('projectId', $('docProject').value);
      if ($('docDesc').value.trim()) fd.append('description', $('docDesc').value.trim());
      if ($('docUploader').value.trim()) fd.append('uploader', $('docUploader').value.trim());
      await uploadRequest(DOC_API, fd);
      showToast('上传成功');
    }
    closeModal($('docMask'));
    loadDocs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 更新版本弹窗 */
$('btnDocVerCancel').addEventListener('click', () => closeModal($('docVerMask')));

$('docVerForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('docVerDocId').value;
  const file = $('docVerFile').files[0];
  if (!file) return showToast('请选择新版本文件', true);
  if (file.size > 50 * 1024 * 1024) return showToast('文件不能超过 50MB', true);
  const fd = new FormData();
  fd.append('file', file);
  if ($('docVerRemark').value.trim()) fd.append('remark', $('docVerRemark').value.trim());
  if ($('docVerUploader').value.trim()) fd.append('uploader', $('docVerUploader').value.trim());
  try {
    await uploadRequest(`${DOC_API}/${id}/versions`, fd);
    showToast('新版本上传成功');
    closeModal($('docVerMask'));
    loadDocs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 版本历史弹窗 */
async function openDocHistory(doc) {
  try {
    const versions = await request(`${DOC_API}/${doc.id}/versions`);
    $('docHisTitle').textContent = `「${doc.title}」版本历史`;
    $('docHisTbody').innerHTML = versions
      .map(
        (v) => `<tr>
          <td>v${v.versionNo}${v.versionNo === doc.latestVersionNo ? ' <span class="tag doc-latest">最新</span>' : ''}</td>
          <td class="bug-title-cell">${escapeHtml(v.originalFilename)}</td>
          <td>${formatSize(v.fileSize)}</td>
          <td>${escapeHtml(v.remark || '-')}</td>
          <td>${escapeHtml(v.uploader || '-')}</td>
          <td>${formatTime(v.createdAt)}</td>
          <td class="op-cell"><button class="btn btn-sm" data-ver="${v.id}" data-doc="${doc.id}">下载</button></td>
        </tr>`
      )
      .join('');
    openModal($('docHisMask'));
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnDocHisClose').addEventListener('click', () => closeModal($('docHisMask')));

$('docHisTbody').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-ver]');
  if (!btn) return;
  window.open(`${DOC_API}/${btn.dataset.doc}/versions/${btn.dataset.ver}/download`, '_blank');
});

/* 文件大小友好显示 */
function formatSize(bytes) {
  if (bytes == null) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/* ===== 测试用例 ===== */
let allCases = []; // 当前筛选条件下的用例列表，前端分页
let casePage = 1;
let casePageSize = 10;

/* 用例展示编号：项目编号-TC序号（如 MALL-TC1），无项目编号时退回 TC-序号 */
function caseNo(tc) {
  const no = tc.seq ?? tc.id;
  const p = projects.find((x) => x.id === tc.projectId);
  return p && p.code ? `${p.code}-TC${no}` : `TC-${no}`;
}

async function loadCases() {
  const params = new URLSearchParams();
  if ($('cProject').value) params.set('projectId', $('cProject').value);
  if ($('cStatus').value) params.set('status', $('cStatus').value);
  if ($('cPriority').value) params.set('priority', $('cPriority').value);
  if ($('cKeyword').value.trim()) params.set('keyword', $('cKeyword').value.trim());
  try {
    allCases = await request(`${CASE_API}?${params.toString()}`);
    // 按项目分组、项目内按序号从 1 往下排（未关联排最后）
    allCases.sort((a, b) => {
      const pa = a.projectId ?? Number.MAX_SAFE_INTEGER;
      const pb = b.projectId ?? Number.MAX_SAFE_INTEGER;
      return pa - pb || (a.seq ?? a.id) - (b.seq ?? b.id);
    });
    renderCases();
  } catch (e) {
    showToast(e.message, true);
  }
  loadCaseSummary();
}

/* 用例汇总分析（列表下方图表，全量数据不受筛选影响） */
async function loadCaseSummary() {
  try {
    const cases = await request(CASE_API);
    renderCaseSummary(cases);
  } catch {
    /* 汇总失败不影响列表 */
  }
}

function renderCaseSummary(cases) {
  // 按执行状态汇总，四态全部列出便于对比
  const statusMap = {};
  for (const k of Object.keys(CASE_STATUS_TEXT)) statusMap[k] = 0;
  for (const c of cases) statusMap[c.status] = (statusMap[c.status] || 0) + 1;
  renderBarChart('chartCaseStatus', statusMap, CASE_STATUS_TEXT);

  // 同步左侧项目栏的用例计数
  caseCountByProject = new Map();
  for (const c of cases) {
    caseCountByProject.set(c.projectId, (caseCountByProject.get(c.projectId) || 0) + 1);
  }
  renderCaseSidebar();

  // 按项目汇总
  const rows = bucketByProject(cases, '未关联');
  if (!rows.length) {
    ['chartCaseProjCount', 'chartCaseProjStatus'].forEach((id) => {
      $(id).innerHTML = '<p class="chart-empty">暂无数据</p>';
    });
    return;
  }
  const countMap = {};
  for (const r of rows) countMap[r.name] = r.items.length;
  renderBarChart('chartCaseProjCount', countMap, null);
  renderStackChart('chartCaseProjStatus', rows, 'status', CASE_STATUS_TEXT, CASE_STATUS_COLOR);
}

/* ===== 测试用例左侧项目栏（与文档库同款布局，计数为用例数） ===== */
let caseProjPage = 1;
let caseProjPageSize = 10;
let caseCountByProject = new Map(); // projectId -> 用例数

function renderCaseSidebar() {
  const list = $('caseProjList');
  const totalPages = Math.max(1, Math.ceil(projects.length / caseProjPageSize));
  if (caseProjPage > totalPages) caseProjPage = totalPages;
  const pageProjects = projects.slice((caseProjPage - 1) * caseProjPageSize, caseProjPage * caseProjPageSize);
  const selected = $('cProject').value;
  const items = [
    `<li class="proj-item ${selected === '' ? 'active' : ''}" data-id="">
      <span class="proj-item-name">📋 全部项目</span>
    </li>`,
  ];
  for (const p of pageProjects) {
    const active = selected === String(p.id);
    const count = caseCountByProject.get(p.id) || 0;
    items.push(`
      <li class="proj-item ${active ? 'active' : ''}" data-id="${p.id}" title="${escapeHtml(p.description || p.name)}">
        <span class="proj-item-name">${escapeHtml(p.name)}</span>
        <span class="proj-item-count ${count === 0 ? 'zero' : ''}">${count}</span>
        <span class="proj-item-ops">
          <button data-op="edit" data-id="${p.id}" title="编辑项目">✎</button>
          <button data-op="del" data-id="${p.id}" title="删除项目">×</button>
        </span>
      </li>`);
  }
  if (!projects.length) {
    items.push('<li class="proj-list-empty">暂无项目，点上方＋创建</li>');
  }
  list.innerHTML = items.join('');
  // 不满一页时也保持固定高度（1 个「全部项目」+ 每页项目位）
  list.style.minHeight = `${(caseProjPageSize + 1) * 37 + 16}px`;
  $('caseProjPageInfo').textContent = `${caseProjPage}/${totalPages}`;
  $('caseProjPrev').disabled = caseProjPage <= 1;
  $('caseProjNext').disabled = caseProjPage >= totalPages;
}

$('caseProjPrev').addEventListener('click', () => {
  caseProjPage--;
  renderCaseSidebar();
});
$('caseProjNext').addEventListener('click', () => {
  caseProjPage++;
  renderCaseSidebar();
});
$('caseProjPageSize').addEventListener('change', (e) => {
  caseProjPageSize = Number(e.target.value);
  caseProjPage = 1;
  renderCaseSidebar();
});

$('btnCaseNewProject').addEventListener('click', () => {
  $('projModalTitle').textContent = '新建项目';
  $('projForm').reset();
  $('projId').value = '';
  openModal($('projMask'));
});

$('caseProjList').addEventListener('click', async (e) => {
  const opBtn = e.target.closest('button[data-op]');
  if (opBtn) {
    const id = Number(opBtn.dataset.id);
    if (opBtn.dataset.op === 'edit') {
      openProjectEditModal(id);
    } else if (opBtn.dataset.op === 'del') {
      const p = projects.find((x) => x.id === id);
      if (!confirm(`确定删除项目「${p ? p.name : '#' + id}」吗？`)) return;
      try {
        await request(`${PROJECT_API}/${id}`, { method: 'DELETE' });
        showToast('删除成功');
        await refreshProjects();
        loadCases();
      } catch (err) {
        showToast(err.message, true);
      }
    }
    return;
  }
  // 点击项目项 → 切换用例筛选（与筛选栏下拉联动）
  const item = e.target.closest('.proj-item');
  if (!item) return;
  $('cProject').value = item.dataset.id;
  casePage = 1;
  renderCaseSidebar();
  loadCases();
});

function renderCases() {
  const tbody = $('caseTbody');
  tbody.innerHTML = '';
  const totalPages = Math.max(1, Math.ceil(allCases.length / casePageSize));
  if (casePage > totalPages) casePage = totalPages;
  const pageCases = allCases.slice((casePage - 1) * casePageSize, casePage * casePageSize);
  for (const tc of pageCases) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${caseNo(tc)}</td>
      <td class="bug-title-cell" title="${escapeHtml(tc.steps || '')}">${escapeHtml(tc.title)}</td>
      <td>${tc.projectId != null ? `<span class="tag proj-tag">${escapeHtml(projectName(tc.projectId))}</span>` : '<span class="detail-empty">未关联</span>'}</td>
      <td>${tc.module ? escapeHtml(tc.module) : '-'}</td>
      <td><span class="tag cp-${tc.priority}">${CASE_PRIORITY_TEXT[tc.priority] || tc.priority}</span></td>
      <td><span class="tag cs-${tc.status}">${CASE_STATUS_TEXT[tc.status] || tc.status}</span></td>
      <td>${escapeHtml(tc.executor || '-')}</td>
      <td>${formatTime(tc.executedAt)}</td>
      <td class="op-cell">
        <button class="btn btn-sm" data-op="detail" data-id="${tc.id}">详情</button>
        <button class="btn btn-sm" data-op="exec" data-id="${tc.id}">执行</button>
        <button class="btn btn-sm" data-op="edit" data-id="${tc.id}">编辑</button>
        <button class="btn btn-sm btn-danger" data-op="del" data-id="${tc.id}">删除</button>
      </td>`;
    tbody.appendChild(tr);
  }
  if (!allCases.length) {
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    tr.innerHTML = '<td colspan="9">暂无用例，点右上方「+ 新建用例」创建</td>';
    tbody.appendChild(tr);
  }
  // 不满一页时用空行补齐，保持表格高度固定
  const rendered = pageCases.length + (allCases.length ? 0 : 1);
  for (let i = rendered; i < casePageSize; i++) {
    const tr = document.createElement('tr');
    tr.className = 'filler-row';
    tr.innerHTML = '<td colspan="9">&nbsp;</td>';
    tbody.appendChild(tr);
  }

  renderCasePager(totalPages);
}

/* 用例列表分页栏 */
function renderCasePager(totalPages) {
  const nums = pageNumbers(casePage, totalPages)
    .map((n) =>
      n === '…'
        ? '<span class="pager-ellipsis">…</span>'
        : `<button class="pager-btn ${n === casePage ? 'active' : ''}" data-page="${n}">${n}</button>`
    )
    .join('');
  $('casePager').innerHTML = `
    <span class="pager-total">共 ${allCases.length} 条</span>
    <select id="casePageSize" class="pager-size">
      ${[10, 20, 50].map((s) => `<option value="${s}" ${s === casePageSize ? 'selected' : ''}>${s} 条/页</option>`).join('')}
    </select>
    <button class="pager-btn" data-page="${casePage - 1}" ${casePage <= 1 ? 'disabled' : ''}>上一页</button>
    ${nums}
    <button class="pager-btn" data-page="${casePage + 1}" ${casePage >= totalPages ? 'disabled' : ''}>下一页</button>`;
}

$('casePager').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-page]');
  if (!btn || btn.disabled) return;
  casePage = Number(btn.dataset.page);
  renderCases();
});
$('casePager').addEventListener('change', (e) => {
  if (e.target.id === 'casePageSize') {
    casePageSize = Number(e.target.value);
    casePage = 1;
    renderCases();
  }
});

$('btnCaseSearch').addEventListener('click', loadCases);
$('btnCaseReset').addEventListener('click', () => {
  $('cKeyword').value = '';
  $('cProject').value = '';
  $('cStatus').value = '';
  $('cPriority').value = '';
  loadCases();
});
$('cKeyword').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadCases();
});

/* 用例列表操作 */
$('caseTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const tc = allCases.find((c) => c.id === id);
  if (!tc) return;
  const op = btn.dataset.op;
  if (op === 'detail') {
    openCaseDetail(tc);
  } else if (op === 'exec') {
    openCaseExecModal(tc);
  } else if (op === 'edit') {
    openCaseEditModal(tc);
  } else if (op === 'del') {
    if (!confirm(`确定删除用例 ${caseNo(tc)}「${tc.title}」吗？`)) return;
    try {
      await request(`${CASE_API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
      loadCases();
    } catch (err) {
      showToast(err.message, true);
    }
  }
});

/* 新建/编辑用例弹窗 */
$('btnCaseNew').addEventListener('click', () => {
  $('caseModalTitle').textContent = '新建用例';
  $('caseForm').reset();
  $('caseId').value = '';
  $('caseProject').value = $('cProject').value; // 默认带入当前筛选的项目
  openModal($('caseMask'));
});

function openCaseEditModal(tc) {
  $('caseModalTitle').textContent = `编辑用例 ${caseNo(tc)}`;
  $('caseForm').reset();
  $('caseId').value = tc.id;
  $('caseTitle').value = tc.title;
  $('caseProject').value = tc.projectId != null ? String(tc.projectId) : '';
  $('caseModule').value = tc.module || '';
  $('casePriority').value = tc.priority;
  $('caseDesigner').value = tc.designer || '';
  $('casePrecondition').value = tc.precondition || '';
  $('caseSteps').value = tc.steps || '';
  $('caseExpected').value = tc.expectedResult || '';
  openModal($('caseMask'));
}

$('btnCaseCancel').addEventListener('click', () => closeModal($('caseMask')));

$('caseForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('caseId').value;
  const payload = {
    title: $('caseTitle').value.trim(),
    projectId: $('caseProject').value ? Number($('caseProject').value) : null,
    module: $('caseModule').value.trim(),
    priority: $('casePriority').value,
    designer: $('caseDesigner').value.trim(),
    precondition: $('casePrecondition').value.trim(),
    steps: $('caseSteps').value.trim(),
    expectedResult: $('caseExpected').value.trim(),
  };
  try {
    if (id) {
      await request(`${CASE_API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      await request(CASE_API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('创建成功');
    }
    closeModal($('caseMask'));
    loadCases();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 执行用例弹窗 */
function openCaseExecModal(tc) {
  $('caseExecId').value = tc.id;
  $('caseExecInfo').textContent = `${caseNo(tc)}「${tc.title}」当前状态：${CASE_STATUS_TEXT[tc.status]}`;
  $('caseExecForm').reset();
  $('caseExecStatus').value = 'PASS';
  $('caseExecResult').value = tc.actualResult || '';
  $('caseExecutor').value = tc.executor || '';
  openModal($('caseExecMask'));
}

$('btnCaseExecCancel').addEventListener('click', () => closeModal($('caseExecMask')));

$('caseExecForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('caseExecId').value;
  const payload = {
    status: $('caseExecStatus').value,
    actualResult: $('caseExecResult').value.trim(),
    executor: $('caseExecutor').value.trim(),
  };
  try {
    await request(`${CASE_API}/${id}/execute`, { method: 'PUT', body: JSON.stringify(payload) });
    showToast('执行结果已记录');
    closeModal($('caseExecMask'));
    loadCases();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 用例详情弹窗 */
let caseDetailId = null; // 当前详情弹窗展示的用例 ID

/* 详情弹窗字段：与新建表单一致的「字段名在上、值框在下」展现 */
function caseDetailField(name, valueHtml, multi = false) {
  return `<div class="detail-field">${name}<div class="detail-field-box${multi ? ' detail-field-multi' : ''}">${valueHtml}</div></div>`;
}

function caseDetailText(value, emptyText) {
  return value ? escapeHtml(value) : `<span class="detail-empty">${emptyText}</span>`;
}

function openCaseDetail(tc) {
  caseDetailId = tc.id;
  $('caseDetailTitle').textContent = `用例 ${caseNo(tc)} 详情`;
  $('caseDetailBody').innerHTML = `
    ${caseDetailField('用例标题', escapeHtml(tc.title))}
    <div class="form-row">
      ${caseDetailField('所属项目', tc.projectId != null ? escapeHtml(projectName(tc.projectId)) : '<span class="detail-empty">未关联</span>')}
      ${caseDetailField('所属模块', caseDetailText(tc.module, '未填写'))}
    </div>
    <div class="form-row">
      ${caseDetailField('优先级', `<span class="tag cp-${tc.priority}">${CASE_PRIORITY_TEXT[tc.priority]}</span>`)}
      ${caseDetailField('编写人', caseDetailText(tc.designer, '未填写'))}
    </div>
    ${caseDetailField('前置条件', caseDetailText(tc.precondition, '无'), true)}
    ${caseDetailField('测试步骤', caseDetailText(tc.steps, '无'), true)}
    ${caseDetailField('预期结果', caseDetailText(tc.expectedResult, '无'), true)}
    <div class="detail-section-title">执行信息</div>
    <div class="form-row">
      ${caseDetailField('执行状态', `<span class="tag cs-${tc.status}">${CASE_STATUS_TEXT[tc.status]}</span>`)}
      ${caseDetailField('执行人', caseDetailText(tc.executor, '未执行'))}
    </div>
    ${caseDetailField('实际结果', caseDetailText(tc.actualResult, '无'), true)}
    <div class="form-row">
      ${caseDetailField('最近执行时间', formatTime(tc.executedAt))}
      ${caseDetailField('创建时间', formatTime(tc.createdAt))}
      ${caseDetailField('更新时间', formatTime(tc.updatedAt))}
    </div>`;
  openModal($('caseDetailMask'));
}

$('btnCaseDetailClose').addEventListener('click', () => closeModal($('caseDetailMask')));

$('btnCaseDetailEdit').addEventListener('click', () => {
  closeModal($('caseDetailMask'));
  const tc = allCases.find((c) => c.id === caseDetailId);
  if (tc) openCaseEditModal(tc);
});

$('btnCaseDetailExec').addEventListener('click', () => {
  closeModal($('caseDetailMask'));
  const tc = allCases.find((c) => c.id === caseDetailId);
  if (tc) openCaseExecModal(tc);
});

/* ===== 用例导入 ===== */
const CASE_IMPORT_HEADERS = ['用例标题', '所属项目', '所属模块', '优先级', '前置条件', '测试步骤', '预期结果', '编写人'];
let caseImportRows = []; // 解析后待导入的用例数组

$('btnCaseImport').addEventListener('click', () => {
  caseImportRows = [];
  $('caseImportFile').value = '';
  $('caseImportPreviewWrap').classList.add('hidden');
  $('btnCaseImportConfirm').disabled = true;
  openModal($('caseImportMask'));
});

$('btnCaseImportCancel').addEventListener('click', () => closeModal($('caseImportMask')));

/* 下载导入模板（带 BOM 保证 Excel 打开不乱码，附两行示例） */
$('btnCaseTemplate').addEventListener('click', () => {
  const example1 = ['登录-密码错误提示', projects[0] ? projects[0].name : '', '登录模块', 'P1', '已注册账号', '1. 打开登录页\n2. 输入错误密码\n3. 点击登录', '提示「账号或密码错误」', '张三'];
  const example2 = ['首页-轮播图展示', '', '首页', 'P2', '', '打开首页观察轮播图', '轮播图正常轮播切换', ''];
  const lines = [CASE_IMPORT_HEADERS, example1, example2]
    .map((row) => row.map(csvEscape).join(','))
    .join('\r\n');
  const blob = new Blob(['\uFEFF' + lines], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '测试用例导入模板.csv';
  a.click();
  URL.revokeObjectURL(a.href);
});

/* CSV 字段转义：含逗号/引号/换行时用双引号包裹 */
function csvEscape(v) {
  const s = String(v ?? '');
  return /[",\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

/* CSV 解析：支持双引号包裹、字段内逗号与换行 */
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else field += ch;
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      row.push(field); field = '';
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      rows.push(row); row = [];
    } else {
      field += ch;
    }
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  // 去掉全空行
  return rows.filter((r) => r.some((c) => c.trim() !== ''));
}

/* 选文件后解析并预览（UTF-8 乱码时自动按 GBK 重读，兼容 Excel 另存的 CSV） */
$('caseImportFile').addEventListener('change', async () => {
  const file = $('caseImportFile').files[0];
  if (!file) return;
  const buf = await file.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\uFFFD')) text = new TextDecoder('gbk').decode(buf);
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = parseCsv(text);
  if (!rows.length) return showToast('文件内容为空', true);

  // 表头容错：按模板列名定位列序，找不到「用例标题」列则拒绝
  const header = rows[0].map((h) => h.trim());
  const colIdx = CASE_IMPORT_HEADERS.map((name) => header.findIndex((h) => h.includes(name)));
  if (colIdx[0] === -1) return showToast('未识别到「用例标题」列，请使用下载的模板填写', true);

  caseImportRows = [];
  const previewTrs = [];
  const errors = [];
  rows.slice(1).forEach((r, i) => {
    const cell = (idx) => (colIdx[idx] >= 0 ? (r[colIdx[idx]] || '').trim() : '');
    const title = cell(0);
    const projName = cell(1);
    const priority = cell(3).toUpperCase();
    const proj = projName ? projects.find((p) => p.name === projName || p.code === projName.toUpperCase()) : null;
    const rowErrors = [];
    if (!title) rowErrors.push('标题为空');
    if (projName && !proj) rowErrors.push(`项目「${projName}」不存在`);
    if (priority && !CASE_PRIORITY_TEXT[priority]) rowErrors.push(`优先级「${cell(3)}」无效（应为 P0~P3）`);
    if (rowErrors.length) {
      errors.push(`第 ${i + 2} 行：${rowErrors.join('、')}`);
    } else {
      caseImportRows.push({
        title,
        projectId: proj ? proj.id : null,
        module: cell(2),
        priority: priority || 'P2',
        precondition: cell(4),
        steps: cell(5),
        expectedResult: cell(6),
        designer: cell(7),
      });
    }
    previewTrs.push(`<tr class="${rowErrors.length ? 'import-row-error' : ''}" title="${escapeHtml(rowErrors.join('、'))}">
      <td class="seq-col">${i + 2}</td>
      <td class="bug-title-cell">${escapeHtml(title) || '<span class="detail-empty">空</span>'}</td>
      <td>${proj ? escapeHtml(proj.name) : projName ? `❌ ${escapeHtml(projName)}` : '未关联'}</td>
      <td>${escapeHtml(cell(2)) || '-'}</td>
      <td>${escapeHtml(cell(3)) || 'P2'}</td>
      <td class="bug-title-cell">${escapeHtml(cell(4)) || '-'}</td>
      <td class="bug-title-cell" title="${escapeHtml(cell(5))}">${escapeHtml(cell(5)) || '-'}</td>
      <td class="bug-title-cell">${escapeHtml(cell(6)) || '-'}</td>
      <td>${escapeHtml(cell(7)) || '-'}</td>
    </tr>`);
  });

  $('caseImportTbody').innerHTML = previewTrs.join('');
  $('caseImportSummary').innerHTML = errors.length
    ? `共 ${rows.length - 1} 行：可导入 <b>${caseImportRows.length}</b> 条，<b class="import-error-text">${errors.length} 条有误将跳过</b>（标红行悬停可看原因）`
    : `共 ${rows.length - 1} 行，均可导入`;
  $('caseImportPreviewWrap').classList.remove('hidden');
  $('btnCaseImportConfirm').disabled = !caseImportRows.length;
});

$('btnCaseImportConfirm').addEventListener('click', async () => {
  if (!caseImportRows.length) return;
  $('btnCaseImportConfirm').disabled = true;
  try {
    const result = await request(`${CASE_API}/import`, { method: 'POST', body: JSON.stringify(caseImportRows) });
    const failed = result.failures ? result.failures.length : 0;
    showToast(`导入完成：成功 ${result.success} 条${failed ? `，失败 ${failed} 条` : ''}`, failed > 0);
    closeModal($('caseImportMask'));
    loadCases();
  } catch (err) {
    showToast(err.message, true);
    $('btnCaseImportConfirm').disabled = false;
  }
});

/* ===== 全局快捷键 ===== */
/* ESC 关闭当前打开的弹窗；多层叠加时（如详情上的图片预览）先关最上层 */
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const masks = document.querySelectorAll('.modal-mask.modal-visible');
  if (masks.length) closeModal(masks[masks.length - 1]);
});

/* ===== 需求管理 ===== */
let allRequirements = []; // 当前筛选条件下的需求列表，前端分页
let reqPage = 1;
let reqPageSize = 10;

/* 需求展示编号：项目编号-R序号（如 MALL-R1），无项目编号时退回 #R-序号 */
function reqNo(req) {
  const no = req.seq ?? req.id;
  const p = projects.find((x) => x.id === req.projectId);
  return p && p.code ? `${p.code}-R${no}` : `#R-${no}`;
}

async function loadRequirements() {
  const params = new URLSearchParams();
  if ($('reqProject').value) params.set('projectId', $('reqProject').value);
  if ($('reqStatus').value) params.set('status', $('reqStatus').value);
  if ($('reqPriority').value) params.set('priority', $('reqPriority').value);
  if ($('reqPeriod').value.trim()) params.set('period', $('reqPeriod').value.trim());
  if ($('reqKeyword').value.trim()) params.set('keyword', $('reqKeyword').value.trim());
  try {
    allRequirements = await request(`${REQ_API}?${params.toString()}`);
    // 按项目分组、项目内按序号从 1 往下排（未关联排最后）
    allRequirements.sort((a, b) => {
      const pa = a.projectId ?? Number.MAX_SAFE_INTEGER;
      const pb = b.projectId ?? Number.MAX_SAFE_INTEGER;
      return pa - pb || (a.seq ?? a.id) - (b.seq ?? b.id);
    });
    // 动态填充期 datalist
    const periods = [...new Set(allRequirements.map((r) => r.period).filter(Boolean))];
    $('reqPeriodList').innerHTML = periods.map((p) => `<option value="${escapeHtml(p)}">`).join('');
    $('rPeriodList').innerHTML = periods.map((p) => `<option value="${escapeHtml(p)}">`).join('');
    renderRequirements();
  } catch (e) {
    showToast(e.message, true);
  }
  loadReqSummary();
}

/* 需求汇总分析（列表下方图表，全量数据不受筛选影响） */
async function loadReqSummary() {
  try {
    const reqs = await request(REQ_API);
    renderReqSummary(reqs);
  } catch {
    /* 汇总失败不影响列表 */
  }
}

function renderReqSummary(reqs) {
  // 按状态汇总
  const statusMap = {};
  for (const k of Object.keys(REQ_STATUS_TEXT)) statusMap[k] = 0;
  for (const r of reqs) statusMap[r.status] = (statusMap[r.status] || 0) + 1;
  renderBarChart('chartReqStatus', statusMap, REQ_STATUS_TEXT);

  // 同步左侧项目栏的需求计数
  reqCountByProject = new Map();
  for (const r of reqs) {
    reqCountByProject.set(r.projectId, (reqCountByProject.get(r.projectId) || 0) + 1);
  }
  renderReqSidebar();

  // 按项目汇总
  const rows = bucketByProject(reqs, '未关联');
  if (!rows.length) {
    ['chartReqProjCount', 'chartReqProjStatus'].forEach((id) => {
      $(id).innerHTML = '<p class="chart-empty">暂无数据</p>';
    });
    return;
  }
  const countMap = {};
  for (const r of rows) countMap[r.name] = r.items.length;
  renderBarChart('chartReqProjCount', countMap, null);
  renderStackChart('chartReqProjStatus', rows, 'status', REQ_STATUS_TEXT, REQ_STATUS_COLOR);
}

/* ===== 需求管理左侧项目栏（与测试用例同款布局，计数为需求数） ===== */
let reqProjPage = 1;
let reqProjPageSize = 10;
let reqCountByProject = new Map(); // projectId -> 需求数

function renderReqSidebar() {
  const list = $('reqProjList');
  const totalPages = Math.max(1, Math.ceil(projects.length / reqProjPageSize));
  if (reqProjPage > totalPages) reqProjPage = totalPages;
  const pageProjects = projects.slice((reqProjPage - 1) * reqProjPageSize, reqProjPage * reqProjPageSize);
  const selected = $('reqProject').value;
  const items = [
    `<li class="proj-item ${selected === '' ? 'active' : ''}" data-id="">
      <span class="proj-item-name">📋 全部项目</span>
    </li>`,
  ];
  for (const p of pageProjects) {
    const active = selected === String(p.id);
    const count = reqCountByProject.get(p.id) || 0;
    items.push(`
      <li class="proj-item ${active ? 'active' : ''}" data-id="${p.id}" title="${escapeHtml(p.description || p.name)}">
        <span class="proj-item-name">${escapeHtml(p.name)}</span>
        <span class="proj-item-count ${count === 0 ? 'zero' : ''}">${count}</span>
        <span class="proj-item-ops">
          <button data-op="edit" data-id="${p.id}" title="编辑项目">✎</button>
          <button data-op="del" data-id="${p.id}" title="删除项目">×</button>
        </span>
      </li>`);
  }
  if (!projects.length) {
    items.push('<li class="proj-list-empty">暂无项目，点上方＋创建</li>');
  }
  list.innerHTML = items.join('');
  list.style.minHeight = `${(reqProjPageSize + 1) * 37 + 16}px`;
  $('reqProjPageInfo').textContent = `${reqProjPage}/${totalPages}`;
  $('reqProjPrev').disabled = reqProjPage <= 1;
  $('reqProjNext').disabled = reqProjPage >= totalPages;
}

$('reqProjPrev').addEventListener('click', () => {
  reqProjPage--;
  renderReqSidebar();
});
$('reqProjNext').addEventListener('click', () => {
  reqProjPage++;
  renderReqSidebar();
});
$('reqProjPageSize').addEventListener('change', (e) => {
  reqProjPageSize = Number(e.target.value);
  reqProjPage = 1;
  renderReqSidebar();
});

$('btnReqNewProject').addEventListener('click', () => {
  $('projModalTitle').textContent = '新建项目';
  $('projForm').reset();
  $('projId').value = '';
  openModal($('projMask'));
});

$('reqProjList').addEventListener('click', async (e) => {
  const opBtn = e.target.closest('button[data-op]');
  if (opBtn) {
    const id = Number(opBtn.dataset.id);
    if (opBtn.dataset.op === 'edit') {
      openProjectEditModal(id);
    } else if (opBtn.dataset.op === 'del') {
      const p = projects.find((x) => x.id === id);
      if (!confirm(`确定删除项目「${p ? p.name : '#' + id}」吗？`)) return;
      try {
        await request(`${PROJECT_API}/${id}`, { method: 'DELETE' });
        showToast('删除成功');
        await refreshProjects();
        loadRequirements();
      } catch (err) {
        showToast(err.message, true);
      }
    }
    return;
  }
  // 点击项目项 → 切换需求筛选（与筛选栏下拉联动）
  const item = e.target.closest('.proj-item');
  if (!item) return;
  $('reqProject').value = item.dataset.id;
  reqPage = 1;
  renderReqSidebar();
  loadRequirements();
});

function renderRequirements() {
  const tbody = $('reqTbody');
  tbody.innerHTML = '';
  const totalPages = Math.max(1, Math.ceil(allRequirements.length / reqPageSize));
  if (reqPage > totalPages) reqPage = totalPages;
  const pageReqs = allRequirements.slice((reqPage - 1) * reqPageSize, reqPage * reqPageSize);
  for (const req of pageReqs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${reqNo(req)}</td>
      <td class="bug-title-cell" title="${escapeHtml(req.description || '')}">${escapeHtml(req.title)}</td>
      <td>${req.projectId != null ? `<span class="tag proj-tag">${escapeHtml(projectName(req.projectId))}</span>` : '<span class="detail-empty">未关联</span>'}</td>
      <td>${req.period ? escapeHtml(req.period) : '-'}</td>
      <td>${req.module ? escapeHtml(req.module) : '-'}</td>
      <td><span class="tag cp-${req.priority}">${REQ_PRIORITY_TEXT[req.priority] || req.priority}</span></td>
      <td><span class="tag rs-${req.status}">${REQ_STATUS_TEXT[req.status] || req.status}</span></td>
      <td>${escapeHtml(req.proposer || '-')}</td>
      <td class="op-cell">
        <button class="btn btn-sm" data-op="detail" data-id="${req.id}">详情</button>
        <button class="btn btn-sm" data-op="edit" data-id="${req.id}">编辑</button>
        <button class="btn btn-sm btn-danger" data-op="del" data-id="${req.id}">删除</button>
      </td>`;
    tbody.appendChild(tr);
  }
  if (!allRequirements.length) {
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    tr.innerHTML = '<td colspan="9">暂无需求，点右上方「+ 新建需求」创建</td>';
    tbody.appendChild(tr);
  }
  // 不满一页时用空行补齐，保持表格高度固定
  const rendered = pageReqs.length + (allRequirements.length ? 0 : 1);
  for (let i = rendered; i < reqPageSize; i++) {
    const tr = document.createElement('tr');
    tr.className = 'filler-row';
    tr.innerHTML = '<td colspan="9">&nbsp;</td>';
    tbody.appendChild(tr);
  }

  renderReqPager(totalPages);
}

/* 需求列表分页栏 */
function renderReqPager(totalPages) {
  const nums = pageNumbers(reqPage, totalPages)
    .map((n) =>
      n === '…'
        ? '<span class="pager-ellipsis">…</span>'
        : `<button class="pager-btn ${n === reqPage ? 'active' : ''}" data-page="${n}">${n}</button>`
    )
    .join('');
  $('reqPager').innerHTML = `
    <span class="pager-total">共 ${allRequirements.length} 条</span>
    <select id="reqPageSize" class="pager-size">
      ${[10, 20, 50].map((s) => `<option value="${s}" ${s === reqPageSize ? 'selected' : ''}>${s} 条/页</option>`).join('')}
    </select>
    <button class="pager-btn" data-page="${reqPage - 1}" ${reqPage <= 1 ? 'disabled' : ''}>上一页</button>
    ${nums}
    <button class="pager-btn" data-page="${reqPage + 1}" ${reqPage >= totalPages ? 'disabled' : ''}>下一页</button>`;
}

$('reqPager').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-page]');
  if (!btn || btn.disabled) return;
  reqPage = Number(btn.dataset.page);
  renderRequirements();
});
$('reqPager').addEventListener('change', (e) => {
  if (e.target.id === 'reqPageSize') {
    reqPageSize = Number(e.target.value);
    reqPage = 1;
    renderRequirements();
  }
});

$('reqSearch').addEventListener('click', loadRequirements);
$('reqReset').addEventListener('click', () => {
  $('reqKeyword').value = '';
  $('reqProject').value = '';
  $('reqStatus').value = '';
  $('reqPriority').value = '';
  $('reqPeriod').value = '';
  loadRequirements();
});
$('reqKeyword').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadRequirements();
});

/* 需求列表操作 */
$('reqTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const req = allRequirements.find((r) => r.id === id);
  if (!req) return;
  const op = btn.dataset.op;
  if (op === 'detail') {
    openReqDetail(req);
  } else if (op === 'edit') {
    openReqEditModal(req);
  } else if (op === 'del') {
    if (!confirm(`确定删除需求 ${reqNo(req)}「${req.title}」吗？`)) return;
    try {
      await request(`${REQ_API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
      loadRequirements();
    } catch (err) {
      showToast(err.message, true);
    }
  }
});

/* 新建/编辑需求弹窗 */
$('reqCreate').addEventListener('click', () => {
  $('reqModalTitle').textContent = '新建需求';
  $('reqForm').reset();
  $('rId').value = '';
  $('rProject').value = $('reqProject').value; // 默认带入当前筛选的项目
  openModal($('reqMask'));
});

function openReqEditModal(req) {
  $('reqModalTitle').textContent = `编辑需求 ${reqNo(req)}`;
  $('reqForm').reset();
  $('rId').value = req.id;
  $('rTitle').value = req.title;
  $('rProject').value = req.projectId != null ? String(req.projectId) : '';
  $('rPeriod').value = req.period || '';
  $('rPriority').value = req.priority;
  $('rStatus').value = req.status;
  $('rModule').value = req.module || '';
  $('rProposer').value = req.proposer || '';
  $('rAssignee').value = req.assignee || '';
  $('rDescription').value = req.description || '';
  openModal($('reqMask'));
}

$('btnReqCancel').addEventListener('click', () => closeModal($('reqMask')));

$('reqForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('rId').value;
  const payload = {
    title: $('rTitle').value.trim(),
    projectId: $('rProject').value ? Number($('rProject').value) : null,
    period: $('rPeriod').value.trim(),
    priority: $('rPriority').value,
    status: $('rStatus').value,
    module: $('rModule').value.trim(),
    proposer: $('rProposer').value.trim(),
    assignee: $('rAssignee').value.trim(),
    description: $('rDescription').value.trim(),
  };
  try {
    if (id) {
      await request(`${REQ_API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      await request(REQ_API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('创建成功');
    }
    closeModal($('reqMask'));
    loadRequirements();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 需求详情弹窗 */
let reqDetailId = null; // 当前详情弹窗展示的需求 ID

/* 详情弹窗字段：与新建表单一致的「字段名在上、值框在下」展现 */
function reqDetailField(name, valueHtml, multi = false) {
  return `<div class="detail-field">${name}<div class="detail-field-box${multi ? ' detail-field-multi' : ''}">${valueHtml}</div></div>`;
}

function reqDetailText(value, emptyText) {
  return value ? escapeHtml(value) : `<span class="detail-empty">${emptyText}</span>`;
}

function openReqDetail(req) {
  reqDetailId = req.id;
  $('reqDetailTitle').textContent = `需求 ${reqNo(req)} 详情`;
  $('reqDetailBody').innerHTML = `
    ${reqDetailField('需求标题', escapeHtml(req.title))}
    <div class="form-row">
      ${reqDetailField('所属项目', req.projectId != null ? escapeHtml(projectName(req.projectId)) : '<span class="detail-empty">未关联</span>')}
      ${reqDetailField('所属期', reqDetailText(req.period, '未填写'))}
    </div>
    <div class="form-row">
      ${reqDetailField('优先级', `<span class="tag cp-${req.priority}">${REQ_PRIORITY_TEXT[req.priority]}</span>`)}
      ${reqDetailField('状态', `<span class="tag rs-${req.status}">${REQ_STATUS_TEXT[req.status]}</span>`)}
    </div>
    <div class="form-row">
      ${reqDetailField('所属模块', reqDetailText(req.module, '未填写'))}
      ${reqDetailField('提出人', reqDetailText(req.proposer, '未填写'))}
    </div>
    ${reqDetailField('负责人', reqDetailText(req.assignee, '未指定'))}
    ${reqDetailField('需求描述', reqDetailText(req.description, '无'), true)}
    <div class="form-row">
      ${reqDetailField('创建时间', formatTime(req.createdAt))}
      ${reqDetailField('更新时间', formatTime(req.updatedAt))}
    </div>`;
  openModal($('reqDetailMask'));
}

$('btnReqDetailClose').addEventListener('click', () => closeModal($('reqDetailMask')));

$('btnReqDetailEdit').addEventListener('click', () => {
  closeModal($('reqDetailMask'));
  const req = allRequirements.find((r) => r.id === reqDetailId);
  if (req) openReqEditModal(req);
});

/* ===== 工具 ===== */
function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function formatTime(isoStr) {
  if (!isoStr) return '-';
  return isoStr.replace('T', ' ').substring(0, 16);
}

/* ===== 初始化 ===== */
async function init() {
  const token = getToken();
  if (!token) {
    showLogin();
    return;
  }
  try {
    currentUser = await request(`${AUTH_API}/me`);
    applyCurrentUser();
    await refreshProjects();
    loadBugs();
  } catch {
    showLogin();
  }
}

function showLogin() {
  currentUser = null;
  $('loginMask').classList.add('modal-visible');
  $('loginMask').classList.remove('hidden');
}

function hideLogin() {
  closeModal($('loginMask'));
}

function applyCurrentUser() {
  if (!currentUser) return;
  $('currentUser').textContent = currentUser.displayName || currentUser.username || '';
  const isAdmin = currentUser.role === 'ADMIN';
  // 新建用户按钮仅管理员可见（普通用户可进系统管理查看协作成员，但不能增删改）
  document.querySelectorAll('#btnNewUser').forEach((b) => {
    b.classList.toggle('hidden', !isAdmin);
  });
  // 新建项目按钮（各侧栏）按角色显隐
  document.querySelectorAll('.proj-add-btn').forEach((b) => {
    b.classList.toggle('hidden', !isAdmin);
  });
}

/* 登录提交 */
$('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('loginUsername').value.trim();
  const password = $('loginPassword').value;
  if (!username || !password) return showToast('请填写用户名和密码', true);
  try {
    const resp = await fetch(`${AUTH_API}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok) throw new Error((data && data.error) || `登录失败 (${resp.status})`);
    setToken(data.token);
    currentUser = data;
    hideLogin();
    applyCurrentUser();
    try { await refreshProjects(); } catch {}
    loadBugs();
    showToast(`欢迎，${currentUser.displayName || currentUser.username}`);
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 登出 */
$('btnLogout').addEventListener('click', async () => {
  try { await request(`${AUTH_API}/logout`, { method: 'POST' }); } catch {}
  setToken(null);
  showLogin();
  $('loginPassword').value = '';
});

/* ===== 用户管理 ===== */
let allUsers = [];

async function loadUsers() {
  const isAdmin = currentUser && currentUser.role === 'ADMIN';
  $('adminHint').textContent = isAdmin ? '' : '仅显示与你共用项目的协作成员（只读）';
  try {
    allUsers = await request(USER_API);
    renderUsers();
  } catch (e) {
    showToast(e.message, true);
  }
}

function renderUsers() {
  const tbody = $('userTbody');
  tbody.innerHTML = '';
  const isAdmin = currentUser && currentUser.role === 'ADMIN';
  for (const u of allUsers) {
    const tr = document.createElement('tr');
    const projText = (u.projects || []).map((p) => escapeHtml(p.name)).join('、') || '<span class="detail-empty">无</span>';
    const ops = isAdmin
      ? `<button class="btn btn-sm" data-op="edit" data-id="${u.id}">编辑</button>
         <button class="btn btn-sm btn-danger" data-op="del" data-id="${u.id}">删除</button>`
      : '<span class="detail-empty">仅查看</span>';
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${escapeHtml(u.username)}</td>
      <td>${escapeHtml(u.displayName || '-')}</td>
      <td><span class="tag ${u.role === 'ADMIN' ? 'role-admin' : 'role-user'}">${userRoleText(u)}</span></td>
      <td>${u.enabled ? '<span class="tag st-RESOLVED">启用</span>' : '<span class="tag st-CLOSED">禁用</span>'}</td>
      <td class="bug-title-cell">${projText}</td>
      <td>${formatTime(u.createdAt)}</td>
      <td class="op-cell">${ops}</td>`;
    tbody.appendChild(tr);
  }
  if (!allUsers.length) {
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    tr.innerHTML = isAdmin
      ? '<td colspan="8">暂无用户，点右上方「+ 新建用户」创建</td>'
      : '<td colspan="8">暂无与你共用项目的协作成员</td>';
    tbody.appendChild(tr);
  }
}

// 普通用户看到的都是协作成员（非管理员），统一显示为「普通用户」；
// 管理员视图下管理员本应显示「管理员」，但当前 list 已过滤掉管理员对普通用户不可见，
// 故此处对管理员账号也标注「普通用户」仅出现在管理员自己的列表里——
// 为避免误导，管理员列表里 role===ADMIN 显示「管理员」。
function userRoleText(u) {
  return u.role === 'ADMIN' ? '管理员' : '普通用户';
}

$('userTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const u = allUsers.find((x) => x.id === id);
  if (btn.dataset.op === 'edit') {
    openUserEditModal(u);
  } else if (btn.dataset.op === 'del') {
    if (!confirm(`确定删除用户「${u ? u.username : '#' + id}」吗？`)) return;
    try {
      await request(`${USER_API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
      loadUsers();
    } catch (err) {
      showToast(err.message, true);
    }
  }
});

$('btnNewUser').addEventListener('click', () => {
  $('userModalTitle').textContent = '新建用户';
  $('userForm').reset();
  $('userId').value = '';
  $('userPwdRequired').classList.remove('hidden');
  $('userPassword').required = true;
  renderUserProjectBind([]);
  openModal($('userMask'));
});

function openUserEditModal(u) {
  $('userModalTitle').textContent = `编辑用户 ${u.username}`;
  $('userForm').reset();
  $('userId').value = u.id;
  $('userUsername').value = u.username;
  $('userDisplayName').value = u.displayName || '';
  $('userRole').value = u.role;
  $('userEnabled').checked = u.enabled;
  $('userPwdRequired').classList.add('hidden');
  $('userPassword').required = false;
  $('userPassword').value = '';
  renderUserProjectBind((u.projects || []).map((p) => p.id));
  openModal($('userMask'));
}

function renderUserProjectBind(checkedIds) {
  const box = $('userProjectBind');
  box.innerHTML = '';
  if (!projects.length) {
    box.innerHTML = '<span class="detail-empty">暂无项目，请先在 Bug 列表左侧创建</span>';
    return;
  }
  const set = new Set(checkedIds);
  for (const p of projects) {
    const label = document.createElement('label');
    label.className = 'bind-item';
    label.innerHTML = `<input type="checkbox" value="${p.id}" ${set.has(p.id) ? 'checked' : ''}> ${escapeHtml(p.name)}`;
    box.appendChild(label);
  }
}

$('btnUserCancel').addEventListener('click', () => closeModal($('userMask')));

$('userForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('userId').value;
  const projectIds = [...$('userProjectBind').querySelectorAll('input:checked')].map((c) => Number(c.value));
  const payload = {
    username: $('userUsername').value.trim(),
    password: $('userPassword').value,
    displayName: $('userDisplayName').value.trim(),
    role: $('userRole').value,
    enabled: $('userEnabled').checked,
    projectIds,
  };
  try {
    if (id) {
      await request(`${USER_API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('更新成功');
    } else {
      await request(USER_API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('创建成功');
    }
    closeModal($('userMask'));
    loadUsers();
  } catch (err) {
    showToast(err.message, true);
  }
});

init();
