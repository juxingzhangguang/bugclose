/* BugClose 前端逻辑 */
const API = '/api/bugs';

const SEVERITY_TEXT = { CRITICAL: '致命', HIGH: '严重', MEDIUM: '一般', LOW: '轻微' };
const PRIORITY_TEXT = { URGENT: '紧急', HIGH: '高', MEDIUM: '中', LOW: '低' };
const STATUS_TEXT = { NEW: '新建', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭' };
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

/* ===== 列表 ===== */
async function loadBugs() {
  const params = new URLSearchParams();
  if ($('fStatus').value) params.set('status', $('fStatus').value);
  if ($('fSeverity').value) params.set('severity', $('fSeverity').value);
  if ($('fPriority').value) params.set('priority', $('fPriority').value);
  if ($('fAssignee').value.trim()) params.set('assignee', $('fAssignee').value.trim());
  if ($('fKeyword').value.trim()) params.set('keyword', $('fKeyword').value.trim());

  try {
    const bugs = await request(`${API}?${params.toString()}`);
    renderBugs(bugs);
  } catch (e) {
    showToast(e.message, true);
  }
}

function renderBugs(bugs) {
  const tbody = $('bugTbody');
  tbody.innerHTML = '';
  $('emptyTip').classList.toggle('hidden', bugs.length > 0);

  for (const bug of bugs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${bug.id}</td>
      <td class="bug-title-cell" title="${escapeHtml(bug.description || '')}">${escapeHtml(bug.title)}</td>
      <td><span class="tag sev-${bug.severity}">${SEVERITY_TEXT[bug.severity]}</span></td>
      <td><span class="tag pri-${bug.priority}">${PRIORITY_TEXT[bug.priority]}</span></td>
      <td><span class="tag st-${bug.status}">${STATUS_TEXT[bug.status]}</span></td>
      <td>${escapeHtml(bug.assignee || '-')}</td>
      <td>${escapeHtml(bug.reporter || '-')}</td>
      <td>${formatTime(bug.createdAt)}</td>
      <td class="op-cell">
        <button class="btn btn-sm" data-op="trans" data-id="${bug.id}">流转</button>
        <button class="btn btn-sm" data-op="edit" data-id="${bug.id}">编辑</button>
        <button class="btn btn-sm btn-danger" data-op="del" data-id="${bug.id}">删除</button>
      </td>`;
    tbody.appendChild(tr);
  }
}

$('bugTbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-op]');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const op = btn.dataset.op;
  if (op === 'edit') openEditModal(id);
  else if (op === 'trans') openTransModal(id);
  else if (op === 'del') {
    if (!confirm(`确定删除 Bug #${id} 吗？`)) return;
    try {
      await request(`${API}/${id}`, { method: 'DELETE' });
      showToast('删除成功');
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
  $('modalMask').classList.remove('hidden');
});

async function openEditModal(id) {
  try {
    const bug = await request(`${API}/${id}`);
    $('modalTitle').textContent = `编辑 Bug #${id}`;
    $('bugId').value = bug.id;
    $('bugTitle').value = bug.title;
    $('bugDesc').value = bug.description || '';
    $('bugSeverity').value = bug.severity;
    $('bugPriority').value = bug.priority;
    $('bugAssignee').value = bug.assignee || '';
    $('bugReporter').value = bug.reporter || '';
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
    description: $('bugDesc').value.trim(),
    severity: $('bugSeverity').value,
    priority: $('bugPriority').value,
    assignee: $('bugAssignee').value.trim(),
    reporter: $('bugReporter').value.trim(),
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
    loadBugs();
  } catch (err) {
    showToast(err.message, true);
  }
});

/* ===== 状态流转 ===== */
async function openTransModal(id) {
  try {
    const bug = await request(`${API}/${id}`);
    $('transBugId').value = bug.id;
    $('transInfo').textContent =
      `Bug #${bug.id}「${bug.title}」当前状态：${STATUS_TEXT[bug.status]}`;
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
loadBugs();
