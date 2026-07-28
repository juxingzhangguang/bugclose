/* BugClose 前端逻辑 */
const API = '/api/bugs';
const PROJECT_API = '/api/projects';

const SEVERITY_TEXT = { CRITICAL: '致命', HIGH: '严重', MEDIUM: '一般', LOW: '轻微' };
const PRIORITY_TEXT = { URGENT: '紧急', HIGH: '高', MEDIUM: '中', LOW: '低' };
const STATUS_TEXT = { NEW: '新建', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭' };
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
    if (view === 'dashboard') loadStatistics();
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
  fillProjectSelect($('bugProject'), '未关联项目');
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
      <span class="proj-item-name">📋 全部 Bug</span>
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
      const p = projects.find((x) => x.id === id);
      if (!p) return;
      $('projModalTitle').textContent = `编辑项目 #${id}`;
      $('projId').value = p.id;
      $('projName').value = p.name;
      $('projCode').value = p.code || '';
      $('projDesc').value = p.description || '';
      $('projMask').classList.remove('hidden');
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
  const buckets = new Map();
  for (const p of projects) buckets.set(p.id, { name: p.name, bugs: [] });
  const unassigned = { name: '未关联', bugs: [] };
  for (const bug of bugs) {
    const b = buckets.get(bug.projectId);
    if (b) b.bugs.push(bug);
    else unassigned.bugs.push(bug);
  }
  const rows = [...buckets.values()];
  if (unassigned.bugs.length) rows.push(unassigned);

  if (!rows.length) {
    ['chartProjCount', 'chartProjStatus', 'chartProjSeverity'].forEach((id) => {
      $(id).innerHTML = '<p class="chart-empty">暂无数据</p>';
    });
    return;
  }

  const countMap = {};
  for (const r of rows) countMap[r.name] = r.bugs.length;
  renderBarChart('chartProjCount', countMap, null);
  renderStackChart('chartProjStatus', rows, 'status', STATUS_TEXT, STATUS_COLOR);
  renderStackChart('chartProjSeverity', rows, 'severity', SEVERITY_TEXT, SEVERITY_COLOR);
}

/* 堆叠条形图：条长按项目 Bug 总量，条内按维度占比分段着色 */
function renderStackChart(containerId, rows, field, textMap, colorMap) {
  const keys = Object.keys(textMap);
  const maxTotal = Math.max(...rows.map((r) => r.bugs.length), 1);
  const legend = `<div class="stack-legend">${keys
    .map((k) => `<span><i class="legend-dot" style="background:${colorMap[k]}"></i>${textMap[k]}</span>`)
    .join('')}</div>`;
  const body = rows
    .map((r) => {
      const total = r.bugs.length;
      const fillPct = ((total / maxTotal) * 100).toFixed(1);
      const segs = keys
        .map((k) => {
          const n = r.bugs.filter((b) => b[field] === k).length;
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
