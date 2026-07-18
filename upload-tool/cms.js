const MAX_DIMENSION = 2500;
const TARGET_SIZE_KB = 1500;
let S = null;
let currentTab = 'groups';
let currentGroupId = null;
let selectedItems = new Set();
let selectMode = false;
let healthState = null;
let editorState = null;
let saving = false;
let editorSequence = 0;
let saveRequestSequence = 0;
let activeSaveRequest = null;

async function api(url, opts) {
  opts = opts || {};
  var method = opts.method || 'GET';
  var init = { method: method, headers: {} };
  Object.keys(opts.headers || {}).forEach(function(name) {
    init.headers[name] = opts.headers[name];
  });
  if (opts.body) {
    if (!(opts.body instanceof FormData)) {
      init.headers['Content-Type'] = 'application/json; charset=utf-8';
    }
    init.body = opts.body;
  }
  var res = await fetch(url, init);
  var payload = null;
  try { payload = await res.json(); } catch (error) { payload = null; }
  if (!res.ok) {
    throw new Error(payload && payload.message ? payload.message : 'HTTP ' + res.status);
  }
  return payload;
}

function $(id) { return document.getElementById(id); }
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function toast(msg, isError) {
  var el = $('toast');
  el.textContent = msg;
  el.className = 'show' + (isError ? ' error' : '');
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.className = ''; }, 2000);
}

async function loadData() {
  $('stats').textContent = '加载中...';
  try {
    var results = await Promise.all([api('/api/state'), api('/api/health')]);
    S = results[0];
    healthState = results[1];
    updateStats();
    updateHealthStatus();
    render();
  } catch(e) {
    $('stats').textContent = '连接失败';
    healthState = null;
    updateHealthStatus();
    toast('无法连接服务器', true);
  }
}

function updateStats() {
  if (!S) return;
  $('stats').textContent = S.photoGroups.length + ' 组 | ' + S.videos.length + ' 视频 | ' + S.commercialProjects.length + ' 项目';
}

function updateHealthStatus() {
  var el = $('health-status');
  if (!el) return;
  if (!healthState) {
    el.textContent = '数据库：未知 · R2：未知 · 孤儿：未知';
    el.className = 'health-status error';
    return;
  }
  var database = healthState.database ? '正常' : '异常';
  var r2 = !healthState.r2.configured ? '未配置' : (healthState.r2.reachable ? '可访问' : '不可访问');
  var orphans = Number(healthState.orphan_photo_items || 0) + Number(healthState.orphan_commercial_items || 0);
  el.textContent = '数据库：' + database + ' · R2：' + r2 + ' · 孤儿：' + orphans;
  el.className = 'health-status' + (healthState.database && (!healthState.r2.configured || healthState.r2.reachable) ? '' : ' error');
}

async function exportData() {
  try {
    await api('/api/export', { method: 'POST' });
    toast('已导出到 data.js / commercial.js');
    loadData();
  } catch(e) { toast('导出失败', true); }
}

document.querySelectorAll('#sidebar nav button').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#sidebar nav button').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentTab = btn.dataset.tab;
    currentGroupId = null;
    closePanel();
    render();
  });
});

function render() {
  var container = $('content-inner');
  if (!S) { container.innerHTML = '<div class="empty-state"><div class="empty-icon">⟳</div><p>加载中...</p></div>'; return; }
  if (currentTab === 'groups') renderGroups(container);
  else if (currentTab === 'videos') renderVideosTab(container);
  else if (currentTab === 'commercial') renderCommercialTab(container);
}

function renderGroups(container) {
  if (currentGroupId !== null) { renderGroupDetail(container); return; }
  var search = ($('search').value || '').toLowerCase();
  var groups = S.photoGroups || [];
  if (search) groups = groups.filter(function(g) { return (g.title||'').toLowerCase().indexOf(search)>=0 || (g.category||'').toLowerCase().indexOf(search)>=0 || (g.date||'').indexOf(search)>=0; });
  if (!groups.length) { container.innerHTML = '<div class="empty-state"><div class="empty-icon">▦</div><p>暂无图片组</p></div>'; return; }
  var html = '<div class="groups-grid">';
  groups.forEach(function(g) {
    var imgs = g.images || [];
    var count = imgs.length;
    var previewClass = count <= 1 ? 'single' : count === 2 ? 'double' : '';
    var previews = imgs.slice(0, 3).map(function(i) {
      var src = (i.src||'').startsWith('http') ? i.src : '/' + (i.src||'');
      return '<img src="' + esc(src) + '" loading="lazy" onerror="this.style.display=\'none\'">';
    }).join('');
    html += '<div class="group-card" onclick="openGroup(' + g.id + ')">';
    if (previews) html += '<div class="preview-strip ' + previewClass + '">' + previews + '</div>';
    else html += '<div class="preview-strip" style="background:var(--bg)"></div>';
    html += '<div class="card-info">';
    if (g.date) html += '<span class="date">' + esc(g.date) + '</span>';
    html += '<span class="cat">' + esc(g.category) + (g.title ? ' · ' + esc(g.title) : '') + '</span>';
    html += '<span class="count">' + count + ' 张图片</span>';
    html += '</div><div class="card-actions" onclick="event.stopPropagation()">';
    html += '<button class="btn-ghost" onclick="editGroup(' + g.id + ')">✎ 编辑</button>';
    html += '<button class="btn-ghost" style="color:var(--danger)" onclick="deleteGroup(' + g.id + ')">删除</button>';
    html += '</div></div>';
  });
  html += '</div>';
  container.innerHTML = html;
}

function openGroup(id) { currentGroupId = id; closePanel(); render(); }

function renderGroupDetail(container) {
  var group = S.photoGroups.find(function(g) { return g.id === currentGroupId; });
  if (!group) { currentGroupId = null; render(); return; }
  var imgs = group.images || [];
  var search = ($('search').value || '').toLowerCase();
  var filtered = imgs;
  if (search) filtered = imgs.filter(function(i) { return (i.title||'').toLowerCase().indexOf(search)>=0 || (i.src||'').toLowerCase().indexOf(search)>=0; });
  var html = '<div class="group-detail"><div class="back-row">';
  html += '<button class="btn-ghost" onclick="currentGroupId=null;closePanel();render()">← 返回</button>';
  html += '<h2>' + esc(group.date||'') + ' ' + esc(group.title||'') + '</h2>';
  html += '<span style="font-size:11px;color:var(--text-dim)">' + esc(group.category) + ' · ' + imgs.length + ' 张</span>';
  html += '<button class="btn btn-secondary btn-sm" onclick="editGroup(' + group.id + ')">✎ 编辑组信息</button></div>';
  if (selectMode && selectedItems.size > 0) {
    html += '<div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">';
    html += '<span style="font-size:12px;color:var(--text-muted)">已选 ' + selectedItems.size + ' 项</span>';
    html += '<button class="btn btn-danger btn-sm" onclick="deleteSelected()">删除选中</button>';
    html += '<button class="btn btn-secondary btn-sm" onclick="toggleSelectMode()">取消</button></div>';
  }
  html += '<div class="upload-zone" id="upload-zone" onclick="this.querySelector(\'input\').click()">';
  html += '<input type="file" accept="image/*" multiple onchange="handleFileUpload(event)">';
  html += '<div class="uz-icon">+</div><div class="uz-text">点击或拖拽上传图片</div>';
  html += '<div class="uz-hint">支持 JPG / PNG / WebP，自动压缩</div></div>';
  html += '<div class="image-grid' + (selectMode?' select-mode':'') + '" id="image-grid">';
  if (!filtered.length) {
    html += '<div class="empty-state" style="grid-column:1/-1"><p>暂无图片</p></div>';
  } else {
    filtered.forEach(function(img) {
      var src = (img.src||'').startsWith('http') ? img.src : '/' + (img.src||'');
      var sel = selectedItems.has(img.id) ? ' selected' : '';
      html += '<div class="image-card' + sel + '" data-id="' + img.id + '" draggable="true" onclick="handleImageClick(event, ' + img.id + ')">';
      html += '<div class="sel-check">✓</div>';
      html += '<img src="' + esc(src) + '" loading="lazy" onerror="this.style.display=\'none\'">';
      html += '<div class="img-title">' + esc(img.title||img.src||'未命名') + '</div></div>';
    });
  }
  html += '</div></div>';
  container.innerHTML = html;
  var uz = $('upload-zone');
  if (uz) {
    uz.addEventListener('dragover', function(e) { e.preventDefault(); uz.classList.add('drag'); });
    uz.addEventListener('dragleave', function() { uz.classList.remove('drag'); });
    uz.addEventListener('drop', function(e) { e.preventDefault(); uz.classList.remove('drag'); handleFileUpload({target:{files:e.dataTransfer.files}}); });
  }
  setupDragSort();
}
function renderVideosTab(container) {
  var videos = S.videos || [];
  var search = ($('search').value || '').toLowerCase();
  var filtered = videos;
  if (search) filtered = videos.filter(function(v) { return (v.title||'').toLowerCase().indexOf(search)>=0 || (v.url||'').toLowerCase().indexOf(search)>=0 || (v.platform||'').toLowerCase().indexOf(search)>=0 || (v.source||'').toLowerCase().indexOf(search)>=0; });
  var html = '<div style="margin-bottom:16px;display:flex;gap:8px"><button class="btn btn-primary btn-sm" onclick="addVideo()">+ 添加视频</button></div>';
  if (!filtered.length) { html += '<div class="empty-state"><div class="empty-icon">▶</div><p>暂无视频</p></div>'; }
  else {
    filtered.forEach(function(v) {
      html += '<div class="group-card" style="display:flex;gap:14px;padding:14px;cursor:default;border-radius:var(--radius);margin-bottom:8px;max-width:600px">';
      html += '<div style="flex:1;min-width:0"><div style="font-weight:600;font-size:13px;margin-bottom:4px">' + esc(v.title||'未命名') + '</div>';
      html += '<div style="font-size:11px;color:var(--text-dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(v.url) + '</div>';
      if (v.description) html += '<div style="font-size:11px;color:var(--text-muted);margin-top:4px">' + esc(v.description) + '</div>';
      html += '</div><div style="display:flex;gap:4px;align-items:flex-start;flex-shrink:0">';
      html += '<button class="btn-ghost" onclick="editVideo(' + v.id + ')">✎</button>';
      html += '<button class="btn-ghost" style="color:var(--danger)" onclick="deleteVideo(' + v.id + ')">🗑</button></div></div>';
    });
  }
  container.innerHTML = html;
}

function renderCommercialTab(container) {
  var projects = S.commercialProjects || [];
  var search = ($('search').value || '').toLowerCase();
  var filtered = projects;
  if (search) filtered = projects.filter(function(p) { return (p.client||'').toLowerCase().indexOf(search)>=0 || (p.title||'').toLowerCase().indexOf(search)>=0 || (p.category||'').toLowerCase().indexOf(search)>=0; });
  var html = '<div style="margin-bottom:16px;display:flex;gap:8px"><button class="btn btn-primary btn-sm" onclick="addProject()">+ 新建项目</button></div>';
  if (!filtered.length) { html += '<div class="empty-state"><div class="empty-icon">◆</div><p>暂无商业项目</p></div>'; }
  else {
    html += '<div class="groups-grid">';
    filtered.forEach(function(p) {
      var cover = (p.cover||'').startsWith('http') ? p.cover : '/' + (p.cover||'');
      var items = p.items || [];
      html += '<div class="group-card" onclick="editProject(\'' + esc(p.id) + '\')">';
      html += '<div class="preview-strip single">';
      if (p.cover) html += '<img src="' + esc(cover) + '" onerror="this.style.display=\'none\'">';
      else html += '<div style="background:var(--bg);height:100px"></div>';
      html += '</div><div class="card-info"><span class="date">' + esc(p.client) + ' · ' + p.year + '</span>';
      html += '<span class="cat">' + esc(p.category) + (p.title ? ' · ' + esc(p.title) : '') + '</span>';
      html += '<span class="count">' + items.length + ' 项内容</span></div>';
      html += '<div class="card-actions" onclick="event.stopPropagation()">';
      html += '<button class="btn-ghost" onclick="editProject(\'' + esc(p.id) + '\')">✎ 编辑</button>';
      html += '<button class="btn-ghost" style="color:var(--danger)" onclick="deleteProject(\'' + esc(p.id) + '\')">删除</button></div></div>';
    });
    html += '</div>';
  }
  container.innerHTML = html;
}

function createEditorState(type, data) {
  return { mode: 'create', type: type, data: data };
}

function editEditorState(type, data) {
  return { mode: 'edit', type: type, data: data };
}

function openPanel(state) {
  state.editorToken = ++editorSequence;
  editorState = state;
  var type = state.type;
  var data = state.data;
  var panel = $('edit-panel');
  var inner = panel.querySelector('.panel-inner');
  var html = '';
  if (type === 'group') {
    html = '<h3 style="font-size:14px;font-weight:600;margin-bottom:4px">编辑图片组</h3>';
    html += '<div class="panel-field"><label>日期</label><input id="ef-date" value="' + esc(data.date||'') + '" placeholder="YYYY-MM-DD"></div>';
    html += '<div class="panel-field"><label>分类</label><select id="ef-category">';
    ['portrait','landscape','street','performance','official'].forEach(function(c) { html += '<option value="' + c + '"' + (data.category===c?' selected':'') + '>' + c + '</option>'; });
    html += '</select></div>';
    html += '<div class="panel-field"><label>标题</label><input id="ef-title" value="' + esc(data.title||'') + '"></div>';
    html += '<div class="panel-field"><label>描述</label><textarea id="ef-desc">' + esc(data.description||'') + '</textarea></div>';
    html += '<div class="panel-field"><label>列数</label><select id="ef-cols">';
    [1,2,3,4].forEach(function(n) { html += '<option value="' + n + '"' + ((data.cols||3)===n?' selected':'') + '>' + n + ' 列</option>'; });
    html += '</select></div>';
    html += '<div class="panel-actions"><button class="btn btn-primary btn-sm" id="panel-save-btn" onclick="savePanel()">保存</button><button class="btn btn-secondary btn-sm" onclick="closePanel()">取消</button></div>';
  } else if (type === 'photo') {
    var src = (data.src||'').startsWith('http') ? data.src : '/' + (data.src||'');
    html = '<div class="panel-preview"><img src="' + esc(src) + '" onerror="this.style.display=\'none\'"></div>';
    html += '<h3 style="font-size:14px;font-weight:600">编辑图片</h3>';
    html += '<div class="panel-field"><label>标题</label><input id="ef-title" value="' + esc(data.title||'') + '"></div>';
    html += '<div class="panel-field"><label>描述</label><textarea id="ef-desc">' + esc(data.description||'') + '</textarea></div>';
    html += '<div class="panel-field"><label>路径</label><input id="ef-src" value="' + esc(data.src||'') + '" style="font-size:11px;color:var(--text-dim)"></div>';
    html += '<div class="panel-actions"><button class="btn btn-primary btn-sm" id="panel-save-btn" onclick="savePanel()">保存</button><button class="btn btn-danger btn-sm" onclick="deletePhotoItem(' + data.id + ')">删除</button><button class="btn btn-secondary btn-sm" onclick="closePanel()">取消</button></div>';
  } else if (type === 'video') {
    html = '<h3 style="font-size:14px;font-weight:600;margin-bottom:4px">编辑视频</h3>';
    html += '<div class="panel-field"><label>标题</label><input id="ef-title" value="' + esc(data.title||'') + '"></div>';
    html += '<div class="panel-field"><label>描述</label><textarea id="ef-desc">' + esc(data.description||'') + '</textarea></div>';
    html += '<div class="panel-field"><label>URL</label><input id="ef-url" value="' + esc(data.url||'') + '"></div>';
    html += '<div class="panel-field"><label>平台</label><select id="ef-platform"><option value="">-- 选择平台 --</option><option value="bilibili"' + (data.platform=='bilibili'?' selected':'') + '>Bilibili</option><option value="xiaohongshu"' + (data.platform=='xiaohongshu'?' selected':'') + '>小红书</option><option value="douyin"' + (data.platform=='douyin'?' selected':'') + '>抖音</option></select></div>';
    html += '<div class="panel-field"><label>来源账号</label><input id="ef-source" value="' + esc(data.source||'') + '" placeholder="如: 沉礁Sleepylagoon个人账号"></div>';
    html += '<div class="panel-actions"><button class="btn btn-primary btn-sm" id="panel-save-btn" onclick="savePanel()">保存</button><button class="btn btn-danger btn-sm" onclick="deleteVideo(' + data.id + ')">删除</button><button class="btn btn-secondary btn-sm" onclick="closePanel()">取消</button></div>';
  } else if (type === 'project') {
    html = '<h3 style="font-size:14px;font-weight:600;margin-bottom:4px">编辑项目</h3>';
    html += '<div class="panel-field"><label>客户/事件</label><input id="ef-client" value="' + esc(data.client||'') + '"></div>';
    html += '<div class="panel-field"><label>标题</label><input id="ef-title" value="' + esc(data.title||'') + '"></div>';
    html += '<div class="panel-field"><label>描述</label><textarea id="ef-desc">' + esc(data.description||'') + '</textarea></div>';
    html += '<div class="panel-field"><label>年份</label><input id="ef-year" type="number" value="' + (data.year||2026) + '"></div>';
    html += '<div class="panel-field"><label>分类</label><select id="ef-category">';
    ['公务摄影','演出摄影','体育摄影','空间摄影','广告','视频','电商'].forEach(function(c) { html += '<option value="' + c + '"' + (data.category===c?' selected':'') + '>' + c + '</option>'; });
    html += '</select></div>';
    html += '<div class="panel-field"><label>封面图 URL</label><input id="ef-cover" value="' + esc(data.cover||'') + '"></div>';
    html += '<div class="panel-actions"><button class="btn btn-primary btn-sm" id="panel-save-btn" onclick="savePanel()">保存</button><button class="btn btn-danger btn-sm" onclick="deleteProject(\'' + esc(data.id) + '\')">删除项目</button><button class="btn btn-secondary btn-sm" onclick="closePanel()">取消</button></div>';
  }
  inner.innerHTML = html;
  panel.classList.remove('hidden');
}

function closePanel(requestToken) {
  if (saving && requestToken === undefined) {
    toast('保存进行中，请稍候', true);
    return false;
  }
  if (requestToken !== undefined) {
    if (!activeSaveRequest || activeSaveRequest.requestToken !== requestToken) return false;
    if (!editorState || editorState.editorToken !== activeSaveRequest.editorToken) return false;
  }
  editorState = null;
  $('edit-panel').classList.add('hidden');
  return true;
}

async function savePanel() {
  if (!editorState || saving) return;
  var state = editorState;
  var type = state.type;
  var data = state.data;
  var body = {};
  var url = '';
  var method = state.mode === 'create' ? 'POST' : 'PUT';
  var saveButton = $('panel-save-btn');
  var request = {
    requestToken: ++saveRequestSequence,
    editorToken: state.editorToken
  };
  activeSaveRequest = request;
  saving = true;
  if (saveButton) saveButton.disabled = true;
  try {
    if (type === 'group') {
      body = { date: $('ef-date').value, category: $('ef-category').value, title: $('ef-title').value, description: $('ef-desc').value, cols: parseInt($('ef-cols').value) };
      url = '/api/photo-groups' + (state.mode === 'edit' ? '/' + data.id : '');
    } else if (type === 'photo') {
      body = { src: $('ef-src').value, title: $('ef-title').value, description: $('ef-desc').value };
      url = '/api/photo-items/' + data.id;
    } else if (type === 'video') {
      body = { title: $('ef-title').value, description: $('ef-desc').value, url: $('ef-url').value, platform: $('ef-platform').value, source: $('ef-source').value };
      url = '/api/videos' + (state.mode === 'edit' ? '/' + data.id : '');
    } else if (type === 'project') {
      body = { id: data.id, client: $('ef-client').value, title: $('ef-title').value, description: $('ef-desc').value, year: parseInt($('ef-year').value), category: $('ef-category').value, cover: $('ef-cover').value };
      url = '/api/commercial-projects' + (state.mode === 'edit' ? '/' + data.id : '');
    }
    await api(url, { method: method, body: JSON.stringify(body) });
    if (editorState && editorState.editorToken === request.editorToken) {
      toast(state.mode === 'create' ? '已添加' : '已保存');
      closePanel(request.requestToken);
    }
    await loadData();
  } catch(e) {
    if (editorState && editorState.editorToken === request.editorToken) {
      toast((state.mode === 'create' ? '添加' : '保存') + '失败: ' + e.message, true);
    }
  } finally {
    if (activeSaveRequest === request) {
      saving = false;
      activeSaveRequest = null;
      if (editorState && editorState.editorToken === request.editorToken) {
        var currentSaveButton = $('panel-save-btn');
        if (currentSaveButton) currentSaveButton.disabled = false;
      }
    }
  }
}
function editGroup(id) { var g = S.photoGroups.find(function(x) { return x.id === id; }); if (g) openPanel(editEditorState('group', g)); }

async function deleteGroup(id) {
  if (!confirm('确定删除此组及其所有图片？包括 R2 上的文件？')) return;
  try {
    await api('/api/photo-groups/' + id, { method: 'DELETE' });
    toast('已删除');
    if (currentGroupId === id) currentGroupId = null;
    closePanel();
    await loadData();
  } catch(e) { toast('删除失败: ' + e.message, true); }
}

function handleImageClick(e, imgId) {
  if (selectMode) {
    e.stopPropagation();
    if (selectedItems.has(imgId)) selectedItems.delete(imgId); else selectedItems.add(imgId);
    updateSelectUI();
    return;
  }
  var img = findImageById(imgId);
  if (img) openPanel(editEditorState('photo', img));
}

function findImageById(id) {
  for (var i = 0; i < S.photoGroups.length; i++) {
    var g = S.photoGroups[i];
    if (g.images) {
      var found = g.images.find(function(im) { return im.id === id; });
      if (found) return found;
    }
  }
  return null;
}

async function deletePhotoItem(id) {
  try {
    await api('/api/photo-items/' + id, { method: 'DELETE' });
    toast('已删除');
    selectedItems.delete(id);
    closePanel();
    await loadData();
  } catch(e) { toast('删除失败: ' + e.message, true); }
}

function addVideo() {
  openPanel(createEditorState('video', { id: 0, title: '', description: '', url: '', platform: '', source: '' }));
}

function editVideo(id) { var v = S.videos.find(function(x) { return x.id === id; }); if (v) openPanel(editEditorState('video', v)); }

async function deleteVideo(id) {
  if (!confirm('确定删除此视频？')) return;
  try { await api('/api/videos/' + id, { method: 'DELETE' }); toast('已删除'); closePanel(); await loadData(); }
  catch(e) { toast('删除失败: ' + e.message, true); }
}

function addProject() {
  openPanel(createEditorState('project', { id: 'commercial-' + Date.now(), client: '', title: '', description: '', year: 2026, category: '', cover: '' }));
}

function editProject(id) { var p = S.commercialProjects.find(function(x) { return x.id === id; }); if (p) openPanel(editEditorState('project', p)); }

async function deleteProject(id) {
  if (!confirm('确定删除此项目及其所有内容？')) return;
  try { await api('/api/commercial-projects/' + id, { method: 'DELETE' }); toast('已删除'); closePanel(); await loadData(); }
  catch(e) { toast('删除失败: ' + e.message, true); }
}

function handleAdd() {
  if (currentTab === 'groups') {
    openPanel(createEditorState('group', { id: 0, date: '', category: 'portrait', title: '', description: '', cols: 3 }));
  } else if (currentTab === 'videos') { addVideo(); }
  else if (currentTab === 'commercial') { addProject(); }
}

function toggleSelectMode() { selectMode = !selectMode; if (!selectMode) selectedItems.clear(); updateSelectUI(); render(); }

function updateSelectUI() {
  $('btn-delete-selected').style.display = (selectMode && selectedItems.size > 0) ? '' : 'none';
  $('btn-select').textContent = selectMode ? '✕' : '☐';
}

async function deleteSelected() {
  if (!selectedItems.size) return;
  if (!confirm('确定删除选中的 ' + selectedItems.size + ' 张图片？包括 R2 上的文件？')) return;
  try {
    var count = selectedItems.size;
    await api('/api/batch-delete', { method: 'POST', body: JSON.stringify({ table: 'photo_items', ids: Array.from(selectedItems) }) });
    toast('已删除 ' + count + ' 项');
    selectedItems.clear(); selectMode = false; updateSelectUI(); await loadData();
  } catch(e) { toast('批量删除失败: ' + e.message, true); }
}

function applyFilter() { render(); }

function compressImage(file) {
  return new Promise(function(resolve, reject) {
    var img = new Image();
    var objectUrl;
    var cleaned = false;
    function cleanup() {
      if (!cleaned && objectUrl) {
        cleaned = true;
        URL.revokeObjectURL(objectUrl);
      }
    }
    function fail(error) {
      cleanup();
      reject(error instanceof Error ? error : new Error('image compression failed'));
    }
    img.onload = function() {
      cleanup();
      try {
        var canvas = document.createElement('canvas');
        var width = img.width, height = img.height;
        if (!width || !height) throw new Error('image has invalid dimensions');
        if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
          var ratio = Math.min(MAX_DIMENSION / width, MAX_DIMENSION / height);
          width = Math.floor(width * ratio);
          height = Math.floor(height * ratio);
        }
        canvas.width = width; canvas.height = height;
        var ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('image canvas is unavailable');
        ctx.drawImage(img, 0, 0, width, height);
        var quality = 0.9;
        (function tryCompress() {
          try {
            canvas.toBlob(function(blob) {
              if (blob && blob.size <= TARGET_SIZE_KB * 1024) { resolve(blob); }
              else if (quality > 0.3) { quality -= 0.1; tryCompress(); }
              else if (blob) { resolve(blob); }
              else { reject(new Error('image compression produced no data')); }
            }, 'image/jpeg', quality);
          } catch (error) { fail(error); }
        })();
      } catch (error) { fail(error); }
    };
    img.onerror = function() { fail(new Error('image decode failed')); };
    try {
      objectUrl = URL.createObjectURL(file);
      img.src = objectUrl;
    } catch (error) { fail(error); }
  });
}

function normalizeUploadDate(value) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return value;
  if (/^\d{4}-\d{2}$/.test(value || '')) return value + '-01';
  return new Date().toISOString().slice(0, 10);
}

function newOperationKey() {
  return crypto.randomUUID();
}

async function uploadPhotoBlob(blob, filename, group, uploadDate, operationKey) {
  var form = new FormData();
  var jpgName = String(filename || 'image').replace(/\.[^.]*$/, '') + '.jpg';
  form.append('image', blob, jpgName);
  form.append('group_id', String(group.id));
  form.append('category', group.category);
  form.append('date', normalizeUploadDate(uploadDate));
  var options = { method: 'POST', body: form };
  if (operationKey) options.headers = { 'Idempotency-Key': operationKey };
  return api('/api/photo-items/upload', options);
}

async function handleFileUpload(event) {
  var files = event.target.files;
  if (!files || !files.length) return;
  if (!currentGroupId) { toast('请先选择一个图片组', true); return; }
  var group = S.photoGroups.find(function(g) { return g.id === currentGroupId; });
  if (!group) return;
  var succeeded = 0;
  var failed = 0;
  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    if (!file.type.startsWith('image/')) continue;
    try {
      var st = document.getElementById('stats');
      if (st) st.textContent = '上传中 ' + (i+1) + '/' + files.length + '...';
      var compressed = await compressImage(file);
      await uploadPhotoBlob(compressed, Date.now() + '-' + i + '.jpg', group, group.date, newOperationKey());
      succeeded++;
    } catch(e) {
      failed++;
      toast('上传 ' + file.name + ' 失败: ' + e.message, true);
    }
  }
  toast('上传完成：成功 ' + succeeded + '，失败 ' + failed, failed > 0);
  if (succeeded > 0) await loadData();
  else updateStats();
}

// ==================== Bulk Upload ====================
let bulkFiles = [];
let bulkSelectedCat = 'portrait';
let bulkGroups = {};
let bulkGroupOperationKeys = {};
let bulkUploading = false;
let bulkQueueLocked = false;

function setBulkInputEnabled(enabled) {
  var input = $('bulk-file-input');
  var drop = $('bulk-drop');
  if (input) input.disabled = !enabled;
  if (drop) {
    if (enabled) drop.classList.remove('disabled');
    else drop.classList.add('disabled');
  }
}

function openBulkUpload() {
  $('bulk-modal').classList.add('active');
  bulkFiles = [];
  bulkGroups = {};
  bulkGroupOperationKeys = {};
  bulkUploading = false;
  bulkQueueLocked = false;
  setBulkInputEnabled(true);
  renderBulkPreviews();
  $('bulk-upload-btn').disabled = true;
  $('bulk-retry-btn').style.display = 'none';
  $('bulk-progress').style.display = 'none';
  $('bulk-stats').textContent = '';
  // Setup tag clicks
  document.querySelectorAll('#bulk-tags .modal-tag').forEach(function(t) {
    t.onclick = function() {
      if (bulkQueueLocked) { toast('重试完成前不能更改分类', true); return; }
      document.querySelectorAll('#bulk-tags .modal-tag').forEach(function(tt) { tt.classList.remove('selected'); });
      t.classList.add('selected');
      bulkSelectedCat = t.dataset.val;
    };
  });
  // Setup drop zone
  var dz = $('bulk-drop');
  dz.onclick = function() { if (!bulkUploading) $('bulk-file-input').click(); };
  dz.ondragover = function(e) { e.preventDefault(); dz.classList.add('drag'); };
  dz.ondragleave = function() { dz.classList.remove('drag'); };
  dz.ondrop = function(e) { e.preventDefault(); dz.classList.remove('drag'); if (!bulkUploading) handleBulkFiles(e.dataTransfer.files); };
  $('bulk-file-input').onchange = function() { if (!bulkUploading) handleBulkFiles($('bulk-file-input').files); };
}

function closeBulkUpload() {
  if (bulkUploading) { toast('上传进行中，请稍候', true); return; }
  $('bulk-modal').classList.remove('active');
  bulkFiles.forEach(revokeBulkPreview);
  bulkFiles = [];
  bulkGroups = {};
  bulkGroupOperationKeys = {};
  bulkQueueLocked = false;
}

function getExifDate(file) {
  return new Promise(function(resolve) {
    var reader = new FileReader();
    var settled = false;
    function finish(value) {
      if (!settled) {
        settled = true;
        resolve(value);
      }
    }
    reader.onload = function(e) {
      try {
        var buffer = e && e.target && e.target.result;
        var view = new DataView(buffer);
        if (view.byteLength < 4 || view.getUint16(0, false) !== 0xFFD8) { finish(null); return; }
        var length = view.byteLength, offset = 2;
        while (offset + 4 <= length) {
          var marker = view.getUint16(offset, false);
          var segmentLength = view.getUint16(offset + 2, false);
          if (segmentLength < 2 || offset + 2 + segmentLength > length) break;
          if (marker === 0xFFE1 && offset + 10 <= length) {
            var exd = '';
            for (var k = offset + 4; k < offset + 10; k++) exd += String.fromCharCode(view.getUint8(k));
            if (exd === 'Exif\u0000\u0000') {
              finish(findExifDateInner(buffer, offset + 10));
              return;
            }
          }
          offset += 2 + segmentLength;
        }
        finish(null);
      } catch (error) { finish(null); }
    };
    reader.onerror = function() { finish(null); };
    reader.onabort = function() { finish(null); };
    try { reader.readAsArrayBuffer(file.slice(0, 65536)); }
    catch (error) { finish(null); }
  });
}

function findExifDateInner(buffer, tiffOffset) {
  try {
    var view = new DataView(buffer);
    if (tiffOffset < 0 || tiffOffset + 8 > view.byteLength) return null;
    var byteOrder = view.getUint16(tiffOffset, false);
    if (byteOrder !== 0x4949 && byteOrder !== 0x4D4D) return null;
    var le = byteOrder === 0x4949;
    var ifdOff = view.getUint32(tiffOffset + 4, le);
    var ifdStart = tiffOffset + ifdOff;
    if (ifdStart < tiffOffset || ifdStart + 2 > view.byteLength) return null;
    var entries = view.getUint16(ifdStart, le);
    for (var i = 0; i < entries; i++) {
      var eo = ifdStart + 2 + i * 12;
      if (eo + 12 > view.byteLength) return null;
      if (view.getUint16(eo, le) === 0x9003) {
        var vo = view.getUint32(eo + 8, le);
        var dof = tiffOffset + vo;
        if (dof < tiffOffset || dof + 10 > view.byteLength) return null;
        var y = (view.getUint8(dof)-48)*1000+(view.getUint8(dof+1)-48)*100+(view.getUint8(dof+2)-48)*10+(view.getUint8(dof+3)-48);
        var m = (view.getUint8(dof+5)-48)*10+(view.getUint8(dof+6)-48);
        var d = (view.getUint8(dof+8)-48)*10+(view.getUint8(dof+9)-48);
        if (y>2000 && y<2100 && m>=1 && m<=12 && d>=1 && d<=31) return y+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0');
      }
    }
    return null;
  } catch (error) { return null; }
}

function extractDateFromFilename(name) {
  var m = name.match(/(\d{4})[-_]?(\d{2})[-_]?(\d{2})/);
  return m ? m[1]+'-'+m[2]+'-'+m[3] : null;
}

async function handleBulkFiles(files) {
  if (bulkUploading) { toast('上传进行中，暂时不能添加图片', true); return; }
  if (!files || !files.length) return;
  $('bulk-stats').textContent = '读取中...';
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    if (!f.type.startsWith('image/')) continue;
    var exif = await getExifDate(f);
    var fnDate = extractDateFromFilename(f.name);
    var date = fnDate || exif || new Date(f.lastModified).toISOString().slice(0, 10);
    bulkFiles.push({ file: f, name: f.name, date: date, status: 'pending', error: '', operationKey: newOperationKey(), previewUrl: URL.createObjectURL(f) });
  }
  renderBulkPreviews();
}

function renderBulkPreviews() {
  var grid = $('bulk-previews');
  var groups = $('bulk-groups');
  if (!bulkFiles.length) { grid.innerHTML = ''; groups.innerHTML = ''; $('bulk-upload-btn').disabled = true; $('bulk-stats').textContent = ''; return; }
  var pendingCount = bulkFiles.filter(function(item) { return item.status === 'pending'; }).length;
  var uploadingCount = bulkFiles.filter(function(item) { return item.status === 'uploading'; }).length;
  var failedCount = bulkFiles.filter(function(item) { return item.status === 'failed'; }).length;
  $('bulk-upload-btn').disabled = bulkUploading || pendingCount === 0;
  $('bulk-retry-btn').style.display = failedCount > 0 && !bulkUploading ? '' : 'none';
  $('bulk-stats').textContent = '待上传 ' + pendingCount + ' · 上传中 ' + uploadingCount + ' · 失败 ' + failedCount;
  grid.innerHTML = '';
  var gb = {};
  bulkFiles.forEach(function(item) {
    var div = document.createElement('div');
    div.className = 'modal-preview status-' + item.status;
    div.innerHTML = '<img src="'+esc(item.previewUrl)+'"><div class="fn">'+esc(item.name)+'</div><div class="db">'+item.date.slice(0,7)+' · '+item.status+'</div>' + (item.error ? '<div class="upload-error">'+esc(item.error)+'</div>' : '');
    grid.appendChild(div);
    var dk = item.date.slice(0, 7);
    if (!gb[dk]) gb[dk] = 0;
    gb[dk]++;
  });
  groups.innerHTML = Object.keys(gb).sort().reverse().map(function(d) { return '<span class="modal-grp">'+d+' ('+gb[d]+'张)</span>'; }).join('');
}

function revokeBulkPreview(item) {
  if (item.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
    item.previewUrl = '';
  }
}

async function doBulkUpload() {
  if (bulkUploading) return;
  var queue = bulkFiles.filter(function(item) { return item.status === 'pending'; });
  if (!queue.length) return;
  bulkUploading = true;
  bulkQueueLocked = true;
  setBulkInputEnabled(false);
  $('bulk-progress').style.display = 'block';
  $('bulk-fill').style.width = '0%';
  $('bulk-label').style.color = '';
  renderBulkPreviews();

  queue.forEach(function(item) {
    if (!item.operationKey) item.operationKey = newOperationKey();
  });

  var succeeded = 0;
  var failed = 0;
  var dateKeys = [];
  queue.forEach(function(item) {
    var dateKey = item.date.slice(0, 7);
    if (dateKeys.indexOf(dateKey) < 0) dateKeys.push(dateKey);
  });
  dateKeys.sort();

  for (var groupIndex = 0; groupIndex < dateKeys.length; groupIndex++) {
    var groupDate = dateKeys[groupIndex];
    if (bulkGroups[groupDate]) continue;
    if (!bulkGroupOperationKeys[groupDate]) bulkGroupOperationKeys[groupDate] = newOperationKey();
    $('bulk-label').textContent = '创建图片组 ' + groupDate + '...';
    try {
      var created = await api('/api/photo-groups', {
        method: 'POST',
        headers: { 'Idempotency-Key': bulkGroupOperationKeys[groupDate] },
        body: JSON.stringify({ date: groupDate, category: bulkSelectedCat, title: '', description: '', cols: 3 })
      });
      bulkGroups[groupDate] = { id: created.id, category: bulkSelectedCat, date: groupDate };
    } catch (error) {
      queue.filter(function(item) { return item.date.slice(0, 7) === groupDate; }).forEach(function(item) {
        item.status = 'failed';
        item.error = error.message;
        failed++;
      });
      renderBulkPreviews();
    }
  }

  for (var i = 0; i < queue.length; i++) {
    var item = queue[i];
    if (item.status === 'failed') continue;
    var dateKey = item.date.slice(0, 7);
    var group = bulkGroups[dateKey];
    if (!group) continue;
    item.status = 'uploading';
    item.error = '';
    $('bulk-label').textContent = '压缩并上传 ' + (i + 1) + '/' + queue.length + ': ' + item.name;
    $('bulk-fill').style.width = Math.round((i / queue.length) * 100) + '%';
    renderBulkPreviews();
    try {
      if (!item.compressedBlob) item.compressedBlob = await compressImage(item.file);
      var compressed = item.compressedBlob;
      await uploadPhotoBlob(compressed, Date.now() + '-' + String(i).padStart(3, '0') + '.jpg', group, item.date, item.operationKey);
      item.status = 'succeeded';
      succeeded++;
    } catch (error) {
      item.status = 'failed';
      item.error = error.message;
      failed++;
    }
    renderBulkPreviews();
  }

  bulkFiles = bulkFiles.filter(function(item) {
    if (item.status === 'succeeded') revokeBulkPreview(item);
    return item.status !== 'succeeded';
  });
  bulkUploading = false;
  setBulkInputEnabled(true);
  $('bulk-fill').style.width = '100%';
  var completion = '上传完成：成功 ' + succeeded + '，失败 ' + failed;
  $('bulk-label').textContent = completion;
  $('bulk-label').style.color = failed > 0 ? '#f87171' : '';
  toast(completion, failed > 0);
  renderBulkPreviews();
  if (succeeded > 0) await loadData();
  var hasRemainingWork = bulkFiles.some(function(item) {
    return item.status === 'pending' || item.status === 'uploading' || item.status === 'failed';
  });
  if (!hasRemainingWork) closeBulkUpload();
}

async function retryFailedUploads() {
  bulkFiles.forEach(function(item) {
    if (item.status === 'failed') {
      item.status = 'pending';
      item.error = '';
    }
  });
  renderBulkPreviews();
  await doBulkUpload();
}

function setupDragSort() {
  var grid = $('image-grid');
  if (!grid) return;
  var cards = grid.querySelectorAll('.image-card[draggable]');
  var dragSrc = null;
  cards.forEach(function(card) {
    card.addEventListener('dragstart', function(e) {
      dragSrc = card;
      card.classList.add('drag-ghost');
      e.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', function() {
      card.classList.remove('drag-ghost');
      grid.querySelectorAll('.image-card.drop-target').forEach(function(c) { c.classList.remove('drop-target'); });
      dragSrc = null;
    });
    card.addEventListener('dragover', function(e) {
      e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      if (card !== dragSrc) card.classList.add('drop-target');
    });
    card.addEventListener('dragleave', function() { card.classList.remove('drop-target'); });
    card.addEventListener('drop', async function(e) {
      e.preventDefault(); card.classList.remove('drop-target');
      if (!dragSrc || card === dragSrc) return;
      var srcId = parseInt(dragSrc.dataset.id);
      var dstId = parseInt(card.dataset.id);
      var group = S.photoGroups.find(function(g) { return g.id === currentGroupId; });
      if (!group || !group.images) return;
      var imgs = group.images.slice();
      var srcIdx = imgs.findIndex(function(i) { return i.id === srcId; });
      var dstIdx = imgs.findIndex(function(i) { return i.id === dstId; });
      if (srcIdx < 0 || dstIdx < 0) return;
      imgs.splice(dstIdx, 0, imgs.splice(srcIdx, 1)[0]);
      var order = imgs.map(function(i) { return i.id; });
      try {
        await api('/api/reorder', { method: 'POST', body: JSON.stringify({ table: 'photo_items', parent_col: 'group_id', parent_id: currentGroupId, order: order }) });
        toast('已排序');
        loadData();
      } catch(e) { toast('排序失败', true); }
    });
  });
}

loadData();
