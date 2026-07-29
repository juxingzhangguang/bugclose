/* BugClose 前端逻辑 */
const API = '/api/bugs';
const PROJECT_API = '/api/projects';
const DOC_API = '/api/docs';

const SEVERITY_TEXT = { CRITICAL: '致命', HIGH: '严重', MEDIUM: '一般', LOW: '轻微' };
const PRIORITY_TEXT = { URGENT: '紧急', HIGH: '高', MEDIUM: '中', LOW: '低' };
const STATUS_TEXT = { NEW: '新建', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭' };
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

/* ===== 视图切换 ===== */
document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const view = btn.dataset.view;
    $('viewList').classList.toggle('hidden', view !== 'list');
    $('viewDashboard').classList.toggle('hidden', view !== 'dashboard');
    $('viewDocs').classList.toggle('hidden', view !== 'docs');
    if (view === 'dashboard') loadStatistics();
    else if (view === 'docs') loadDocs();
    else loadBugs();
  });
});

/* ===== 请求封装 ===== */
async function request(url, options = {}) {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new Error((data && data.error) || `请求失败 (${resp.status})`);
  }
  return data;
}

/* ===== Toast ===== */
let toastTimer = null;
function showToast(msg, isError = false) {
  const toast = $('toast');
  toast.textContent = msg;
  toast.classList.toggle('error', isError);
  toast.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 2200);
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
  fillProjectSelect($('bugProject'), '未关联项目');
  fillProjectSelect($('docProject'), '未关联项目');
  fillProjectSelect($('dProject'), '全部项目');
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
  $('projMask').classList.remove('hidden');
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
  $('modalMask').classList.remove('hidden');
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
    $('modalMask').classList.remove('hidden');
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnCancel').addEventListener('click', () => $('modalMask').classList.add('hidden'));

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
    $('modalMask').classList.add('hidden');
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
      const resp = await fetch('/api/uploads', { method: 'POST', body: fd });
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
    $('imgPreviewMask').classList.remove('hidden');
  }
});

$('imgPreviewMask').addEventListener('click', () => {
  $('imgPreviewMask').classList.add('hidden');
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
    $('detailMask').classList.remove('hidden');
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnDetailClose').addEventListener('click', () => $('detailMask').classList.add('hidden'));

$('btnDetailEdit').addEventListener('click', () => {
  $('detailMask').classList.add('hidden');
  if (detailBugId != null) openEditModal(detailBugId);
});

/* 详情内点击缩略图查看大图 */
$('detailBody').addEventListener('click', (e) => {
  const img = e.target.closest('.image-item img');
  if (img) {
    $('imgPreviewLarge').src = img.src;
    $('imgPreviewMask').classList.remove('hidden');
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
    $('transMask').classList.remove('hidden');
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnTransCancel').addEventListener('click', () => $('transMask').classList.add('hidden'));

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
    $('transMask').classList.add('hidden');
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
  $('projMask').classList.remove('hidden');
});

$('btnProjCancel').addEventListener('click', () => $('projMask').classList.add('hidden'));

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
    $('projMask').classList.add('hidden');
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
  $('projMask').classList.remove('hidden');
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
    $('docVerMask').classList.remove('hidden');
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
    $('docMask').classList.remove('hidden');
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
  $('docMask').classList.remove('hidden');
});

$('btnDocCancel').addEventListener('click', () => $('docMask').classList.add('hidden'));

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
    $('docMask').classList.add('hidden');
    loadDocs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* 更新版本弹窗 */
$('btnDocVerCancel').addEventListener('click', () => $('docVerMask').classList.add('hidden'));

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
    $('docVerMask').classList.add('hidden');
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
    $('docHisMask').classList.remove('hidden');
  } catch (e) {
    showToast(e.message, true);
  }
}

$('btnDocHisClose').addEventListener('click', () => $('docHisMask').classList.add('hidden'));

$('docHisTbody').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-ver]');
  if (!btn) return;
  window.open(`${DOC_API}/${btn.dataset.doc}/versions/${btn.dataset.ver}/download`, '_blank');
});

/* multipart 上传请求（不能带 JSON Content-Type） */
async function uploadRequest(url, formData) {
  const resp = await fetch(url, { method: 'POST', body: formData });
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new Error((data && data.error) || `上传失败 (${resp.status})`);
  }
  return data;
}

/* 文件大小友好显示 */
function formatSize(bytes) {
  if (bytes == null) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

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
(async () => {
  try {
    await refreshProjects();
  } catch {
    /* 项目加载失败不阻塞 Bug 列表 */
  }
  loadBugs();
})();
