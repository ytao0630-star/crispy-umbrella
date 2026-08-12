/* 工业园区资产管理系统 · 前端（原生 JS，无外部依赖） */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const API = {
  get: (p) => fetch(p).then(r => r.json()),
  post: (p, b) => fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then(r => r.json()),
  put: (p, b) => fetch(p, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then(r => r.json()),
  delete: (p) => fetch(p, { method: 'DELETE' }).then(r => r.json()),
};

let ROLE = '系统管理员';
const ROLES = ['系统管理员', '招商专员', '财务', '物业', '园区领导'];
// 客户漏斗分级（对齐《月度执行管控》Excel：线索→C类潜在→B类意向(到访)→A类成单）
const STAGES = ['线索', '潜在(C类)', '意向(B类)', '成单(A类)', '流失'];
const BIZ_TYPES = ['销售', '租赁'];
let SYS_TAB = 'users';
let CURRENT_VIEW = 'dashboard';
const CACHE = { buildings: [], customers: [], units: [], contracts: [] };

const PERMS = {
  '系统管理员': 'all',
  '招商专员': ['customers_add', 'contracts_add', 'unit_edit', 'lease_renew', 'lease_terminate', 'factory_view', 'merchants_add', 'merchants_edit', 'merchants_delete'],
  '财务': ['billing_add', 'receipt_add', 'meter_add', 'deposit_add', 'factory_view', 'merchants_add', 'merchants_edit', 'merchants_delete'],
  '物业': ['workorder_add', 'workorder_edit'],
  '园区领导': ['factory_view'],
};
function can(action) {
  if (ROLE === '系统管理员') return true;
  if (ROLE === '园区领导') return false;
  return (PERMS[ROLE] || []).includes(action);
}

// ---------- 工具 ----------
function fmt(n) {
  if (n === null || n === undefined) return '0';
  const v = Number(n);
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
}
function yuan(n) { return '¥' + fmt(n); }
function today() { return new Date().toISOString().slice(0, 10); }
function now() { return new Date().toISOString().slice(0, 19).replace('T', ' '); }
function tag(t) { return `<span class="tag t-${t}">${t}</span>`; }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 1800);
}
function sel(options, val) {
  return options.map(o => `<option value="${esc(o)}" ${o === val ? 'selected' : ''}>${esc(o)}</option>`).join('');
}
function bname(id) { const b = CACHE.buildings.find(x => x.id == id); return b ? b.name : '-'; }
function cname(id) { const c = CACHE.customers.find(x => x.id == id); return c ? c.name : '-'; }
function uname(id) { const u = CACHE.units.find(x => x.id == id); return u ? u.code : '-'; }
function ccode(id) { const c = CACHE.contracts.find(x => x.id == id); return c ? c.code : '-'; }

// ---------- 模态 ----------
function openModal(title, bodyHtml, onSave, saveLabel = '保存', modalClass = '') {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = bodyHtml;
  const modal = $('#modal'); modal.className = 'modal' + (modalClass ? ' ' + modalClass : '');
  const mask = $('#modalMask'); mask.classList.add('show');
  $('#modalSave')?.remove();
  const actions = document.createElement('div');
  actions.className = 'form-actions';
  actions.id = 'modalSave';
  if (onSave) {
    actions.innerHTML = `<button class="btn ghost" id="mCancel">取消</button><button class="btn" id="mOk">${saveLabel}</button>`;
    $('#modalBody').appendChild(actions);
    $('#mCancel').onclick = closeModal;
    $('#mOk').onclick = () => onSave();
  } else {
    actions.innerHTML = `<button class="btn" id="mClose">关闭</button>`;
    $('#modalBody').appendChild(actions);
    $('#mClose').onclick = closeModal;
  }
}
function closeModal() { $('#modalMask').classList.remove('show'); $('#modal').className = 'modal'; }

// ---------- 导航 ----------
function setView(v, sysTab) {
  CURRENT_VIEW = v;
  if (sysTab) SYS_TAB = sysTab;
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $$('.bnav-item').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $$('.nav-sub-item').forEach(b => b.classList.toggle('active', b.dataset.sysTab === SYS_TAB));
  // 自动展开当前视图所在的业务域分组，其余折叠
  $$('.nav-group').forEach(g => g.classList.remove('open'));
  const activeNav = $$('.nav-item').find(b => b.dataset.view === v)
    || $$('.nav-sub-item').find(b => b.classList.contains('active'));
  if (activeNav) { const g = activeNav.closest('.nav-group'); if (g) g.classList.add('open'); }
  const map = {
    dashboard: renderDashboard, assets: renderAssets, leases: renderLeases,
    'factory-rental': renderFactoryRental, 'factory-sales': renderFactorySales,
    customers: renderCrm, contracts: renderContracts, billing: renderBilling, meter: renderMeter,
    deposits: renderDeposits,
    merchants: renderMerchants,
    workorders: renderWorkOrders, system: renderSystem, market: renderMarket,
  };
  if (map[v]) { $('#view').innerHTML = '<div class="empty">加载中…</div>'; map[v](); }
  window.scrollTo(0, 0);
}
function refreshCurrent() {
  const map = {
    dashboard: renderDashboard, assets: renderAssets, leases: renderLeases,
    'factory-rental': renderFactoryRental, 'factory-sales': renderFactorySales,
    customers: renderCrm, contracts: renderContracts, billing: renderBilling, meter: renderMeter,
    deposits: renderDeposits,
    merchants: renderMerchants,
    workorders: renderWorkOrders, system: renderSystem, market: renderMarket,
  };
  if (map[CURRENT_VIEW]) map[CURRENT_VIEW]();
}

// ---------- 看板 ----------
async function renderDashboard() {
  const d = await API.get('/api/dashboard');
  const maxTrend = Math.max(1, ...d.revenue_trend.map(t => t.amount));
  const trendBars = d.revenue_trend.map(t =>
    `<div class="bar-row"><div class="bl">${t.month}</div><div class="bar-track"><div class="bar-fill" style="width:${(t.amount / maxTrend * 100).toFixed(1)}%"></div></div><div class="bv">${yuan(t.amount)}</div></div>`).join('');
  const statusEntries = Object.entries(d.by_status);
  const maxSt = Math.max(1, ...statusEntries.map(([, n]) => n));
  const statusBars = statusEntries.map(([k, n]) =>
    `<div class="bar-row"><div class="bl">${k}</div><div class="bar-track"><div class="bar-fill" style="width:${(n / maxSt * 100).toFixed(1)}%;background:#16a34a"></div></div><div class="bv">${n}</div></div>`).join('');
  const factory = d.factory, apt = d.apartment;
  $('#view').innerHTML = `
    <div class="section-title">运营看板 <span class="sub">实时汇总 · 数据本地存储</span></div>
    <div class="grid kpi-grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr));margin-bottom:20px">
      <div class="kpi blue"><div class="label">资产单元总数</div><div class="value">${d.total_units}</div></div>
      <div class="kpi green"><div class="label">整体出租率</div><div class="value">${d.lease_rate}<small>%</small></div></div>
      <div class="kpi purple"><div class="label">整体间夜出租率</div><div class="value">${d.night_rate}<small>%</small></div><div class="sub" style="font-size:11px;color:var(--muted);margin-top:4px">${d.occupied_nights}/${d.total_nights} 间夜</div></div>
      <div class="kpi green"><div class="label">整体销售去化率</div><div class="value">${d.sale_rate}<small>%</small></div></div>
      <div class="kpi amber"><div class="label">整体空置</div><div class="value">${d.vacant}</div></div>
      <div class="kpi red"><div class="label">整体欠费</div><div class="value">${yuan(d.arrears)}</div></div>
      <div class="kpi blue"><div class="label">整体收缴率</div><div class="value">${d.collection_rate}<small>%</small></div></div>
    </div>
    <div class="section-title" style="font-size:16px;margin-top:4px">🏭 厂房运营</div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">厂房总数</div><div class="value">${factory.total}</div></div>
      <div class="kpi green"><div class="label">厂房出租率</div><div class="value">${factory.lease_rate}<small>%</small></div></div>
      <div class="kpi purple"><div class="label">厂房间夜出租率</div><div class="value">${factory.night_rate}<small>%</small></div><div class="sub" style="font-size:11px;color:var(--muted);margin-top:4px">${factory.occupied_nights}/${factory.total_nights} 间夜</div></div>
      <div class="kpi green"><div class="label">厂房销售去化率</div><div class="value">${factory.sale_rate}<small>%</small></div></div>
      <div class="kpi amber"><div class="label">厂房空置</div><div class="value">${factory.vacant}</div></div>
      <div class="kpi red"><div class="label">厂房欠费</div><div class="value">${yuan(factory.arrears)}</div></div>
      <div class="kpi blue"><div class="label">厂房收缴率</div><div class="value">${factory.collection_rate}<small>%</small></div></div>
    </div>
    <div class="section-title" style="font-size:16px;margin-top:4px">🏠 公寓运营</div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">公寓总数</div><div class="value">${apt.total}</div></div>
      <div class="kpi green"><div class="label">公寓出租率</div><div class="value">${apt.lease_rate}<small>%</small></div></div>
      <div class="kpi purple"><div class="label">公寓间夜出租率</div><div class="value">${apt.night_rate}<small>%</small></div><div class="sub" style="font-size:11px;color:var(--muted);margin-top:4px">${apt.occupied_nights}/${apt.total_nights} 间夜</div></div>
      <div class="kpi amber"><div class="label">公寓空置</div><div class="value">${apt.vacant}</div></div>
      <div class="kpi red"><div class="label">公寓欠费</div><div class="value">${yuan(apt.arrears)}</div></div>
      <div class="kpi blue"><div class="label">公寓收缴率</div><div class="value">${apt.collection_rate}<small>%</small></div></div>
    </div>
    <div class="chart-flex">
      <div class="panel chart-box"><h3>单元状态分布</h3>${statusBars || '<div class="empty">无数据</div>'}</div>
      <div class="panel chart-box"><h3>近 6 个月实收趋势</h3>${trendBars || '<div class="empty">无数据</div>'}</div>
    </div>
    <div class="chart-flex">
      <div class="panel chart-box">
        <h3>收费概览</h3>
        <div class="bar-row"><div class="bl">应收总额</div><div class="bar-track"><div class="bar-fill" style="width:100%;background:#2563eb"></div></div><div class="bv">${yuan(d.total_ar)}</div></div>
        <div class="bar-row"><div class="bl">已收</div><div class="bar-track"><div class="bar-fill" style="width:${(d.total_paid / (d.total_ar || 1) * 100).toFixed(1)}%;background:#16a34a"></div></div><div class="bv">${yuan(d.total_paid)}</div></div>
        <div class="bar-row"><div class="bl">欠费</div><div class="bar-track"><div class="bar-fill" style="width:${(d.arrears / (d.total_ar || 1) * 100).toFixed(1)}%;background:#dc2626"></div></div><div class="bv">${yuan(d.arrears)}</div></div>
      </div>
      <div class="panel chart-box">
        <h3>工单统计</h3>
        ${(['待派', '处理中', '已完成'].map(s => `<div class="bar-row"><div class="bl">${s}</div><div class="bar-track"><div class="bar-fill" style="width:${((d.work_orders[s] || 0) / Math.max(1, Object.values(d.work_orders).reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%;background:#d97706"></div></div><div class="bv">${d.work_orders[s] || 0}</div></div>`)).join('')}
      </div>
    </div>`;
}

// ---------- 资产台账 ----------
async function renderAssets() {
  const [units, buildings] = await Promise.all([API.get('/api/units'), API.get('/api/buildings')]);
  CACHE.buildings = buildings; CACHE.units = units;
  const statusOpts = ['', '空置', '在租', '在售', '已售', '自持', '装修中', '锁定'];
  const typeOpts = ['', '厂房', '公寓'];
  const bOpts = ['', ...buildings.map(b => b.id)];
  $('#view').innerHTML = `
    <div class="section-title">资产台账 <span class="sub">楼栋 → 单元三级，状态实时联动</span></div>
    <div class="btn-row">
      ${can('unit_edit') ? '<button class="btn" id="addBuilding">+ 楼栋</button><button class="btn" id="addUnit">+ 单元</button>' : ''}
    </div>
    <div class="filters">
      <select id="fStatus">${statusOpts.map(o => `<option value="${o}">${o || '全部状态'}</option>`).join('')}</select>
      <select id="fType">${typeOpts.map(o => `<option value="${o}">${o || '全部业态'}</option>`).join('')}</select>
      <select id="fBld">${bOpts.map(o => `<option value="${o}">${o ? bname(o) : '全部楼栋'}</option>`).join('')}</select>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>单元编号</th><th>楼栋</th><th>业态</th><th>面积(㎡)</th><th>租金(月)</th><th>售价</th><th>状态</th><th>当前合同</th><th>当前客户</th>${can('unit_edit') ? '<th>操作</th>' : ''}</tr></thead>
      <tbody id="unitTable"></tbody>
    </table></div>`;
  function renderList() {
    const st = $('#fStatus').value, tp = $('#fType').value, bid = $('#fBld').value;
    let list = units.filter(u => (!st || u.status === st) && (!tp || u.type === tp) && (!bid || u.building_id == bid));
    $('#unitTable').innerHTML = list.map(u => `
      <tr>
        <td>${esc(u.code)}</td><td>${esc(bname(u.building_id))}</td><td>${tag(u.type)}</td>
        <td>${fmt(u.area)}</td><td>${u.rent_price ? yuan(u.rent_price) : '-'}</td><td>${u.property_price ? yuan(u.property_price) : '-'}</td>
        <td>${tag(u.status)}</td><td>${esc(ccode(u.current_contract_id))}</td><td>${esc(cname(u.current_customer_id))}</td>
        ${can('unit_edit') ? `<td><button class="btn sm ghost" onclick="editUnit(${u.id})">编辑</button></td>` : ''}
      </tr>`).join('') || '<tr><td colspan="10" class="empty">无记录</td></tr>';
  }
  $$('.filters select').forEach(s => s.onchange = renderList);
  renderList();
  if (can('unit_edit')) {
    $('#addBuilding').onclick = () => openModal('新增楼栋', `
      <div class="form-grid"><div class="form-row"><label>编号</label><input id="f_code"></div><div class="form-row"><label>名称</label><input id="f_name"></div><div class="form-row"><label>业态</label><select id="f_type">${sel(['厂房','公寓'])}</select></div><div class="form-row"><label>楼层数</label><input id="f_floors" type="number"></div><div class="form-row" style="grid-column:1/3"><label>地址</label><input id="f_addr"></div><div class="form-row" style="grid-column:1/3"><label>总面积</label><input id="f_area" type="number"></div></div>`, async () => {
      await API.post('/api/buildings', { code: $('#f_code').value, name: $('#f_name').value, type: $('#f_type').value, floors: +$('#f_floors').value || 0, address: $('#f_addr').value, total_area: +$('#f_area').value || 0 });
      closeModal(); toast('楼栋已添加'); renderAssets();
    });
    $('#addUnit').onclick = () => openModal('新增单元', `
      <div class="form-grid"><div class="form-row"><label>单元编号</label><input id="f_code"></div><div class="form-row"><label>所属楼栋</label><select id="f_bld">${bOpts.slice(1).map(o => `<option value="${o}">${bname(o)}</option>`).join('')}</select></div><div class="form-row"><label>业态</label><select id="f_type">${sel(['厂房','公寓'])}</select></div><div class="form-row"><label>面积(㎡)</label><input id="f_area" type="number"></div><div class="form-row"><label>月租金</label><input id="f_rent" type="number"></div><div class="form-row"><label>售价</label><input id="f_price" type="number"></div><div class="form-row"><label>可租</label><select id="f_rentable">${sel(['1','0'])}</select></div><div class="form-row"><label>可售</label><select id="f_sellable">${sel(['1','0'])}</select></div></div>`, async () => {
      await API.post('/api/units', { code: $('#f_code').value, building_id: +$('#f_bld').value, type: $('#f_type').value, area: +$('#f_area').value || 0, rent_price: +$('#f_rent').value || 0, property_price: +$('#f_price').value || 0, sellable: +$('#f_sellable').value, rentable: +$('#f_rentable').value, status: '空置' });
      closeModal(); toast('单元已添加'); renderAssets();
    });
  }
}
window.editUnit = async function(id) {
  const u = CACHE.units.find(x => x.id == id);
  openModal('编辑单元', `
    <div class="form-grid"><div class="form-row"><label>单元编号</label><input id="f_code" value="${esc(u.code)}"></div><div class="form-row"><label>面积(㎡)</label><input id="f_area" type="number" value="${u.area || ''}"></div><div class="form-row"><label>月租金</label><input id="f_rent" type="number" value="${u.rent_price || ''}"></div><div class="form-row"><label>售价</label><input id="f_price" type="number" value="${u.property_price || ''}"></div><div class="form-row"><label>状态</label><select id="f_status">${sel(['空置','在租','在售','已售','装修中','锁定'], u.status)}</select></div></div>`, async () => {
    await API.put('/api/units/' + id, { code: $('#f_code').value, area: +$('#f_area').value || 0, rent_price: +$('#f_rent').value || 0, property_price: +$('#f_price').value || 0, status: $('#f_status').value });
    closeModal(); toast('单元已更新'); renderAssets();
  });
};

// ---------- 公寓管理（独立登记表） ----------
async function renderLeases() {
  const summary = await API.get('/api/apartment-rentals/summary');
  const rooms = await API.get('/api/apartment-rooms');
  const year = new Date().getFullYear();
  let aptView = 'rooms'; // rooms | year
  let aptYear = String(year);
  CACHE.apartmentRooms = rooms;
  CACHE.aptSummary = summary;
  const statusOpts = ['', '空置', '已预订', '在住', '待退房'];
  const categoryOpts = ['', '单人间', '双人间', '四人间', '套房'];
  const floors = ['', ...new Set(rooms.map(r => r.floor).filter(Boolean))];
  let filters = { category: '', floor: '', keyword: '' };

  $('#view').innerHTML = `
    <div class="section-title">公寓管理 <span class="sub">房间主档 · 出租记录 · 按年视图</span>
      ${can('unit_edit') ? '<button class="btn primary" id="syncAptFees" style="float:right">⇩ 同步收费数据</button>' : ''}
    </div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">总房间数</div><div class="value">${summary.total}</div></div>
      <div class="kpi green"><div class="label">当前在住</div><div class="value">${summary.occupied}</div></div>
      <div class="kpi"><div class="label">当前空置</div><div class="value">${summary.vacant}</div></div>
      <div class="kpi green"><div class="label">押金总额</div><div class="value">${yuan(summary.deposit_total)}</div></div>
      <div class="kpi blue"><div class="label">月租总额</div><div class="value">${yuan(summary.rent_total)}</div></div>
      <div class="kpi red"><div class="label">待缴笔数</div><div class="value">${summary.pending_pay}</div></div>
    </div>
    <div class="view-tabs" id="aptTabs">
      <button class="vtab ${aptView === 'rooms' ? 'active' : ''}" data-v="rooms">房间列表</button>
      <button class="vtab ${aptView === 'year' ? 'active' : ''}" data-v="year">按年视图</button>
    </div>
    <div id="aptViewBody"></div>`;

  const syncBtn = $('#syncAptFees');
  if (syncBtn) syncBtn.onclick = () => syncApartmentFees();

  $$('#aptTabs .vtab').forEach(b => b.onclick = () => {
    aptView = b.dataset.v;
    $$('#aptTabs .vtab').forEach(x => x.classList.toggle('active', x.dataset.v === aptView));
    renderViewBody();
  });

  function renderViewBody() {
    if (aptView === 'rooms') renderRooms();
    else renderYear();
  }

  // ===== 房间列表 =====
  function renderRooms() {
    const filtersHtml = `
      <select id="f_category"><option value="">全部类别</option>${categoryOpts.slice(1).map(o => `<option value="${o}">${o}</option>`).join('')}</select>
      <select id="f_floor"><option value="">全部楼层</option>${floors.slice(1).map(o => `<option value="${o}">${o} 层</option>`).join('')}</select>
      <input id="f_kw" placeholder="搜索房号/企业/人员" style="min-width:180px">
      ${can('unit_edit') ? '<button class="btn" id="addRoom">+ 新增房间</button> <button class="btn ghost" id="addRental">+ 登记出租</button>' : ''}`;
    $('#aptViewBody').innerHTML = `
      <div class="filters" id="aptFilters">${filtersHtml}</div>
      <div class="table-wrap"><table>
        <thead><tr>
          <th>房号</th><th>楼层</th><th>类别</th><th>方位</th><th>当前状态</th>
          <th>现租户</th><th>企业</th><th>入驻</th><th>退房</th>
          <th>押金</th><th>月租</th><th>缴费</th><th>电表号</th><th>房卡</th><th>密码</th><th>指纹</th>
          ${can('unit_edit') ? '<th>操作</th>' : ''}
        </tr></thead>
        <tbody id="aptTable"></tbody>
      </table></div>`;
    $$('#aptFilters select, #aptFilters input').forEach(el => el.oninput = el.onchange = () => {
      filters = { category: $('#f_category').value, floor: $('#f_floor').value, keyword: $('#f_kw').value };
      renderList();
    });
    if (can('unit_edit')) {
      $('#addRoom').onclick = () => openRoomModal();
      $('#addRental').onclick = () => openRentalModal();
    }
    renderList();
  }
  function renderList() {
    let list = rooms.filter(r => {
      if (filters.category && r.room_category !== filters.category) return false;
      if (filters.floor && String(r.floor) !== filters.floor) return false;
      if (filters.keyword) {
        const cur = r.current || {};
        const kw = filters.keyword.toLowerCase();
        const text = `${r.room_no || ''} ${cur.company_name || ''} ${cur.occupant_name || ''}`.toLowerCase();
        if (!text.includes(kw)) return false;
      }
      return true;
    });
    $('#aptTable').innerHTML = list.map(r => {
      const cur = r.current || {};
      const status = cur.check_out_date ? '已退/空' : '在住';
      return `
      <tr>
        <td><b>${esc(r.room_no || '-')}</b></td><td>${esc(r.floor || '-')} 层</td><td>${esc(r.room_category || '-')}</td><td>${esc(r.orientation || '-')}</td>
        <td>${tag(cur.occupant_name ? status : '空置')}</td>
        <td>${esc(cur.occupant_name || '-')}</td><td>${esc(cur.company_name || '-')}</td>
        <td>${esc(cur.check_in_date || '-')}</td><td>${esc(cur.check_out_date || '-')}</td>
        <td>${yuan(cur.deposit || 0)}</td><td>${yuan(cur.monthly_rent || 0)}</td><td>${tag(cur.payment_status || '-')}</td>
        <td>${esc(r.meter_no || '-')}</td><td>${esc(cur.key_card || '-')}</td><td>${cur.room_password ? '<span class="pwd-mask" title="仅编辑/详情可见">******</span>' : '-'}</td><td>${esc(cur.fingerprint || '-')}</td>
        ${can('unit_edit') ? `<td>
          <button class="btn sm ghost" onclick="openRoomFeeModal(${r.id})">收费</button>
          <button class="btn sm ghost" onclick="openRoomHistory(${r.id})">出租记录</button>
          <button class="btn sm ghost" onclick="openRoomModal(${r.id})">编辑房</button>
          <button class="btn sm red" onclick="deleteRoom(${r.id})">删房</button>
        </td>` : ''}
      </tr>`;
    }).join('') || '<tr><td colspan="16" class="empty">无记录</td></tr>';
  }

  // ===== 按年视图 =====
  async function renderYear() {
    $('#aptViewBody').innerHTML = `
      <div class="filters">
        <label>年份</label><select id="f_year">${[year, year-1, year-2].map(y => `<option value="${y}" ${String(y)===aptYear?'selected':''}>${y} 年</option>`).join('')}</select>
        <span class="sub" style="margin-left:8px">蓝色竖边=入住月，红色竖边=退房月；悬停看精确起止，点击占用格看详情</span>
      </div>
      <div class="table-wrap" id="yearWrap"><div class="empty">加载中…</div></div>`;
    $('#f_year').onchange = () => { aptYear = $('#f_year').value; loadYear(); };
    await loadYear();
  }
  async function loadYear() {
    const data = await API.get('/api/apartment-year-view?year=' + aptYear);
    const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    let html = `<table class="year-table"><thead><tr><th class="yroom">房号/月</th>${months.map(m => `<th>${m}</th>`).join('')}</tr></thead><tbody>`;
    html += data.rooms.map(room => {
      const cells = months.map((m, i) => {
        const rec = room.months[i + 1];
        if (!rec) return `<td class="vacant" title="空置"></td>`;
        const name = rec.occupant_name || rec.company_name || '租户';
        const ci = rec.check_in_date || '';
        const co = rec.check_out_date || '';
        const ciMonth = ci ? parseInt(ci.slice(5, 7), 10) : null;
        const coMonth = co ? parseInt(co.slice(5, 7), 10) : null;
        const ciDay = ci ? parseInt(ci.slice(8, 10), 10) : null;
        const coDay = co ? parseInt(co.slice(8, 10), 10) : null;
        const isStart = ciMonth === (i + 1);
        const isEnd = coMonth === (i + 1);
        const classes = ['occupied'];
        if (isStart) classes.push('start-month');
        if (isEnd) classes.push('end-month');
        if (!isStart && !isEnd) classes.push('full-month');
        let hint = '';
        if (isStart && ciDay) hint = `<span class="ym-hint">${ciDay}日入住</span>`;
        else if (isEnd && coDay) hint = `<span class="ym-hint">${coDay}日退房</span>`;
        const tooltip = [
          esc(name),
          `企业：${esc(rec.company_name || '-')}`,
          `入住：${esc(ci || '-')}`,
          `退房：${esc(co || '至今')}`,
          `月租：${yuan(rec.monthly_rent || 0)}`,
          `押金：${yuan(rec.deposit || 0)}`,
          `缴费：${esc(rec.payment_status || '-')}`
        ].join('&#10;');
        return `<td class="${classes.join(' ')}" title="${tooltip}" onclick="openRentalModal(null, ${rec.id})"><div class="ycell-inner"><span class="yname">${esc(name)}</span>${hint}</div></td>`;
      }).join('');
      return `<tr><td class="yroom"><b>${esc(room.room_no)}</b><br><span class="ts">${esc(room.room_category||'')}</span></td>${cells}</tr>`;
    }).join('');
    html += '</tbody></table>';
    $('#yearWrap').innerHTML = html;
  }

  renderViewBody();
}

// ===== 房间主档弹窗 =====
window.openRoomModal = function(id) {
  const isEdit = !!id;
  const r = isEdit ? CACHE.apartmentRooms.find(x => x.id == id) : {};
  const categoryOpts = ['单人间', '双人间', '四人间', '套房'];
  const orientOpts = ['东', '西', '南', '北', '南北通透', '东南', '西南', '东北', '西北'];
  openModal(isEdit ? '编辑房间' : '新增房间', `
    <div class="form-grid">
      <div class="form-row"><label>楼层</label><input id="f_floor" value="${esc(r.floor || '')}" placeholder="如 3"></div>
      <div class="form-row"><label>房号</label><input id="f_room_no" value="${esc(r.room_no || '')}" placeholder="如 301"></div>
      <div class="form-row"><label>房间类别</label><select id="f_room_category">${sel(categoryOpts, r.room_category)}</select></div>
      <div class="form-row"><label>方位</label><select id="f_orientation">${sel(orientOpts, r.orientation)}</select></div>
      <div class="form-row"><label>电表号</label><input id="f_meter_no" value="${esc(r.meter_no || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>备注</label><input id="f_room_note" value="${esc(r.room_note || '')}"></div>
    </div>`, async () => {
    const body = {
      floor: $('#f_floor').value, room_no: $('#f_room_no').value,
      room_category: $('#f_room_category').value, orientation: $('#f_orientation').value,
      meter_no: $('#f_meter_no').value, room_note: $('#f_room_note').value,
    };
    if (isEdit) await API.put('/api/apartment-rooms/' + id, body);
    else await API.post('/api/apartment-rooms', body);
    closeModal(); toast(isEdit ? '房间已更新' : '房间已新增'); renderLeases();
  });
};
window.deleteRoom = async function(id) {
  if (!confirm('删除房间会同时删除其全部出租记录，确定？')) return;
  await API.delete('/api/apartment-rooms/' + id);
  toast('已删除'); renderLeases();
};

// ===== 出租记录弹窗（新增/编辑）=====
window.openRentalModal = async function(roomId, rentalId) {
  let room = null, rec = null;
  if (rentalId) {
    const rentals = await API.get('/api/apartment-rentals');
    rec = rentals.find(x => x.id == rentalId);
    room = CACHE.apartmentRooms.find(x => x.id == rec.room_id);
    roomId = rec.room_id;
  } else if (roomId) {
    room = CACHE.apartmentRooms.find(x => x.id == roomId);
  }
  const isEdit = !!rec;
  const statusOpts = ['待缴', '已缴', '欠费'];
  const roomsOpts = CACHE.apartmentRooms.map(x => `<option value="${x.id}" ${String(x.id)===String(roomId)?'selected':''}>${esc(x.room_no)}（${esc(x.room_category||'')}）</option>`).join('');
  openModal(isEdit ? '编辑出租记录' : '登记出租', `
    <div class="form-grid">
      <div class="form-row" style="grid-column:1/3"><label>房间</label><select id="f_room_id">${roomsOpts}</select></div>
      <div class="form-row" style="grid-column:1/3"><label>企业名称</label><input id="f_company_name" value="${esc(rec?rec.company_name:'')}"></div>
      <div class="form-row"><label>入住人员</label><input id="f_occupant_name" value="${esc(rec?rec.occupant_name:'')}"></div>
      <div class="form-row"><label>联系方式</label><input id="f_contact_phone" value="${esc(rec?rec.contact_phone:'')}"></div>
      <div class="form-row"><label>入住人数</label><input id="f_occupancy_count" type="number" value="${rec&&rec.occupancy_count!=null?rec.occupancy_count:''}"></div>
      <div class="form-row"><label>入驻时间</label><input id="f_check_in_date" type="date" value="${esc(rec?rec.check_in_date:'')}"></div>
      <div class="form-row"><label>退房时间</label><input id="f_check_out_date" type="date" value="${esc(rec?rec.check_out_date:'')}"></div>
      <div class="form-row"><label>押金（元）</label><input id="f_deposit" type="number" value="${rec&&rec.deposit!=null?rec.deposit:''}"></div>
      <div class="form-row"><label>房租/月（元）</label><input id="f_monthly_rent" type="number" value="${rec&&rec.monthly_rent!=null?rec.monthly_rent:''}"></div>
      <div class="form-row"><label>缴费状态</label><select id="f_payment_status">${sel(statusOpts, rec?rec.payment_status:'待缴')}</select></div>
      <div class="form-row"><label>电费（元）</label><input id="f_electric_balance" type="number" value="${rec&&rec.electric_balance!=null?rec.electric_balance:''}"></div>
      <div class="form-row"><label>房卡</label><input id="f_key_card" value="${esc(rec?rec.key_card:'')}"></div>
      <div class="form-row"><label>密码</label><input id="f_room_password" value="${esc(rec?rec.room_password:'')}"></div>
      <div class="form-row"><label>指纹</label><input id="f_fingerprint" value="${esc(rec?rec.fingerprint:'')}" placeholder="已录 / 未录 / -"></div>
      <div class="form-row"><label>承办人</label><input id="f_handler" value="${esc(rec?rec.handler:'')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>备注</label><input id="f_note" value="${esc(rec?rec.note:'')}"></div>
    </div>`, async () => {
    const body = {
      room_id: +$('#f_room_id').value,
      company_name: $('#f_company_name').value, occupant_name: $('#f_occupant_name').value,
      contact_phone: $('#f_contact_phone').value, occupancy_count: +$('#f_occupancy_count').value || 0,
      check_in_date: $('#f_check_in_date').value, check_out_date: $('#f_check_out_date').value,
      deposit: +$('#f_deposit').value || 0, monthly_rent: +$('#f_monthly_rent').value || 0,
      payment_status: $('#f_payment_status').value, electric_balance: +$('#f_electric_balance').value || 0,
      key_card: $('#f_key_card').value, room_password: $('#f_room_password').value,
      fingerprint: $('#f_fingerprint').value, handler: $('#f_handler').value, note: $('#f_note').value,
    };
    if (isEdit) await API.put('/api/apartment-rentals/' + rec.id, body);
    else await API.post('/api/apartment-rentals', body);
    closeModal(); toast(isEdit ? '已更新' : '已登记'); renderLeases();
  });
};

// ===== 房间出租历史（下钻时间线）=====
window.openRoomHistory = async function(roomId) {
  const room = CACHE.apartmentRooms.find(x => x.id == roomId);
  const rentals = await API.get('/api/apartment-rentals?room_id=' + roomId);
  const list = rentals.slice().reverse();
  openModal(`房间 ${esc(room.room_no)} 出租记录（${list.length} 次）`, `
    <div class="apt-history">
      ${list.map((r, i) => `
        <div class="hist-item">
          <div class="hist-head"><b>${esc(r.occupant_name || '未填')}</b> · ${esc(r.company_name || '-')}
            <span class="hist-date">${esc(r.check_in_date || '-')} ~ ${esc(r.check_out_date || '至今')}</span></div>
          <div class="hist-body">人数 ${r.occupancy_count||0} · 押金 ${yuan(r.deposit||0)} · 月租 ${yuan(r.monthly_rent||0)} · 缴费 ${esc(r.payment_status||'-')}</div>
          <div class="hist-foot">承办 ${esc(r.handler||'-')} ${r.note?`· ${esc(r.note)}`:''}</div>
          ${can('unit_edit') ? `<div class="hist-ops"><button class="btn sm ghost" onclick="openRentalModal(null, ${r.id})">编辑</button> <button class="btn sm red" onclick="deleteRental(${r.id})">删除</button></div>` : ''}
        </div>`).join('') || '<div class="empty">暂无出租记录</div>'}
    </div>
    ${can('unit_edit') ? `<div class="btn-row"><button class="btn" onclick="openRentalModal(${roomId})">+ 新增本次出租</button></div>` : ''}
  `, null, '关闭');
};
window.deleteRental = async function(id) {
  if (!confirm('确定删除该出租记录？')) return;
  await API.delete('/api/apartment-rentals/' + id);
  toast('已删除'); renderLeases();
};

// ===== 房间收费（押金/租金/电费/退押金等）=====
window.openRoomFeeModal = async function(roomId) {
  const room = CACHE.apartmentRooms.find(x => x.id == roomId);
  const rentals = await API.get('/api/apartment-rentals?room_id=' + roomId);
  const current = rentals.find(r => !r.check_out_date) || rentals[0];
  const rentalId = current ? current.id : null;
  const [fees, summary] = await Promise.all([
    API.get('/api/apartment-fees?room_id=' + roomId),
    API.get('/api/apartment-fees/summary?room_id=' + roomId)
  ]);
  const feeTypes = ['房租', '押金', '电费', '水费', '物业费', '网费', '退押金', '其他'];
  const payMethods = ['现金', '微信', '支付宝', '银行转账', '对公', '其他'];
  const feeStatus = ['已收', '已退', '待收'];
  const defaultOperator = current && current.handler ? current.handler : '';

  function refresh() { openRoomFeeModal(roomId); }

  const rowsHtml = feeTypes.map((t, i) => `
    <tr class="fee-batch-row" data-type="${esc(t)}">
      <td><input type="checkbox" class="f-check" id="f_check_${i}" data-idx="${i}"></td>
      <td><label for="f_check_${i}" style="cursor:pointer;font-weight:500">${esc(t)}</label></td>
      <td><input type="number" class="f-amount" id="f_amount_${i}" placeholder="0.00" style="min-width:90px"></td>
      <td>
        <select class="f-status" id="f_status_${i}">
          ${feeStatus.map(s => `<option value="${esc(s)}" ${s === (t === '退押金' ? '已退' : '已收') ? 'selected' : ''}>${esc(s)}</option>`).join('')}
        </select>
      </td>
      <td>
        <select class="f-method" id="f_method_${i}">
          ${payMethods.map(m => `<option value="${esc(m)}" ${m === '微信' ? 'selected' : ''}>${esc(m)}</option>`).join('')}
        </select>
      </td>
      <td><input type="text" class="f-note" id="f_note_${i}" placeholder="备注" style="min-width:120px"></td>
    </tr>
  `).join('');

  openModal(`房间 ${esc(room.room_no)} 收费管理`, `
    <div class="fee-summary">
      <div class="kpi blue"><div class="label">费用笔数</div><div class="value">${summary.count}</div></div>
      <div class="kpi green"><div class="label">实收总额</div><div class="value">${yuan(summary.income)}</div></div>
      <div class="kpi red"><div class="label">退款总额</div><div class="value">${yuan(summary.refund)}</div></div>
      <div class="kpi amber"><div class="label">押金结余</div><div class="value">${yuan(summary.deposit_balance)}</div></div>
    </div>
    <h4 style="margin:18px 0 10px;color:var(--muted);font-size:13px;font-weight:600">新增收费 / 退款</h4>
    <div class="form-grid fee-form" style="margin-bottom:12px">
      <div class="form-row"><label>统一日期</label><input id="f_batch_date" type="date" value="${today()}"></div>
      <div class="form-row"><label>经办人</label><input id="f_batch_operator" value="${esc(defaultOperator)}"></div>
    </div>
    <div class="fee-batch-actions" style="margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap">
      <button type="button" class="btn sm ghost" onclick="setFeeBatch('rent')">标准月费（房租+物业+网费）</button>
      <button type="button" class="btn sm ghost" onclick="setFeeBatch('utility')">水电费</button>
      <button type="button" class="btn sm ghost" onclick="setFeeBatch('deposit')">押金</button>
      <button type="button" class="btn sm ghost" onclick="setFeeBatch('refund')">退租结算</button>
      <button type="button" class="btn sm ghost" onclick="setFeeBatch('clear')">清空</button>
    </div>
    <div class="table-wrap"><table class="fee-table fee-batch-table">
      <thead><tr><th style="width:36px"><input type="checkbox" id="f_check_all"></th><th>费用类型</th><th>金额（元）</th><th>状态</th><th>支付方式</th><th>备注</th></tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table></div>
    <h4 style="margin:18px 0 10px;color:var(--muted);font-size:13px;font-weight:600">费用明细</h4>
    <div class="table-wrap"><table class="fee-table">
      <thead><tr><th>日期</th><th>类型</th><th>金额</th><th>状态</th><th>支付方式</th><th>经办人</th><th>备注</th><th>来源</th><th>操作</th></tr></thead>
      <tbody>
        ${fees.length ? fees.map(f => `
          <tr>
            <td>${esc(f.fee_date || '-')}</td>
            <td>${esc(f.fee_type || '-')}</td>
            <td>${yuan(f.amount || 0)}</td>
            <td>${tag(f.status || '已收')}</td>
            <td>${esc(f.pay_method || '-')}</td>
            <td>${esc(f.operator || '-')}</td>
            <td class="wrap">${esc(f.note || '-')}</td>
            <td>${tag(f.source === '收费' ? '收费' : '手工')}</td>
            <td>
              <button class="btn sm ghost" onclick="editApartmentFee(${f.id}, ${roomId})">编辑</button>
              <button class="btn sm red" onclick="deleteApartmentFee(${f.id}, ${roomId})">删除</button>
            </td>
          </tr>
        `).join('') : '<tr><td colspan="9" class="empty">暂无费用记录</td></tr>'}
      </tbody>
    </table></div>
  `, async () => {
    const date = $('#f_batch_date').value;
    const operator = $('#f_batch_operator').value;
    const items = [];
    feeTypes.forEach((t, i) => {
      const checked = $('#f_check_' + i).checked;
      const amount = +$('#f_amount_' + i).value || 0;
      if (!checked || !amount) return;
      items.push({
        room_id: roomId,
        rental_id: rentalId,
        fee_type: t,
        amount,
        fee_date: date,
        pay_method: $('#f_method_' + i).value,
        status: $('#f_status_' + i).value,
        operator,
        note: $('#f_note_' + i).value,
      });
    });
    if (!items.length) { toast('请至少勾选一项并填写金额'); return; }
    await API.post('/api/apartment-fees/batch', { items });
    closeModal(); toast(`已登记 ${items.length} 笔费用`); refresh();
  });

  // 全选/取消全选
  setTimeout(() => {
    const allBox = $('#f_check_all');
    if (allBox) allBox.onchange = () => {
      $$('.f-check').forEach(cb => cb.checked = allBox.checked);
    };
  }, 0);
};

window.syncApartmentFees = async function() {
  if (!confirm('将把「中心收费」中所有公寓类账单同步到公寓租赁：\n· 更新各房间出租记录的缴费状态\n· 生成/刷新公寓收费台账（来源标记为「收费同步」）\n\n该操作幂等，可重复执行。确定？')) return;
  const btn = $('#syncAptFees');
  if (btn) { btn.disabled = true; btn.textContent = '同步中…'; }
  try {
    const res = await API.post('/api/apartment/sync', {});
    const n = res && res.synced_bills != null ? res.synced_bills : '—';
    toast(`✅ 同步完成：公寓收费台账共 ${n} 笔`);
    await renderLeases();
  } catch (e) {
    toast('同步失败：' + (e && e.message ? e.message : e));
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⇩ 同步收费数据'; }
  }
};

window.setFeeBatch = function(preset) {
  const feeTypes = ['房租', '押金', '电费', '水费', '物业费', '网费', '退押金', '其他'];
  const map = {
    rent: ['房租', '物业费', '网费'],
    utility: ['电费', '水费'],
    deposit: ['押金'],
    refund: ['退押金', '其他'],
    clear: [],
  };
  const set = new Set(map[preset] || []);
  feeTypes.forEach((t, i) => {
    const cb = $('#f_check_' + i);
    if (!cb) return;
    cb.checked = set.has(t);
    if (preset === 'clear') $('#f_amount_' + i).value = '';
  });
};
window.editApartmentFee = async function(id, roomId) {
  const fee = (await API.get('/api/apartment-fees?room_id=' + roomId)).find(x => x.id == id);
  if (!fee) return;
  const feeTypes = ['房租', '押金', '电费', '水费', '物业费', '网费', '退押金', '其他'];
  const payMethods = ['现金', '微信', '支付宝', '银行转账', '对公', '其他'];
  const feeStatus = ['已收', '已退', '待收'];
  openModal('编辑费用记录', `
    <div class="form-grid">
      <div class="form-row"><label>费用类型</label><select id="f_fee_type">${sel(feeTypes, fee.fee_type)}</select></div>
      <div class="form-row"><label>金额（元）</label><input id="f_fee_amount" type="number" value="${fee.amount != null ? fee.amount : ''}"></div>
      <div class="form-row"><label>日期</label><input id="f_fee_date" type="date" value="${esc(fee.fee_date || '')}"></div>
      <div class="form-row"><label>支付方式</label><select id="f_pay_method">${sel(payMethods, fee.pay_method)}</select></div>
      <div class="form-row"><label>收支状态</label><select id="f_fee_status">${sel(feeStatus, fee.status)}</select></div>
      <div class="form-row"><label>经办人</label><input id="f_fee_operator" value="${esc(fee.operator || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>备注</label><input id="f_fee_note" value="${esc(fee.note || '')}"></div>
    </div>`, async () => {
    const body = {
      fee_type: $('#f_fee_type').value,
      amount: +$('#f_fee_amount').value || 0,
      fee_date: $('#f_fee_date').value,
      pay_method: $('#f_pay_method').value,
      status: $('#f_fee_status').value,
      operator: $('#f_fee_operator').value,
      note: $('#f_fee_note').value,
    };
    await API.put('/api/apartment-fees/' + id, body);
    closeModal(); toast('费用已更新'); openRoomFeeModal(roomId);
  });
};
window.deleteApartmentFee = async function(id, roomId) {
  if (!confirm('确定删除该费用记录？')) return;
  await API.delete('/api/apartment-fees/' + id);
  toast('已删除'); openRoomFeeModal(roomId);
};

// ---------- 厂房租赁 / 厂房销售 ----------
const FACTORY_STATE = {
  rental: { tab: 'list', year: String(new Date().getFullYear()) },
  sales: { tab: 'list', year: String(new Date().getFullYear()) }
};
function renderFactoryRental() { _renderFactory('rental'); }
function renderFactorySales() { _renderFactory('sales'); }

async function _renderFactory(kind) {
  const isRental = kind === 'rental';
  const s = FACTORY_STATE[kind];
  const title = isRental ? '厂房租赁' : '厂房销售';
  const sub = isRental ? '在租 / 空置厂房及租期管理' : '在售 / 已售厂房及回款管理';
  const allowedStatus = isRental ? ['空置','在租'] : ['空置','在售','已售'];
  const [units, buildings, customers] = await Promise.all([API.get('/api/factories'), API.get('/api/buildings'), API.get('/api/customers')]);
  CACHE.units = units; CACHE.buildings = buildings; CACHE.customers = customers;
  const visible = units.filter(u => allowedStatus.includes(u.status));

  const tab = (id, label) => `<button class="tab ${s.tab===id?'active':''}" onclick="FACTORY_STATE['${kind}'].tab='${id}';${isRental?'renderFactoryRental':'renderFactorySales'}()">${label}</button>`;
  $('#view').innerHTML = `
    <div class="section-title">${title} <span class="sub">${sub}</span></div>
    <div class="tabs">${tab('list', isRental?'租赁列表':'销售列表')}${tab('year','按年视图')}</div>
    <div id="factoryViewBody"></div>`;

  function renderList() {
    const st = $('#fStatus') ? $('#fStatus').value : '';
    let list = visible.filter(u => (!st || u.status === st));
    const statusOptions = isRental
      ? `<option value="">全部状态</option><option value="空置">空置</option><option value="在租">在租</option>`
      : `<option value="">全部状态</option><option value="空置">空置</option><option value="在售">在售</option><option value="已售">已售</option>`;
    const headers = isRental
      ? `<th>单元</th><th>楼栋</th><th>面积(㎡)</th><th>月租</th><th>状态</th><th>当前租户</th><th>租赁起止</th><th>操作</th>`
      : `<th>单元</th><th>楼栋</th><th>面积(㎡)</th><th>售价</th><th>状态</th><th>当前买方</th><th>签约日期</th><th>回款状态</th><th>操作</th>`;

    $('#factoryViewBody').innerHTML = `
      <div class="filters"><select id="fStatus">${statusOptions}</select></div>
      <div class="table-wrap"><table><thead><tr>${headers}</tr></thead><tbody id="factoryTable"></tbody></table></div>`;

    $('#factoryTable').innerHTML = list.map(u => {
      const ct = u.contract || {};
      const isLease = ct.type === '租赁';
      const isSale = ct.type === '销售';
      let ops = '';
      if (u.status === '空置' && can('contracts_add')) {
        ops += `<button class="btn sm ghost" onclick="openContractModal(${u.id},'${isRental?'租赁':'销售'}')">${isRental?'租赁':'销售'}</button> `;
      }
      if (can('contracts_add')) ops += `<button class="btn sm ghost" onclick="openUnitRecords(${u.id})">单位记录</button>`;

      if (isRental) {
        const range = isLease && ct.start_date ? `${esc(ct.start_date)} ~ ${esc(ct.end_date || '至今')}` : '-';
        const tenant = u.customer_name || (isLease ? '在租' : '-');
        return `<tr>
          <td><b>${esc(u.code)}</b></td><td>${esc(bname(u.building_id))}</td><td>${fmt(u.area)}</td>
          <td>${u.rent_price ? yuan(u.rent_price) : '-'}</td><td>${tag(u.status)}</td>
          <td>${esc(tenant)}</td><td>${esc(range)}</td><td>${ops || '-'}</td>
        </tr>`;
      } else {
        const saleDate = isSale && ct.start_date ? esc(ct.start_date) : '-';
        const buyer = u.customer_name || (isSale ? '已售' : '-');
        const payStatus = isSale ? esc(ct.sale_status || ct.status || '-') : '-';
        return `<tr>
          <td><b>${esc(u.code)}</b></td><td>${esc(bname(u.building_id))}</td><td>${fmt(u.area)}</td>
          <td>${u.property_price ? yuan(u.property_price) : '-'}</td><td>${tag(u.status)}</td>
          <td>${esc(buyer)}</td><td>${esc(saleDate)}</td><td>${esc(payStatus)}</td><td>${ops || '-'}</td>
        </tr>`;
      }
    }).join('') || `<tr><td colspan="${isRental?8:9}" class="empty">无记录</td></tr>`;
    if ($('#fStatus')) $('#fStatus').onchange = renderList;
  }

  async function renderYear() {
    $('#factoryViewBody').innerHTML = `
      <div class="filters">
        <label>年份</label><select id="f_year">${[s.year, +s.year-1, +s.year-2].map(y => `<option value="${y}" ${String(y)===s.year?'selected':''}>${y} 年</option>`).join('')}</select>
        <span class="sub" style="margin-left:8px">${isRental?'绿=租赁中（蓝边起租月 / 红边退租月）；悬停看租户/起止/金额':'紫=已售（标签约月）；悬停看买方/签约日/金额/回款'}</span>
      </div>
      <div class="table-wrap" id="factoryYearWrap"><div class="empty">加载中…</div></div>`;
    $('#f_year').onchange = () => { s.year = $('#f_year').value; loadFactoryYear(); };
    await loadFactoryYear();
  }

  async function loadFactoryYear() {
    const data = await API.get('/api/factory-year-view?year=' + s.year);
    const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
    let html = `<table class="year-table"><thead><tr><th class="yroom">单元/月</th>${months.map(m => `<th>${m}</th>`).join('')}</tr></thead><tbody>`;
    html += data.units.filter(u => allowedStatus.includes(u.status)).map(u => {
      const cells = months.map((m, i) => {
        const rec = u.months[i + 1];
        if (!rec || rec.kind !== (isRental ? '租赁' : '销售')) return `<td class="vacant" title="空置"></td>`;
        const name = rec.customer_name || (rec.kind === '销售' ? '买方' : '企业');
        const ci = rec.start_date || '';
        const co = rec.end_date || (rec.kind === '销售' ? rec.start_date : '');
        const ciMonth = ci ? parseInt(ci.slice(5, 7), 10) : null;
        const coMonth = co ? parseInt(co.slice(5, 7), 10) : null;
        const ciDay = ci ? parseInt(ci.slice(8, 10), 10) : null;
        const coDay = co ? parseInt(co.slice(8, 10), 10) : null;
        if (rec.kind === '销售') {
          const tooltip = [esc(name) + '（已售）', `签约：${esc(ci || '-')}`, `金额：${yuan(rec.amount || 0)}`,
            `回款：${esc(rec.sale_status || rec.status || '-')}`].join('&#10;');
          return `<td class="sold-cell" title="${tooltip}" onclick="openUnitRecords(${u.id})"><div class="ycell-inner"><span class="yname">${esc(name)}</span><span class="ym-hint sale">${ciDay ? ciDay + '日售' : '售'}</span></div></td>`;
        }
        const classes = ['occupied'];
        const isStart = ciMonth === (i + 1);
        const isEnd = coMonth === (i + 1);
        if (isStart) classes.push('start-month');
        if (isEnd) classes.push('end-month');
        if (!isStart && !isEnd) classes.push('full-month');
        let hint = '';
        if (isStart && ciDay) hint = `<span class="ym-hint">${ciDay}日租</span>`;
        else if (isEnd && coDay) hint = `<span class="ym-hint">${coDay}日退</span>`;
        const tooltip = [esc(name), `租赁起：${esc(ci || '-')}`, `到期：${esc(co || '至今')}`,
          `金额：${yuan(rec.amount || 0)}`, `押金：${yuan(rec.deposit || 0)}`, `状态：${esc(rec.status || '-')}`].join('&#10;');
        return `<td class="${classes.join(' ')}" title="${tooltip}" onclick="openUnitRecords(${u.id})"><div class="ycell-inner"><span class="yname">${esc(name)}</span>${hint}</div></td>`;
      }).join('');
      return `<tr><td class="yroom"><b>${esc(u.code)}</b><br><span class="ts">${esc(u.area ? fmt(u.area) + '㎡' : '')}</span></td>${cells}</tr>`;
    }).join('');
    html += '</tbody></table>';
    $('#factoryYearWrap').innerHTML = html;
  }

  if (s.tab === 'year') renderYear();
  else renderList();
}

// 单位记录（厂房租赁 + 销售历史下钻）
window.openUnitRecords = async function(unitId) {
  const u = CACHE.units.find(x => x.id == unitId);
  const contracts = await API.get('/api/contracts?unit_id=' + unitId);
  const rows = contracts.map(ct => `
    <tr>
      <td>${tag(ct.type)}</td><td>${esc(ct.code || '-')}</td>
      <td>${esc(ct.customer_name || cname(ct.customer_id) || '-')}</td>
      <td>${esc(ct.start_date || '-')} ~ ${esc(ct.end_date || '至今')}</td>
      <td>${yuan(ct.amount || 0)}</td><td>${esc(ct.pay_cycle || '-')}</td>
      <td>${yuan(ct.deposit || 0)}</td><td>${tag(ct.status)}</td>
    </tr>`).join('') || '<tr><td colspan="8" class="empty">暂无合同记录</td></tr>';
  openModal(`单位记录：${esc(u ? u.code : '')}`, `
    <div class="table-wrap"><table>
      <thead><tr><th>类型</th><th>合同号</th><th>客户</th><th>起止</th><th>金额</th><th>周期</th><th>押金</th><th>状态</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`, null, '关闭');
};

// ---------- 客户 CRM ----------
let CRM_TAB = 'list';
let CRM_CTRL_YEAR = 2026;
let CRM_CTRL_BIZ = '销售';
async function renderCrm() {
  const [customers, summary, followups, channels] = await Promise.all([
    API.get('/api/customers'), API.get('/api/crm/summary'), API.get('/api/crm/followups'), API.get('/api/channels')
  ]);
  CACHE.customers = customers;
  CACHE.channels = channels;
  const chMap = {}; channels.forEach(ch => chMap[ch.id] = (ch.category ? ch.category + ' / ' : '') + ch.name);
  let currentStage = '';
  let currentBiz = '';
  let currentSource = '';
  const tab = (id, label) => `<button class="tab ${CRM_TAB===id?'active':''}" onclick="CRM_TAB='${id}';renderCrm()">${label}</button>`;
  $('#view').innerHTML = `
    <div class="section-title">客户管理 <span class="sub">销售/租赁双线 · 线索→C类→B类→A类漏斗</span></div>
    <div class="tabs">${tab('list','客户列表')}${tab('control','执行管控')}</div>
    ${CRM_TAB==='control' ? '<div id="crmControlWrap"></div>' : `
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">客户总数</div><div class="value">${summary.total}</div></div>
      ${STAGES.map(s => `<div class="kpi"><div class="label">${s}</div><div class="value">${summary.by_stage[s] || 0}</div></div>`).join('')}
      <div class="kpi amber"><div class="label">待跟进</div><div class="value">${summary.follow_due}</div></div>
    </div>
    <div class="filters">
      <select id="fStage"><option value="">全部阶段</option>${STAGES.map(s => `<option value="${s}">${s}</option>`).join('')}</select>
      <select id="fBiz"><option value="">全部业务线</option>${BIZ_TYPES.map(s => `<option value="${s}">${s}</option>`).join('')}</select>
      <select id="fSource"><option value="">全部来源</option>${Object.keys(summary.by_source || {}).map(s => `<option value="${s}">${s}</option>`).join('')}</select>
      <input id="fKw" placeholder="搜索客户名/联系人/电话">
      ${can('customers_add') ? '<button class="btn" id="addCust">+ 新增客户</button>' : ''}
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>名称</th><th>类型</th><th>业务线</th><th>阶段</th><th>渠道</th><th>来源</th><th>负责人</th><th>行业</th><th>需求</th><th>预算</th><th>最近跟进</th><th>下次跟进</th><th>操作</th></tr></thead>
      <tbody id="crmTable"></tbody>
    </table></div>`}`;
  if (CRM_TAB === 'control') { renderCrmControl(); return; }
  function renderList() {
    const kw = $('#fKw').value.toLowerCase();
    let list = customers.filter(c => {
      if (currentStage && c.stage !== currentStage) return false;
      if (currentBiz && c.biz_type !== currentBiz) return false;
      if (currentSource && c.source !== currentSource) return false;
      if (kw && !`${c.name} ${c.contact} ${c.phone} ${c.industry}`.toLowerCase().includes(kw)) return false;
      return true;
    });
    $('#crmTable').innerHTML = list.map(c => `
      <tr>
        <td>${esc(c.name)}</td><td>${tag(c.type)}</td><td>${tag(c.biz_type||'销售')}</td><td>${tag(c.stage || '线索')}</td>
        <td>${esc(chMap[c.channel_id] || '-')}</td><td>${esc(c.source || '-')}</td><td>${esc(c.owner || '-')}</td>
        <td>${esc(c.industry || '-')}</td><td>${esc(c.demand || '-')}</td><td>${c.budget ? yuan(c.budget) : '-'}</td>
        <td>${esc(c.last_follow || '-')}</td><td>${esc(c.next_follow || '-')}</td>
        <td><button class="btn sm ghost" onclick="openCrm(${c.id})">详情</button></td>
      </tr>`).join('') || '<tr><td colspan="13" class="empty">无记录</td></tr>';
  }
  $('#fStage').onchange = () => { currentStage = $('#fStage').value; renderList(); };
  $('#fBiz').onchange = () => { currentBiz = $('#fBiz').value; renderList(); };
  $('#fSource').onchange = () => { currentSource = $('#fSource').value; renderList(); };
  $('#fKw').oninput = renderList;
  renderList();
  if (can('customers_add')) $('#addCust').onclick = () => openCustomerModal();
}
window.openCustomerModal = function(c = {}) {
  const isEdit = !!c.id;
  const sources = ['官网', '转介绍', '中介', '电话', '展会', '其他'];
  const channels = CACHE.channels || [];
  const chByCat = {};
  channels.forEach(ch => { (chByCat[ch.category] = chByCat[ch.category] || []).push(ch); });
  const chOpts = Object.keys(chByCat).map(cat =>
    `<optgroup label="${esc(cat)}">${chByCat[cat].map(ch => `<option value="${ch.id}" ${String(c.channel_id)===String(ch.id)?'selected':''}>${esc(ch.name)}</option>`).join('')}</optgroup>`
  ).join('');
  openModal(isEdit ? '编辑客户' : '新增客户', `
    <div class="form-grid">
      <div class="form-row"><label>类型</label><select id="f_type">${sel(['企业','个人'], c.type)}</select></div>
      <div class="form-row"><label>名称</label><input id="f_name" value="${esc(c.name || '')}"></div>
      <div class="form-row"><label>联系人</label><input id="f_contact" value="${esc(c.contact || '')}"></div>
      <div class="form-row"><label>电话</label><input id="f_phone" value="${esc(c.phone || '')}"></div>
      <div class="form-row"><label>业务线</label><select id="f_biz_type">${sel(BIZ_TYPES, c.biz_type || '销售')}</select></div>
      <div class="form-row"><label>阶段</label><select id="f_stage">${sel(STAGES, c.stage || '线索')}</select></div>
      <div class="form-row"><label>渠道</label><select id="f_channel_id"><option value="">未选</option>${chOpts}</select></div>
      <div class="form-row"><label>来源</label><select id="f_source">${sel(sources, c.source || '其他')}</select></div>
      <div class="form-row"><label>负责人</label><input id="f_owner" value="${esc(c.owner || '')}"></div>
      <div class="form-row"><label>行业</label><input id="f_industry" value="${esc(c.industry || '')}"></div>
      <div class="form-row"><label>需求</label><input id="f_demand" value="${esc(c.demand || '')}"></div>
      <div class="form-row"><label>预算</label><input id="f_budget" type="number" value="${c.budget || ''}"></div>
      <div class="form-row"><label>标签</label><input id="f_tags" value="${esc(c.tags || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>地址</label><input id="f_address" value="${esc(c.address || '')}"></div>
    </div>`, async () => {
    const body = {
      type: $('#f_type').value, name: $('#f_name').value, contact: $('#f_contact').value, phone: $('#f_phone').value,
      biz_type: $('#f_biz_type').value, stage: $('#f_stage').value, channel_id: $('#f_channel_id').value || null,
      source: $('#f_source').value, owner: $('#f_owner').value,
      industry: $('#f_industry').value, demand: $('#f_demand').value, budget: +$('#f_budget').value || 0,
      tags: $('#f_tags').value, address: $('#f_address').value,
    };
    if (c.type === '企业') body.credit_code = c.credit_code || '';
    else body.id_number = c.id_number || '';
    if (isEdit) await API.put('/api/customers/' + c.id, body);
    else await API.post('/api/customers', body);
    closeModal(); toast(isEdit ? '客户已更新' : '客户已添加'); renderCrm();
  });
};
window.openCrm = async function(id) {
  const c = CACHE.customers.find(x => x.id == id);
  const follows = await API.get('/api/crm/followups?customer_id=' + id);
  const stageOpts = STAGES.slice();
  const ch = (CACHE.channels || []).find(x => String(x.id) === String(c.channel_id));
  const chName = ch ? (ch.category + ' / ' + ch.name) : '-';
  openModal('客户详情：' + c.name, `
    <div class="crm-detail">
      <div class="kv"><span>阶段</span><b>${tag(c.stage || '线索')}</b></div>
      <div class="kv"><span>业务线</span><b>${tag(c.biz_type || '销售')}</b></div>
      <div class="kv"><span>渠道</span><b>${esc(chName)}</b></div>
      <div class="kv"><span>来源</span><b>${esc(c.source || '-')}</b></div>
      <div class="kv"><span>负责人</span><b>${esc(c.owner || '-')}</b></div>
      <div class="kv"><span>行业</span><b>${esc(c.industry || '-')}</b></div>
      <div class="kv"><span>需求</span><b>${esc(c.demand || '-')}</b></div>
      <div class="kv"><span>预算</span><b>${c.budget ? yuan(c.budget) : '-'}</b></div>
      <div class="kv"><span>电话</span><b>${esc(c.phone || '-')}</b></div>
      <div class="kv"><span>地址</span><b>${esc(c.address || '-')}</b></div>
    </div>
    <div style="border-top:1px solid var(--line);margin:14px 0 10px;padding-top:10px"><b>跟进记录</b> ${can('customers_add') ? '<button class="btn sm ghost" id="addFollow">+ 新增跟进</button>' : ''}</div>
    <div id="followList">${follows.length ? follows.map(f => `<div class="follow-item"><div class="follow-head"><b>${f.date}</b> ${esc(f.type)} · ${esc(f.operator || '-')}</div><div class="follow-body">${esc(f.content)}</div>${f.next_plan ? `<div class="follow-next">下次：${esc(f.next_plan)}</div>` : ''}</div>`).join('') : '<div class="empty" style="padding:20px">暂无跟进</div>'}</div>`, null);
  if (can('customers_add')) {
    $('#addFollow').onclick = () => openFollowModal(id);
  }
};
window.openFollowModal = function(customerId) {
  const c = CACHE.customers.find(x => x.id == customerId);
  openModal('新增跟进', `
    <div class="form-grid">
      <div class="form-row"><label>跟进日期</label><input id="f_date" type="date" value="${today()}"></div>
      <div class="form-row"><label>跟进方式</label><select id="f_type">${sel(['电话','拜访','微信','邮件','其他'])}</select></div>
      <div class="form-row" style="grid-column:1/3"><label>跟进内容</label><input id="f_content"></div>
      <div class="form-row"><label>下次计划</label><input id="f_next_plan"></div>
      <div class="form-row"><label>经办人</label><input id="f_operator" value="${esc(ROLE)}"></div>
      <div class="form-row"><label>同时更新客户阶段</label><select id="f_stage">${sel(['', ...STAGES], '')}</select></div>
    </div>`, async () => {
    const body = { customer_id: customerId, date: $('#f_date').value, type: $('#f_type').value, content: $('#f_content').value, next_plan: $('#f_next_plan').value, operator: $('#f_operator').value };
    await API.post('/api/crm/followups', body);
    const stage = $('#f_stage').value;
    if (stage) {
      await API.put('/api/customers/' + customerId, { stage, last_follow: $('#f_date').value, next_follow: $('#f_next_plan').value });
    }
    closeModal(); toast('跟进已保存'); renderCrm();
  });
};

// ---------- 执行管控看板（销售/租赁双线漏斗：计划 vs 实际）----------
async function renderCrmControl() {
  const wrap = document.getElementById('crmControlWrap');
  if (!wrap) return;
  const year = CRM_CTRL_YEAR || new Date().getFullYear();
  const data = await API.get('/api/crm/control?year=' + year);
  const biz = CRM_CTRL_BIZ || '销售';
  const months = (data.biz_types[biz] || {months: []}).months;
  const pct = v => v == null ? '<span class="muted">-</span>' : (v * 100).toFixed(0) + '%';
  wrap.innerHTML = `
    <div class="ctrl-bar">
      <select id="ctrlYear">${[2024,2025,2026,2027].map(y => `<option value="${y}" ${y==year?'selected':''}>${y}年</option>`).join('')}</select>
      <select id="ctrlBiz">${BIZ_TYPES.map(b => `<option ${b==biz?'selected':''}>${b}</option>`).join('')}</select>
      ${can('customers_add') ? '<button class="btn" id="editPlan">录入月度计划</button>' : ''}
      <span class="sub">实际值由客户里程碑日期自动计算；计划值点击「录入月度计划」填写</span>
    </div>
    <div class="table-wrap"><table class="ctrl-table">
      <thead><tr><th>月份</th><th>计划C</th><th>实际C</th><th>计划B</th><th>实际B</th><th>计划A</th><th>实际A</th><th>本月完成率(A)</th><th>累计A</th><th>累计完成率(A)</th><th>转化率(B→A)</th></tr></thead>
      <tbody>
        ${months.map(m => `<tr>
          <td>${m.month}月</td>
          <td>${m.plan_C}</td><td class="${m.actual_C?'hl':''}">${m.actual_C}</td>
          <td>${m.plan_B}</td><td class="${m.actual_B?'hl':''}">${m.actual_B}</td>
          <td>${m.plan_A}</td><td class="${m.actual_A?'hl':''}">${m.actual_A}</td>
          <td>${pct(m.rate_A)}</td>
          <td>${m.cum_A}</td><td>${pct(m.cum_rate_A)}</td>
          <td>${pct(m.cum_conv_BA)}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
  $('#ctrlYear').onchange = () => { CRM_CTRL_YEAR = +$('#ctrlYear').value; renderCrmControl(); };
  $('#ctrlBiz').onchange = () => { CRM_CTRL_BIZ = $('#ctrlBiz').value; renderCrmControl(); };
  if (can('customers_add')) $('#editPlan').onclick = () => openPlanModal(year, biz, months);
}

window.openPlanModal = async function(year, biz, months) {
  const plans = await API.get('/api/crm-plans?year=' + year);
  const exMap = {}; plans.forEach(p => { if (p.biz_type === biz) exMap[p.month] = p; });
  openModal(`${year}年 ${biz} 月度计划`, `
    <div class="table-wrap"><table class="plan-edit">
      <thead><tr><th>月份</th><th>计划新增C类</th><th>计划新增B类</th><th>计划成单A类</th></tr></thead>
      <tbody>
        ${Array.from({length: 12}, (_, i) => { const m = i + 1; const e = exMap[m] || {}; return `<tr>
          <td>${m}月</td>
          <td><input id="pc_${m}" type="number" value="${e.plan_C || ''}" placeholder="0"></td>
          <td><input id="pb_${m}" type="number" value="${e.plan_B || ''}" placeholder="0"></td>
          <td><input id="pa_${m}" type="number" value="${e.plan_A || ''}" placeholder="0"></td>
        </tr>`; }).join('')}
      </tbody>
    </table></div>`, async () => {
    for (let m = 1; m <= 12; m++) {
      const body = {
        year, month: m, biz_type: biz,
        plan_C: +($('#pc_' + m).value) || 0,
        plan_B: +($('#pb_' + m).value) || 0,
        plan_A: +($('#pa_' + m).value) || 0,
      };
      const ex = exMap[m];
      if (ex) await API.put('/api/crm-plans/' + ex.id, body);
      else await API.post('/api/crm-plans', body);
    }
    closeModal(); toast('月度计划已保存'); renderCrmControl();
  });
};

// ---------- 市场调研 ----------
async function renderMarket() {
  const rows = await API.get('/api/market-research');
  CACHE.marketRecords = rows;
  const types = ['', ...new Set(rows.map(r => r.type).filter(Boolean))];
  const statuses = ['', ...new Set(rows.map(r => r.status).filter(Boolean))];
  let fType = '', fStatus = '', kw = '';
  $('#view').innerHTML = `
    <div class="section-title">市场调研 <span class="sub">周边竞品厂房详情</span></div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">样本数</div><div class="value">${rows.length}</div></div>
      <div class="kpi green"><div class="label">在售/招商中</div><div class="value">${rows.filter(r => r.status && r.status.includes('售') || r.status.includes('招商')).length}</div></div>
      <div class="kpi amber"><div class="label">均价(售)</div><div class="value">${yuan(rows.filter(r => r.sale_price).reduce((a, r) => a + r.sale_price, 0) / Math.max(1, rows.filter(r => r.sale_price).length))}</div></div>
      <div class="kpi purple"><div class="label">均租</div><div class="value">${yuan(rows.filter(r => r.rent_price).reduce((a, r) => a + r.rent_price, 0) / Math.max(1, rows.filter(r => r.rent_price).length))}</div></div>
    </div>
    <div class="filters">
      <select id="fType"><option value="">全部类型</option>${types.slice(1).map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('')}</select>
      <select id="fStatus"><option value="">全部租售情况</option>${statuses.slice(1).map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('')}</select>
      <input id="fKw" placeholder="搜索竞品名/区位">
      ${can('unit_edit') ? '<button class="btn" id="addMarket">+ 新增竞品</button>' : ''}
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>竞品/园区</th><th>厂房类型</th><th>面积(㎡)</th><th>对外售价</th><th>租金</th><th>租售情况</th><th>区位</th><th>距离</th><th>优势</th><th>备注</th><th>操作</th></tr></thead>
      <tbody id="marketTable"></tbody>
    </table></div>`;
  function renderList() {
    let list = rows.filter(r => (!fType || r.type === fType) && (!fStatus || r.status === fStatus) && (!kw || `${r.name} ${r.address} ${r.advantage}`.toLowerCase().includes(kw)));
    $('#marketTable').innerHTML = list.map(r => `
      <tr>
        <td>${esc(r.name)}</td><td>${esc(r.type)}</td><td>${fmt(r.area)}</td><td>${r.sale_price ? yuan(r.sale_price) : '-'}</td><td>${r.rent_price ? yuan(r.rent_price) : '-'}</td><td>${tag(r.status)}</td><td>${esc(r.address || '-')}</td><td>${esc(r.distance || '-')}</td><td class="wrap">${esc(r.advantage || '-')}</td><td class="wrap">${esc(r.note || '-')}</td>
        <td><button class="btn sm" onclick="openMarketDetail(${r.id})">详情</button> ${can('unit_edit') ? `<button class="btn sm ghost" onclick="editMarket(${r.id})">编辑</button> <button class="btn sm red" onclick="deleteMarket(${r.id})">删除</button>` : ''}</td>
      </tr>`).join('') || '<tr><td colspan="11" class="empty">无记录</td></tr>';
  }
  $('#fType').onchange = () => { fType = $('#fType').value; renderList(); };
  $('#fStatus').onchange = () => { fStatus = $('#fStatus').value; renderList(); };
  $('#fKw').oninput = () => { kw = $('#fKw').value.toLowerCase(); renderList(); };
  renderList();
  if (can('unit_edit')) $('#addMarket').onclick = () => openMarketModal();
}
window.openMarketDetail = function(id) {
  const r = (CACHE.marketRecords || []).find(x => x.id == id);
  if (!r) return toast('记录不存在');
  openMarketDetailModal(r);
};
window.openMarketDetailModal = function(r = {}) {
  if (!r.id) return toast('请先保存后再填写详情');
  const sections = [
    { title: '概况', fields: [
      { key: 'name', label: '竞品/园区名', span: true },
      { key: 'type', label: '厂房类型', type: 'select', options: ['标准厂房','独栋厂房','分层厂房','钢结构厂房'] },
      { key: 'area', label: '面积(㎡)', type: 'number' },
      { key: 'sale_price', label: '对外售价(元/㎡)', type: 'number' },
      { key: 'rent_price', label: '租金(元/㎡/天)', type: 'number' },
      { key: 'status', label: '租售情况', type: 'select', options: ['招商中','满租','部分空置','在售','已售罄'] },
      { key: 'address', label: '区位' },
      { key: 'distance', label: '距本园区' },
      { key: 'advantage', label: '优势', span: true, type: 'textarea' },
      { key: 'note', label: '备注', span: true, type: 'textarea' },
    ]},
    { title: '建筑指标', fields: [
      { key: 'floor_height', label: '层高(m)', type: 'number' },
      { key: 'load_bearing', label: '承重(吨/㎡)', type: 'number' },
      { key: 'column_span', label: '柱距(m)', type: 'number' },
      { key: 'plot_ratio', label: '容积率', type: 'number' },
      { key: 'power_capacity', label: '配电(KVA)', type: 'number' },
      { key: 'fire_rating', label: '消防等级', type: 'select', options: ['甲级','乙级','丙级','丁级','戊级','无'] },
      { key: 'delivery_floor', label: '交付标准-地面' },
      { key: 'delivery_wall', label: '交付标准-墙面' },
      { key: 'delivery_roof', label: '交付标准-屋顶' },
      { key: 'delivery_door', label: '交付标准-门窗' },
    ]},
    { title: '费用与配套', fields: [
      { key: 'property_fee', label: '物业费(元/㎡/月)', type: 'number' },
      { key: 'water_fee', label: '水费(元/吨)', type: 'number' },
      { key: 'electricity_fee', label: '电费(元/度)', type: 'number' },
      { key: 'parking_fee', label: '停车费(元/月)', type: 'number' },
      { key: 'parking_count', label: '停车位数量', type: 'number' },
      { key: 'canteen', label: '食堂配套' },
      { key: 'dormitory', label: '宿舍配套' },
      { key: 'office_facility', label: '办公配套' },
      { key: 'logistics_facility', label: '物流配套' },
      { key: 'surrounding_biz', label: '周边商业', type: 'textarea', span: true },
    ]},
    { title: '交通', fields: [
      { key: 'dist_expressway', label: '距高速口(km)', type: 'number' },
      { key: 'dist_subway', label: '距地铁站(km)', type: 'number' },
      { key: 'dist_airport', label: '距机场(km)', type: 'number' },
      { key: 'bus_lines', label: '公交线路', span: true },
    ]},
    { title: '招商与竞争分析', fields: [
      { key: 'target_industry', label: '目标客户行业' },
      { key: 'commission_rate', label: '佣金点数(%)', type: 'number' },
      { key: 'contact_name', label: '招商联系人' },
      { key: 'contact_title', label: '职务' },
      { key: 'contact_phone', label: '联系电话' },
      { key: 'policy', label: '招商政策/优惠', span: true, type: 'textarea' },
      { key: 'our_advantage', label: '我方优势', span: true, type: 'textarea' },
      { key: 'our_weakness', label: '我方劣势', span: true, type: 'textarea' },
      { key: 'follow_up_plan', label: '跟进建议', span: true, type: 'textarea' },
      { key: 'research_date', label: '调研日期', type: 'date' },
      { key: 'researcher', label: '调研员' },
    ]},
  ];
  function mkField(f) {
    const v = r[f.key] ?? '';
    const span = f.span ? ' style="grid-column:1/3"' : '';
    let input = '';
    if (f.type === 'select') {
      input = `<select id="f_${f.key}">${sel(f.options, v)}</select>`;
    } else if (f.type === 'date') {
      input = `<input id="f_${f.key}" type="date" value="${esc(v)}">`;
    } else if (f.type === 'number') {
      input = `<input id="f_${f.key}" type="number" step="any" value="${v ? v : ''}">`;
    } else if (f.type === 'textarea') {
      input = `<textarea id="f_${f.key}" rows="2">${esc(v)}</textarea>`;
    } else {
      input = `<input id="f_${f.key}" value="${esc(v)}">`;
    }
    return `<div class="form-row"${span}><label>${f.label}</label>${input}</div>`;
  }
  const bodyHtml = `<div class="form-grid">${sections.map(s => `<div class="detail-section">${s.title}</div>` + s.fields.map(mkField).join('')).join('')}</div>`;
  openModal(`竞品详情：${esc(r.name)}`, bodyHtml, async () => {
    const body = {};
    sections.forEach(s => s.fields.forEach(f => {
      const el = $('#f_' + f.key);
      body[f.key] = f.type === 'number' ? (+el.value || 0) : el.value;
    }));
    await API.put('/api/market-research/' + r.id, body);
    closeModal(); toast('竞品详情已保存'); renderMarket();
  }, '保存', 'wide');
};
window.openMarketModal = function(r = {}) {
  const isEdit = !!r.id;
  openModal(isEdit ? '编辑竞品' : '新增竞品', `
    <div class="form-grid">
      <div class="form-row" style="grid-column:1/3"><label>竞品/园区名</label><input id="f_name" value="${esc(r.name || '')}"></div>
      <div class="form-row"><label>厂房类型</label><select id="f_type">${sel(['标准厂房','独栋厂房','分层厂房','钢结构厂房'], r.type)}</select></div>
      <div class="form-row"><label>面积(㎡)</label><input id="f_area" type="number" value="${r.area || ''}"></div>
      <div class="form-row"><label>对外售价(元/㎡)</label><input id="f_sale_price" type="number" value="${r.sale_price || ''}"></div>
      <div class="form-row"><label>租金(元/㎡/天)</label><input id="f_rent_price" type="number" value="${r.rent_price || ''}"></div>
      <div class="form-row"><label>租售情况</label><select id="f_status">${sel(['招商中','满租','部分空置','在售','已售罄'], r.status)}</select></div>
      <div class="form-row"><label>区位</label><input id="f_address" value="${esc(r.address || '')}"></div>
      <div class="form-row"><label>距本园区</label><input id="f_distance" value="${esc(r.distance || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>优势</label><input id="f_advantage" value="${esc(r.advantage || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>备注</label><input id="f_note" value="${esc(r.note || '')}"></div>
    </div>`, async () => {
    const body = { name: $('#f_name').value, type: $('#f_type').value, area: +$('#f_area').value || 0, sale_price: +$('#f_sale_price').value || 0, rent_price: +$('#f_rent_price').value || 0, status: $('#f_status').value, address: $('#f_address').value, distance: $('#f_distance').value, advantage: $('#f_advantage').value, note: $('#f_note').value };
    if (isEdit) await API.put('/api/market-research/' + r.id, body);
    else await API.post('/api/market-research', body);
    closeModal(); toast(isEdit ? '竞品已更新' : '竞品已添加'); renderMarket();
  });
};
window.editMarket = function(id) { const r = (CACHE.marketRecords || []).find(x => x.id == id); openMarketModal(r); };
window.deleteMarket = async function(id) { if (!confirm('确定删除？')) return; await API.delete('/api/market-research/' + id); toast('已删除'); renderMarket(); };

// ---------- 合同 ----------
async function renderContracts() {
  const [contracts, units, customers] = await Promise.all([API.get('/api/contracts'), API.get('/api/units'), API.get('/api/customers')]);
  CACHE.contracts = contracts; CACHE.units = units; CACHE.customers = customers;
  $('#view').innerHTML = `
    <div class="section-title">合同管理 <span class="sub">租赁 / 销售合同台账</span></div>
    <div class="filters">
      <select id="fType"><option value="">全部类型</option><option value="租赁">租赁</option><option value="销售">销售</option></select>
      <select id="fStatus"><option value="">全部状态</option><option value="生效">生效</option><option value="到期">到期</option><option value="退租">退租</option><option value="已售">已售</option></select>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>合同号</th><th>类型</th><th>单元</th><th>客户</th><th>起止日期</th><th>金额</th><th>付款周期</th><th>状态</th><th>操作</th></tr></thead>
      <tbody id="contractTable"></tbody>
    </table></div>`;
  function renderList() {
    const tp = $('#fType').value, st = $('#fStatus').value;
    let list = contracts.filter(c => (!tp || c.type === tp) && (!st || c.status === st));
    $('#contractTable').innerHTML = list.map(c => `
      <tr>
        <td>${esc(c.code)}</td><td>${tag(c.type)}</td><td>${esc(uname(c.unit_id))}</td><td>${esc(cname(c.customer_id))}</td>
        <td>${esc(c.start_date || '-')} ~ ${esc(c.end_date || '-')}</td><td>${yuan(c.amount || 0)}</td><td>${esc(c.pay_cycle || '-')}</td><td>${tag(c.status)}</td>
        <td>${c.status === '生效' && can('lease_terminate') ? `<button class="btn sm red" onclick="terminateContract(${c.id})">退租</button>` : '-'}</td>
      </tr>`).join('') || '<tr><td colspan="9" class="empty">无记录</td></tr>';
  }
  $('#fType').onchange = renderList; $('#fStatus').onchange = renderList;
  renderList();
}
window.openContractModal = async function(unitId, type) {
  const u = CACHE.units.find(x => x.id == unitId);
  const customers = await API.get('/api/customers');
  CACHE.customers = customers;
  const cOpts = customers.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  openModal((type === '租赁' ? '厂房租赁' : '厂房销售') + '：' + (u ? u.code : ''), `
    <div class="form-grid">
      <div class="form-row"><label>合同号</label><input id="f_code" placeholder="HT-${type === '租赁' ? 'L' : 'S'}-..."></div>
      <div class="form-row" style="grid-column:1/3"><label>客户</label><select id="f_cust">${cOpts}</select></div>
      <div class="form-row"><label>金额</label><input id="f_amt" type="number" value="${type === '租赁' ? (u ? u.rent_price || '' : '') : (u ? u.property_price || '' : '')}"></div>
      <div class="form-row"><label>付款周期</label><select id="f_cycle">${sel(type === '租赁' ? ['月','季','年'] : ['一次性'])}</select></div>
      <div class="form-row"><label>起始日</label><input id="f_sd" type="date" value="${today()}"></div>
      <div class="form-row"><label>结束日</label><input id="f_ed" type="date" value="${type === '租赁' ? '' : today()}"></div>
      <div class="form-row"><label>押金</label><input id="f_dep" type="number" value="0"></div>
    </div>`, async () => {
    await API.post('/api/contracts', {
      code: $('#f_code').value, type, unit_id: unitId,
      customer_id: +$('#f_cust').value, amount: +$('#f_amt').value || 0, pay_cycle: $('#f_cycle').value,
      start_date: $('#f_sd').value, end_date: $('#f_ed').value, deposit: +$('#f_dep').value || 0,
      status: type === '租赁' ? '生效' : '已售', sign_date: today(), note: type,
    });
    closeModal(); toast('合同已创建'); refreshCurrent();
  });
};
window.terminateContract = async function(id) {
  if (!confirm('确认退租？')) return;
  await API.post('/api/contracts/' + id + '/terminate', { actual_end_date: today(), move_out_reason: '到期退租', deposit_action: '暂不退', deposit_amount: 0 });
  toast('已退租'); renderContracts();
};

// ---------- 收费 / 账单 ----------
async function renderBilling() {
  const [bills, units, customers] = await Promise.all([API.get('/api/bills'), API.get('/api/units'), API.get('/api/customers')]);
  CACHE.bills = bills; CACHE.units = units; CACHE.customers = customers;
  $('#view').innerHTML = `
    <div class="section-title">收费管理 <span class="sub">账单 · 收款（不含公寓）</span></div>
    <div class="filters">
      <select id="fStatus"><option value="">全部状态</option><option value="待收">待收</option><option value="已收">已收</option><option value="欠费">欠费</option></select>
      <select id="fType"><option value="">全部项目</option><option value="租金">租金</option><option value="物业">物业</option><option value="水电">水电</option><option value="房款">房款</option></select>
      <button class="btn" id="genBills">生成月度账单</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>周期</th><th>项目</th><th>单元</th><th>客户</th><th>金额</th><th>已收</th><th>状态</th><th>操作</th></tr></thead>
      <tbody id="billTable"></tbody>
    </table></div>`;
  function renderList() {
    const st = $('#fStatus').value, tp = $('#fType').value;
    let list = bills.filter(b => (!st || b.status === st) && (!tp || b.item_type === tp));
    $('#billTable').innerHTML = list.map(b => `
      <tr>
        <td>${esc(b.period)}</td><td>${esc(b.item_type)}</td><td>${esc(uname(b.unit_id))}</td><td>${esc(cname(b.customer_id))}</td>
        <td>${yuan(b.amount || 0)}</td><td>${yuan(b.paid_amount || 0)}</td><td>${tag(b.status)}</td>
        <td>${b.status !== '已收' && can('receipt_add') ? `<button class="btn sm ghost" onclick="addReceipt(${b.id})">收款</button>` : '-'}</td>
      </tr>`).join('') || '<tr><td colspan="8" class="empty">无记录</td></tr>';
  }
  $('#fStatus').onchange = renderList; $('#fType').onchange = renderList;
  $('#genBills').onclick = async () => { const r = await API.post('/api/bills/generate', { month: today().slice(0, 7) }); toast(`生成 ${r.created} 笔账单`); renderBilling(); };
  renderList();
}
window.addReceipt = function(billId) {
  openModal('登记收款', `
    <div class="form-grid"><div class="form-row"><label>收款金额</label><input id="f_amt" type="number"></div><div class="form-row"><label>收款日期</label><input id="f_date" type="date" value="${today()}"></div><div class="form-row"><label>收款方式</label><select id="f_method">${sel(['转账','现金','线上','汇票'])}</select></div><div class="form-row"><label>凭证号</label><input id="f_voucher"></div></div>`, async () => {
    await API.post('/api/bills/' + billId + '/receipt', { amount: +$('#f_amt').value || 0, date: $('#f_date').value, method: $('#f_method').value, voucher_no: $('#f_voucher').value });
    closeModal(); toast('收款已登记'); renderBilling();
  });
};

// ---------- 水电抄表 ----------
let meterRows = [];
function meterLog(action, detail) {
  const logs = JSON.parse(localStorage.getItem('park_meter_logs') || '[]');
  logs.unshift({ action, detail, who: ROLE, at: now() });
  localStorage.setItem('park_meter_logs', JSON.stringify(logs.slice(0, 50)));
}
async function renderMeter() {
  const [rows, units, customers] = await Promise.all([
    API.get('/api/meter-records'), API.get('/api/units'), API.get('/api/customers'),
  ]);
  meterRows = rows;
  CACHE.units = units; CACHE.customers = customers;
  const thisMonth = today().slice(0, 7);
  const mRows = rows.filter(r => r.bill_month === thisMonth);
  const sum = (arr, k) => arr.reduce((a, r) => a + (Number(r[k]) || 0), 0);
  const kWater = sum(mRows, 'water_fee'), kElec = sum(mRows, 'electric_fee');
  const tenants = [...new Set(rows.map(r => r.tenant_name || '未关联租户').filter(Boolean))];
  const periods = [...new Set(rows.map(r => r.bill_month).filter(Boolean))].sort().reverse();
  $('#view').innerHTML = `
    <div class="section-title">水电抄表 <span class="sub">水 / 电双表 · 按租户分组 · 费用自动核算</span></div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">抄表总笔数</div><div class="value">${rows.length}</div></div>
      <div class="kpi green"><div class="label">本月水费</div><div class="value">${yuan(kWater)}</div></div>
      <div class="kpi amber"><div class="label">本月电费</div><div class="value">${yuan(kElec)}</div></div>
      <div class="kpi purple"><div class="label">本月合计</div><div class="value">${yuan(kWater + kElec)}</div></div>
    </div>
    <div class="filters">
      <input id="mSearch" placeholder="搜索租户 / 编号 / 铺位">
      <select id="mTenant"><option value="">全部租户</option>${sel(tenants)}</select>
      <select id="mPeriod"><option value="">全部周期</option>${sel(periods)}</select>
      ${can('meter_add') ? '<button class="btn" id="mAdd">+ 新增抄表</button>' : ''}
      ${can('meter_add') ? '<button class="btn ghost" id="mImport">导入</button>' : ''}
      <button class="btn ghost" id="mExport">导出</button>
      <button class="btn ghost" id="mLog">操作记录</button>
      <button class="btn danger ghost" id="mDel">删除选中</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr>
        <th><input type="checkbox" id="mAll"></th>
        <th>抄表编号</th><th>关联铺位</th><th>关联租户</th><th>抄表日期</th><th>费用周期</th>
        <th>水·上期</th><th>水·本期</th><th>水·单价</th><th>水·费用</th>
        <th>电·上期</th><th>电·本期</th><th>电·单价</th><th>电·费用</th>
        <th>合计</th><th>操作</th>
      </tr></thead>
      <tbody id="mTable"></tbody>
    </table></div>
    <input type="file" id="mFile" accept=".csv" style="display:none">`;
  function renderList() {
    const kw = $('#mSearch').value.trim();
    const ft = $('#mTenant').value;
    const fp = $('#mPeriod').value;
    let list = meterRows.filter(r =>
      (!kw || (r.tenant_name || '').includes(kw) || (r.meter_no || '').includes(kw) || (r.unit_code || '').includes(kw)) &&
      (!ft || r.tenant_name === ft) && (!fp || r.bill_month === fp));
    const groups = {};
    list.forEach(r => { const k = r.tenant_name || '未关联租户'; if (!groups[k]) groups[k] = []; groups[k].push(r); });
    let html = '';
    Object.keys(groups).forEach(g => {
      const gRows = groups[g];
      const gW = sum(gRows, 'water_fee'), gE = sum(gRows, 'electric_fee');
      html += `<tr class="grp"><td colspan="16">🏢 ${esc(g)} <span class="grp-sum">水费 ${yuan(gW)} · 电费 ${yuan(gE)} · 合计 ${yuan(gW + gE)}</span></td></tr>`;
      html += gRows.map(r => `<tr data-id="${r.id}">
        <td><input type="checkbox" class="mchk" value="${r.id}"></td>
        <td>${esc(r.meter_no)}</td><td>${esc(r.unit_code || '-')}</td><td>${esc(r.tenant_name || '-')}</td>
        <td>${esc(r.reading_date)}</td><td>${esc(r.bill_month)}</td>
        <td>${fmt(r.water_prev)}</td><td>${fmt(r.water_curr)}</td><td>${fmt(r.water_price)}</td><td>${yuan(r.water_fee)}</td>
        <td>${fmt(r.electric_prev)}</td><td>${fmt(r.electric_curr)}</td><td>${fmt(r.electric_price)}</td><td>${yuan(r.electric_fee)}</td>
        <td>${yuan(r.total_fee)}</td>
        <td>${can('meter_add') ? `<button class="btn sm ghost" onclick="editMeter(${r.id})">编辑</button> ` : ''}<button class="btn sm ghost" onclick="delMeter(${r.id})">删除</button></td>
      </tr>`).join('');
    });
    $('#mTable').innerHTML = html || '<tr><td colspan="16" class="empty">无记录</td></tr>';
    $('#mAll').onchange = () => { $$('.mchk').forEach(c => c.checked = $('#mAll').checked); };
  }
  $('#mSearch').oninput = renderList;
  $('#mTenant').onchange = renderList;
  $('#mPeriod').onchange = renderList;
  if (can('meter_add')) {
    $('#mAdd').onclick = () => openMeterModal(null);
    $('#mImport').onclick = () => $('#mFile').click();
  }
  $('#mExport').onclick = exportMeterCSV;
  $('#mLog').onclick = showMeterLog;
  $('#mDel').onclick = deleteSelectedMeters;
  $('#mFile').onchange = (e) => importMeterCSV(e.target.files[0]);
  renderList();
}
window.openMeterModal = function (rec) {
  rec = rec || {};
  const isEdit = !!(rec && rec.id);
  const unitMap = {}; (CACHE.units || []).forEach(u => unitMap[u.id] = u);
  const custMap = {}; (CACHE.customers || []).forEach(c => custMap[c.id] = c);
  const unitOpts = (CACHE.units || []).map(u => `<option value="${u.id}" ${u.id == rec.unit_id ? 'selected' : ''}>${esc(u.code)}</option>`).join('');
  const body = `
    <div class="form-grid">
      <div class="form-row"><label>抄表编号</label><input id="mm_no" value="${esc(rec.meter_no || '')}" placeholder="留空自动生成"></div>
      <div class="form-row"><label>关联铺位</label><select id="mm_unit">${unitOpts}</select></div>
      <div class="form-row"><label>关联租户</label><input id="mm_tenant" value="${esc(rec.tenant_name || '')}" placeholder="选铺位自动带出"></div>
      <div class="form-row"><label>抄表日期</label><input id="mm_date" type="date" value="${esc(rec.reading_date || today())}"></div>
      <div class="form-row"><label>费用周期</label><input id="mm_month" value="${esc(rec.bill_month || today().slice(0, 7))}" placeholder="YYYY-MM"></div>
      <div class="form-row"><label>水·上期读数(吨)</label><input id="mm_wp" type="number" step="0.01" value="${rec.water_prev == null ? '' : rec.water_prev}"></div>
      <div class="form-row"><label>水·本期读数(吨)</label><input id="mm_wc" type="number" step="0.01" value="${rec.water_curr == null ? '' : rec.water_curr}"></div>
      <div class="form-row"><label>水·单价(元/吨)</label><input id="mm_wpr" type="number" step="0.01" value="${rec.water_price == null ? 3 : rec.water_price}"></div>
      <div class="form-row"><label>电·上期读数(度)</label><input id="mm_ep" type="number" step="0.01" value="${rec.electric_prev == null ? '' : rec.electric_prev}"></div>
      <div class="form-row"><label>电·本期读数(度)</label><input id="mm_ec" type="number" step="0.01" value="${rec.electric_curr == null ? '' : rec.electric_curr}"></div>
      <div class="form-row"><label>电·单价(元/度)</label><input id="mm_epr" type="number" step="0.01" value="${rec.electric_price == null ? 1.5 : rec.electric_price}"></div>
    </div>
    <div class="meter-preview" id="mm_preview"></div>`;
  openModal(isEdit ? '编辑抄表记录' : '新增抄表记录', body, async () => {
    const payload = {
      meter_no: $('#mm_no').value.trim(),
      unit_id: parseInt($('#mm_unit').value) || null,
      tenant_name: $('#mm_tenant').value.trim(),
      reading_date: $('#mm_date').value,
      bill_month: $('#mm_month').value || $('#mm_date').value.slice(0, 7),
      water_prev: $('#mm_wp').value, water_curr: $('#mm_wc').value, water_price: $('#mm_wpr').value,
      electric_prev: $('#mm_ep').value, electric_curr: $('#mm_ec').value, electric_price: $('#mm_epr').value,
    };
    if (isEdit) await API.put('/api/meter-records/' + rec.id, payload);
    else await API.post('/api/meter-records', payload);
    meterLog(isEdit ? '编辑' : '新增', (payload.tenant_name || '') + ' ' + payload.bill_month);
    closeModal(); toast(isEdit ? '已保存' : '已新增'); renderMeter();
  });
  const calc = () => {
    const wp = +$('#mm_wp').value || 0, wc = +$('#mm_wc').value || 0, wpr = +$('#mm_wpr').value || 0;
    const ep = +$('#mm_ep').value || 0, ec = +$('#mm_ec').value || 0, epr = +$('#mm_epr').value || 0;
    const wf = Math.max(0, wc - wp) * wpr, ef = Math.max(0, ec - ep) * epr;
    $('#mm_preview').innerHTML = `水费 <b>${yuan(Math.round(wf * 100) / 100)}</b> ｜ 电费 <b>${yuan(Math.round(ef * 100) / 100)}</b> ｜ 合计 <b>${yuan(Math.round((wf + ef) * 100) / 100)}</b>`;
  };
  $('#mm_unit').onchange = () => {
    const u = unitMap[$('#mm_unit').value];
    if (u && u.current_customer_id && custMap[u.current_customer_id]) $('#mm_tenant').value = custMap[u.current_customer_id].name;
  };
  $('#mm_date').onchange = () => { const d = $('#mm_date').value; if (d) $('#mm_month').value = d.slice(0, 7); };
  ['mm_wp', 'mm_wc', 'mm_wpr', 'mm_ep', 'mm_ec', 'mm_epr'].forEach(id => $('#' + id).oninput = calc);
  calc();
};
window.editMeter = function (id) { const r = meterRows.find(x => x.id == id); if (r) openMeterModal(r); };
window.delMeter = async function (id) {
  if (!confirm('确定删除该抄表记录？')) return;
  const no = (meterRows.find(x => x.id == id) || {}).meter_no || '';
  await API.delete('/api/meter-records/' + id);
  meterLog('删除', '编号 ' + no); toast('已删除'); renderMeter();
};
window.deleteSelectedMeters = async function () {
  const ids = $$('.mchk:checked').map(c => +c.value);
  if (!ids.length) { toast('请先勾选记录'); return; }
  if (!confirm('确定删除选中的 ' + ids.length + ' 条记录？')) return;
  for (const id of ids) await API.delete('/api/meter-records/' + id);
  meterLog('删除', ids.length + ' 条'); toast('已删除 ' + ids.length + ' 条'); renderMeter();
};
window.exportMeterCSV = function () {
  const header = ['抄表编号', '关联铺位', '关联租户', '抄表日期', '费用周期', '水上期', '水本期', '水单价', '水费用', '电上期', '电本期', '电单价', '电费用', '合计'];
  const lines = meterRows.map(r => [r.meter_no, r.unit_code, r.tenant_name, r.reading_date, r.bill_month, r.water_prev, r.water_curr, r.water_price, r.water_fee, r.electric_prev, r.electric_curr, r.electric_price, r.electric_fee, r.total_fee]);
  const csv = [header.join(',')].concat(lines.map(r => r.map(v => v == null ? '' : v).join(','))).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = '水电抄表台账.csv'; a.click();
  meterLog('导出', meterRows.length + ' 条');
};
window.importMeterCSV = async function (file) {
  if (!file) return;
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) { toast('文件无数据'); return; }
  const header = lines[0].split(',').map(h => h.trim());
  const unitByCode = {}; (CACHE.units || []).forEach(u => unitByCode[u.code] = u);
  let ok = 0;
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(',');
    const o = {}; header.forEach((h, j) => o[h] = vals[j]);
    const code = (o['关联铺位'] || '').trim();
    const u = unitByCode[code];
    const payload = {
      meter_no: (o['抄表编号'] || '').trim(), unit_id: u ? u.id : null, unit_code: code,
      tenant_name: (o['关联租户'] || '').trim(), reading_date: (o['抄表日期'] || today()).trim(),
      bill_month: (o['费用周期'] || (o['抄表日期'] || today()).slice(0, 7)).trim(),
      water_prev: o['水上期'], water_curr: o['水本期'], water_price: o['水单价'],
      electric_prev: o['电上期'], electric_curr: o['电本期'], electric_price: o['电单价'],
    };
    await API.post('/api/meter-records', payload); ok++;
  }
  meterLog('导入', ok + ' 条'); toast('已导入 ' + ok + ' 条'); renderMeter();
};
window.showMeterLog = function () {
  const logs = JSON.parse(localStorage.getItem('park_meter_logs') || '[]');
  const html = logs.length ? logs.map(l => `<div class="log-item"><span class="log-act">${esc(l.action)}</span> ${esc(l.detail)} <span class="log-meta">${esc(l.who)} · ${esc(l.at)}</span></div>`).join('') : '<div class="empty">暂无操作记录</div>';
  openModal('操作记录', `<div class="log-list">${html}</div>`, null);
};

// ---------- 商户管理（租户信息 / 租赁周期 / 租金方式 / 分成收入 / 收电费）----------
const MERCHANT_CATS = ['餐饮', '零售', '办公', '制造', '服务', '仓储物流', '其他'];
const PAY_CYCLES = ['月付', '季付', '半年付', '年付'];
const RENT_TYPES = ['固定租金', '保底+分成', '纯分成'];
const MERCHANT_STATUS = ['在租', '意向', '退租'];

// 本期应计租金/分成（元）
function merchantRent(m) {
  const rev = Number(m.monthly_revenue) || 0;
  const ratio = Number(m.split_ratio) || 0;
  const fixed = Number(m.fixed_rent) || 0;
  const base = Number(m.base_amount) || 0;
  if (m.rent_type === '纯分成') return rev * ratio / 100;
  if (m.rent_type === '保底+分成') return Math.max(base, rev * ratio / 100);
  return fixed;
}
function merchantElecDue(m) { return (Number(m.electric_usage) || 0) * (Number(m.electric_price) || 0); }
function merchantElecArrears(m) { return merchantElecDue(m) - (Number(m.electric_paid) || 0); }
function leaseMonthsOf(m) {
  if (!m.start_date || !m.end_date) return '-';
  const a = new Date(m.start_date), b = new Date(m.end_date);
  const ms = b - a;
  if (isNaN(ms) || ms < 0) return '-';
  return Math.round(ms / 86400000 / 30);
}

async function renderMerchants() {
  const merchants = await API.get('/api/merchants');
  CACHE.merchants = merchants;
  let fStatus = '', fCat = '', fKw = '';
  const renting = merchants.filter(m => m.status === '在租');
  const rentSum = renting.reduce((s, m) => s + merchantRent(m), 0);
  const elecArrears = renting.reduce((s, m) => s + Math.max(0, merchantElecArrears(m)), 0);
  $('#view').innerHTML = `
    <div class="section-title">商户管理 <span class="sub">租户信息 · 租赁周期 · 租金方式 · 分成收入 · 收电费</span></div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">商户总数</div><div class="value">${merchants.length}</div></div>
      <div class="kpi"><div class="label">在租商户</div><div class="value">${renting.length}</div></div>
      <div class="kpi green"><div class="label">本月应收（租金+分成）</div><div class="value">${yuan(rentSum)}</div></div>
      <div class="kpi amber"><div class="label">电费欠缴合计</div><div class="value">${yuan(elecArrears)}</div></div>
    </div>
    <div class="filters">
      <select id="mStatus"><option value="">全部状态</option>${MERCHANT_STATUS.map(s => `<option value="${s}">${s}</option>`).join('')}</select>
      <select id="mCat"><option value="">全部业态</option>${MERCHANT_CATS.map(s => `<option value="${s}">${s}</option>`).join('')}</select>
      <input id="mKw" placeholder="搜索编号/名称/联系人/电话">
      ${can('merchants_add') ? '<button class="btn" id="addMerchant">+ 新增商户</button>' : ''}
    </div>
    <div class="table-wrap"><table>
      <thead><tr>
        <th>编号</th><th>名称</th><th>业态</th><th>关联资产</th><th>联系人/电话</th>
        <th>租赁周期</th><th>缴费</th><th>租金方式</th><th>本期应收</th><th>电费欠缴</th><th>状态</th><th>操作</th>
      </tr></thead>
      <tbody id="merchantTable"></tbody>
    </table></div>`;
  function renderList() {
    const kw = $('#mKw').value.toLowerCase();
    const list = merchants.filter(m => {
      if (fStatus && m.status !== fStatus) return false;
      if (fCat && m.category !== fCat) return false;
      if (kw && !`${m.code} ${m.name} ${m.contact} ${m.phone}`.toLowerCase().includes(kw)) return false;
      return true;
    });
    $('#merchantTable').innerHTML = list.map(m => `
      <tr>
        <td>${esc(m.code || '-')}</td>
        <td><b>${esc(m.name)}</b></td>
        <td>${tag(m.category || '-')}</td>
        <td>${m.unit_id ? esc(uname(m.unit_id)) : '-'}</td>
        <td>${esc(m.contact || '-')}<br><span class="mut">${esc(m.phone || '-')}</span></td>
        <td>${esc(m.start_date || '-')} ~ ${esc(m.end_date || '-')}<br><span class="mut">${leaseMonthsOf(m)} 个月</span></td>
        <td>${esc(m.pay_cycle || '-')}</td>
        <td>${tag(m.rent_type || '-')}</td>
        <td>${yuan(merchantRent(m))}</td>
        <td>${merchantElecArrears(m) > 0 ? `<span style="color:#e0531f">${yuan(merchantElecArrears(m))}</span>` : yuan(0)}</td>
        <td>${tag(m.status || '-')}</td>
        <td>
          <button class="btn sm ghost" onclick="openMerchantDetail(${m.id})">详情</button>
          ${can('merchants_edit') ? `<button class="btn sm ghost" onclick="openMerchantModal(${m.id})">编辑</button>` : ''}
          ${can('merchants_delete') ? `<button class="btn sm danger" onclick="deleteMerchant(${m.id})">删除</button>` : ''}
        </td>
      </tr>`).join('') || '<tr><td colspan="12" class="empty">无记录</td></tr>';
  }
  $('#mStatus').onchange = () => { fStatus = $('#mStatus').value; renderList(); };
  $('#mCat').onchange = () => { fCat = $('#mCat').value; renderList(); };
  $('#mKw').oninput = renderList;
  renderList();
  if (can('merchants_add')) $('#addMerchant').onclick = () => openMerchantModal();
}

window.openMerchantModal = function(id) {
  const isEdit = !!id;
  const m = isEdit ? (CACHE.merchants || []).find(x => x.id == id) : {};
  const custOpts = (CACHE.customers || []).map(c => `<option value="${c.id}" ${String(m.customer_id) === String(c.id) ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  const unitOpts = (CACHE.units || []).map(u => `<option value="${u.id}" ${String(m.unit_id) === String(u.id) ? 'selected' : ''}>${esc(u.code)}</option>`).join('');
  const split = (t) => `<div style="grid-column:1/3;font-weight:600;color:var(--accent);margin:10px 0 2px;font-size:13px">${t}</div>`;
  openModal(isEdit ? '编辑商户' : '新增商户', `
    <div class="form-grid">
      <div class="form-row"><label>商户编号</label><input id="f_code" value="${esc(m.code || '')}" placeholder="如 M001"></div>
      <div class="form-row"><label>商户名称</label><input id="f_name" value="${esc(m.name || '')}"></div>
      <div class="form-row"><label>关联客户</label><select id="f_customer_id"><option value="">未关联</option>${custOpts}</select></div>
      <div class="form-row"><label>关联资产单元</label><select id="f_unit_id"><option value="">未关联</option>${unitOpts}</select></div>
      <div class="form-row"><label>经营业态</label><select id="f_category">${sel(MERCHANT_CATS, m.category)}</select></div>
      <div class="form-row"><label>状态</label><select id="f_status">${sel(MERCHANT_STATUS, m.status || '在租')}</select></div>
      <div class="form-row"><label>联系人</label><input id="f_contact" value="${esc(m.contact || '')}"></div>
      <div class="form-row"><label>电话</label><input id="f_phone" value="${esc(m.phone || '')}"></div>
      <div class="form-row"><label>入场日期</label><input id="f_enter_date" type="date" value="${esc(m.enter_date || '')}"></div>
      <div class="form-row"><label></label><span class="mut"></span></div>
      ${split('租赁周期')}
      <div class="form-row"><label>起租日</label><input id="f_start_date" type="date" value="${esc(m.start_date || '')}"></div>
      <div class="form-row"><label>到期日</label><input id="f_end_date" type="date" value="${esc(m.end_date || '')}"></div>
      <div class="form-row"><label>缴费周期</label><select id="f_pay_cycle">${sel(PAY_CYCLES, m.pay_cycle || '月付')}</select></div>
      <div class="form-row"><label></label><span class="mut"></span></div>
      ${split('租金方式')}
      <div class="form-row"><label>租金方式</label><select id="f_rent_type">${sel(RENT_TYPES, m.rent_type || '固定租金')}</select></div>
      <div class="form-row"><label>月固定租金</label><input id="f_fixed_rent" type="number" value="${m.fixed_rent || ''}"></div>
      <div class="form-row"><label>保底额</label><input id="f_base_amount" type="number" value="${m.base_amount || ''}"></div>
      <div class="form-row"><label>分成比例%</label><input id="f_split_ratio" type="number" value="${m.split_ratio || ''}"></div>
      <div class="form-row"><label>物业费/月</label><input id="f_property_fee" type="number" value="${m.property_fee || ''}"></div>
      <div class="form-row"><label>本月营业额</label><input id="f_monthly_revenue" type="number" value="${m.monthly_revenue || ''}"></div>
      <div class="form-row"><label></label><span class="mut"></span></div>
      ${split('收电费')}
      <div class="form-row"><label>电表号</label><input id="f_electric_meter_no" value="${esc(m.electric_meter_no || '')}"></div>
      <div class="form-row"><label>电价(元/度)</label><input id="f_electric_price" type="number" step="0.01" value="${m.electric_price || ''}"></div>
      <div class="form-row"><label>本月用电量(度)</label><input id="f_electric_usage" type="number" value="${m.electric_usage || ''}"></div>
      <div class="form-row"><label>已缴电费</label><input id="f_electric_paid" type="number" value="${m.electric_paid || ''}"></div>
      <div class="form-row" style="grid-column:1/3"><label>备注</label><input id="f_note" value="${esc(m.note || '')}"></div>
    </div>`, async () => {
    const body = {
      code: $('#f_code').value.trim(),
      name: $('#f_name').value.trim(),
      customer_id: $('#f_customer_id').value ? +$('#f_customer_id').value : null,
      unit_id: $('#f_unit_id').value ? +$('#f_unit_id').value : null,
      category: $('#f_category').value,
      status: $('#f_status').value,
      contact: $('#f_contact').value.trim(),
      phone: $('#f_phone').value.trim(),
      enter_date: $('#f_enter_date').value || null,
      start_date: $('#f_start_date').value || null,
      end_date: $('#f_end_date').value || null,
      pay_cycle: $('#f_pay_cycle').value,
      rent_type: $('#f_rent_type').value,
      fixed_rent: +$('#f_fixed_rent').value || 0,
      base_amount: +$('#f_base_amount').value || 0,
      split_ratio: +$('#f_split_ratio').value || 0,
      property_fee: +$('#f_property_fee').value || 0,
      monthly_revenue: +$('#f_monthly_revenue').value || 0,
      electric_meter_no: $('#f_electric_meter_no').value.trim(),
      electric_price: +$('#f_electric_price').value || 0,
      electric_usage: +$('#f_electric_usage').value || 0,
      electric_paid: +$('#f_electric_paid').value || 0,
      note: $('#f_note').value.trim(),
    };
    if (isEdit) await API.put('/api/merchants/' + id, body);
    else await API.post('/api/merchants', body);
    closeModal(); toast(isEdit ? '商户已更新' : '商户已添加'); renderMerchants();
  });
};

window.openMerchantDetail = function(id) {
  const m = (CACHE.merchants || []).find(x => x.id == id);
  if (!m) return;
  const rent = merchantRent(m);
  const due = merchantElecDue(m);
  const arrears = merchantElecArrears(m);
  openModal('商户详情：' + m.name, `
    <div class="crm-detail">
      <div class="kv"><span>商户编号</span><b>${esc(m.code || '-')}</b></div>
      <div class="kv"><span>状态</span><b>${tag(m.status || '-')}</b></div>
      <div class="kv"><span>经营业态</span><b>${esc(m.category || '-')}</b></div>
      <div class="kv"><span>关联客户</span><b>${m.customer_id ? esc(cname(m.customer_id)) : '-'}</b></div>
      <div class="kv"><span>关联资产</span><b>${m.unit_id ? esc(uname(m.unit_id)) : '-'}</b></div>
      <div class="kv"><span>联系人</span><b>${esc(m.contact || '-')}</b></div>
      <div class="kv"><span>电话</span><b>${esc(m.phone || '-')}</b></div>
      <div class="kv"><span>入场日期</span><b>${esc(m.enter_date || '-')}</b></div>
    </div>
    <div style="border-top:1px solid var(--line);margin:14px 0 10px;padding-top:10px"><b>租赁周期</b></div>
    <div class="crm-detail">
      <div class="kv"><span>起租日</span><b>${esc(m.start_date || '-')}</b></div>
      <div class="kv"><span>到期日</span><b>${esc(m.end_date || '-')}</b></div>
      <div class="kv"><span>租期(约)</span><b>${leaseMonthsOf(m)} 个月</b></div>
      <div class="kv"><span>缴费周期</span><b>${esc(m.pay_cycle || '-')}</b></div>
    </div>
    <div style="border-top:1px solid var(--line);margin:14px 0 10px;padding-top:10px"><b>租金方式 / 分成收入</b></div>
    <div class="crm-detail">
      <div class="kv"><span>租金方式</span><b>${tag(m.rent_type || '-')}</b></div>
      <div class="kv"><span>月固定租金</span><b>${yuan(m.fixed_rent || 0)}</b></div>
      <div class="kv"><span>保底额</span><b>${yuan(m.base_amount || 0)}</b></div>
      <div class="kv"><span>分成比例</span><b>${m.split_ratio || 0}%</b></div>
      <div class="kv"><span>本月营业额</span><b>${yuan(m.monthly_revenue || 0)}</b></div>
      <div class="kv"><span>物业费/月</span><b>${yuan(m.property_fee || 0)}</b></div>
      <div class="kv"><span>本期应收(租金+分成)</span><b style="color:#0a7d3b">${yuan(rent)}</b></div>
    </div>
    <div style="border-top:1px solid var(--line);margin:14px 0 10px;padding-top:10px"><b>收电费</b></div>
    <div class="crm-detail">
      <div class="kv"><span>电表号</span><b>${esc(m.electric_meter_no || '-')}</b></div>
      <div class="kv"><span>电价</span><b>${yuan(m.electric_price || 0)}/度</b></div>
      <div class="kv"><span>本月用电量</span><b>${fmt(m.electric_usage || 0)} 度</b></div>
      <div class="kv"><span>应缴电费</span><b>${yuan(due)}</b></div>
      <div class="kv"><span>已缴电费</span><b>${yuan(m.electric_paid || 0)}</b></div>
      <div class="kv"><span>电费欠缴</span><b style="color:${arrears > 0 ? '#e0531f' : '#0a7d3b'}">${yuan(arrears)}</b></div>
    </div>
    ${m.note ? `<div style="border-top:1px solid var(--line);margin:14px 0 10px;padding-top:10px"><b>备注</b><div class="mut" style="margin-top:6px">${esc(m.note)}</div></div>` : ''}
  `, null);
};

window.deleteMerchant = async function(id) {
  if (!confirm('确认删除该商户记录？此操作不可撤销。')) return;
  await API.delete('/api/merchants/' + id);
  toast('已删除'); renderMerchants();
};

// ---------- 押金 ----------
async function renderDeposits() {
  const [deposits, contracts] = await Promise.all([API.get('/api/deposits'), API.get('/api/contracts')]);
  CACHE.contracts = contracts;
  const received = deposits.filter(d => d.type === '收').reduce((a, b) => a + (b.amount || 0), 0);
  const refunded = deposits.filter(d => d.type === '退').reduce((a, b) => a + (b.amount || 0), 0);
  const offset = deposits.filter(d => d.type === '抵扣').reduce((a, b) => a + (b.amount || 0), 0);
  const held = received - refunded - offset;
  $('#view').innerHTML = `
    <div class="section-title">押金管理 <span class="sub">厂房 + 公寓押金统一登记</span></div>
    <div class="grid kpi-grid">
      <div class="kpi blue"><div class="label">总笔数</div><div class="value">${deposits.length}</div></div>
      <div class="kpi green"><div class="label">已收押金</div><div class="value">${yuan(received)}</div></div>
      <div class="kpi red"><div class="label">已退押金</div><div class="value">${yuan(refunded)}</div></div>
      <div class="kpi amber"><div class="label">抵扣押金</div><div class="value">${yuan(offset)}</div></div>
      <div class="kpi purple"><div class="label">在押余额</div><div class="value">${yuan(held)}</div></div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>房间号</th><th>合同</th><th>客户</th><th>类型</th><th>金额</th><th>日期</th><th>备注</th></tr></thead>
      <tbody id="depTable"></tbody>
    </table></div>`;
  $('#depTable').innerHTML = deposits.map(d => `
    <tr><td>${esc(d.unit_code || uname(d.unit_id))}</td><td>${esc(ccode(d.contract_id))}</td><td>${esc(cname(d.customer_id))}</td><td>${tag(d.type)}</td><td>${yuan(d.amount)}</td><td>${esc(d.date || '-')}</td><td>${esc(d.note || '-')}</td></tr>`
  ).join('') || '<tr><td colspan="7" class="empty">无记录</td></tr>';
}

// ---------- 工单 ----------
async function renderWorkOrders() {
  const rows = await API.get('/api/work-orders');
  $('#view').innerHTML = `
    <div class="section-title">工单管理 <span class="sub">报修 / 巡检 / 派工</span></div>
    <div class="filters">
      <select id="fStatus"><option value="">全部状态</option><option value="待派">待派</option><option value="处理中">处理中</option><option value="已完成">已完成</option></select>
      ${can('workorder_add') ? '<button class="btn" id="addWo">+ 新增工单</button>' : ''}
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>工单号</th><th>类型</th><th>报修人</th><th>描述</th><th>处理人</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
      <tbody id="woTable"></tbody>
    </table></div>`;
  function renderList() {
    const st = $('#fStatus').value;
    let list = rows.filter(r => !st || r.status === st);
    $('#woTable').innerHTML = list.map(r => `
      <tr>
        <td>${esc(r.code)}</td><td>${esc(r.type)}</td><td>${esc(r.reporter)}</td><td>${esc(r.description)}</td><td>${esc(r.assignee || '-')}</td><td>${tag(r.status)}</td><td>${esc(r.created_at)}</td>
        <td>${can('workorder_edit') && r.status !== '已完成' ? `<button class="btn sm ghost" onclick="assignWorkOrder(${r.id})">派工</button>` : '-'}</td>
      </tr>`).join('') || '<tr><td colspan="8" class="empty">无记录</td></tr>';
  }
  $('#fStatus').onchange = renderList;
  renderList();
  if (can('workorder_add')) $('#addWo').onclick = () => openWorkOrderModal();
}
window.openWorkOrderModal = function(r = {}) {
  const isEdit = !!r.id;
  openModal(isEdit ? '派工' : '新增工单', `
    <div class="form-grid">
      <div class="form-row"><label>工单号</label><input id="f_code" value="${esc(r.code || '')}"></div>
      <div class="form-row"><label>类型</label><select id="f_type">${sel(['报修','巡检','投诉','其他'], r.type)}</select></div>
      <div class="form-row"><label>报修人</label><input id="f_reporter" value="${esc(r.reporter || '')}"></div>
      <div class="form-row"><label>处理人</label><input id="f_assignee" value="${esc(r.assignee || '')}"></div>
      <div class="form-row" style="grid-column:1/3"><label>描述</label><input id="f_desc" value="${esc(r.description || '')}"></div>
      <div class="form-row"><label>状态</label><select id="f_status">${sel(['待派','处理中','已完成'], r.status || '待派')}</select></div>
    </div>`, async () => {
    const body = { code: $('#f_code').value, type: $('#f_type').value, reporter: $('#f_reporter').value, assignee: $('#f_assignee').value, description: $('#f_desc').value, status: $('#f_status').value };
    if (isEdit) await API.put('/api/work-orders/' + r.id, body);
    else await API.post('/api/work-orders', body);
    closeModal(); toast(isEdit ? '已更新' : '已新增'); renderWorkOrders();
  });
};
window.assignWorkOrder = function(id) { const r = { id }; openWorkOrderModal(r); };

// ---------- 系统管理 ----------
async function renderSystem() {
  const tabs = { users: renderSysUsers, depts: renderSysDepts, roles: renderSysRoles, perms: renderSysPerms, menus: renderSysMenus, rules: renderSysRules, dict: renderSysDict, audit: renderSysAudit };
  $('#view').innerHTML = `<div class="section-title">系统管理</div><div id="sysView"></div>`;
  (tabs[SYS_TAB] || renderSysUsers)();
}
async function renderSysUsers() {
  const rows = await API.get('/api/users');
  const depts = await API.get('/api/departments');
  const roles = await API.get('/api/sys_roles');
  $('#sysView').innerHTML = `
    <div class="btn-row"><button class="btn" id="addU">+ 新增人员</button></div>
    <div class="table-wrap"><table>
      <thead><tr><th>用户名</th><th>姓名</th><th>部门</th><th>角色</th><th>电话</th><th>状态</th><th>操作</th></tr></thead>
      <tbody id="uTable"></tbody>
    </table></div>`;
  $('#uTable').innerHTML = rows.map(u => `
    <tr><td>${esc(u.username)}</td><td>${esc(u.name)}</td><td>${esc(u.department_name || '-')}</td><td>${esc(u.role_name || u.role || '-')}</td><td>${esc(u.phone || '-')}</td><td>${tag(u.status)}</td>
    <td><button class="btn sm ghost" onclick="editUser(${u.id})">编辑</button></td></tr>`).join('') || '<tr><td colspan="7" class="empty">无记录</td></tr>';
  $('#addU').onclick = () => openUserModal();
}
window.openUserModal = function(u = {}) {
  const isEdit = !!u.id;
  openModal(isEdit ? '编辑人员' : '新增人员', `
    <div class="form-grid"><div class="form-row"><label>用户名</label><input id="f_username" value="${esc(u.username || '')}"></div><div class="form-row"><label>姓名</label><input id="f_name" value="${esc(u.name || '')}"></div><div class="form-row"><label>电话</label><input id="f_phone" value="${esc(u.phone || '')}"></div><div class="form-row"><label>邮箱</label><input id="f_email" value="${esc(u.email || '')}"></div><div class="form-row"><label>密码</label><input id="f_password" type="password" placeholder="${isEdit ? '留空不修改' : ''}"></div><div class="form-row"><label>角色</label><input id="f_role" value="${esc(u.role || '')}"></div></div>`, async () => {
    const body = { username: $('#f_username').value, name: $('#f_name').value, phone: $('#f_phone').value, email: $('#f_email').value, role: $('#f_role').value };
    if ($('#f_password').value) body.password = $('#f_password').value;
    if (isEdit) await API.put('/api/users/' + u.id, body);
    else await API.post('/api/users', body);
    closeModal(); toast('已保存'); renderSysUsers();
  });
};
window.editUser = function(id) { API.get('/api/users').then(rows => { const u = rows.find(x => x.id == id); openUserModal(u); }); };

async function renderSysDepts() {
  const rows = await API.get('/api/departments');
  $('#sysView').innerHTML = `<div class="btn-row"><button class="btn" id="addD">+ 新增部门</button></div><div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>负责人</th><th>排序</th></tr></thead><tbody id="dTable"></tbody></table></div>`;
  $('#dTable').innerHTML = rows.map(d => `<tr><td>${esc(d.code)}</td><td>${esc(d.name)}</td><td>${esc(d.manager || '-')}</td><td>${d.sort || 0}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">无记录</td></tr>';
  $('#addD').onclick = () => openDeptModal();
}
window.openDeptModal = function(d = {}) {
  const isEdit = !!d.id;
  openModal(isEdit ? '编辑部门' : '新增部门', `<div class="form-grid"><div class="form-row"><label>编码</label><input id="f_code" value="${esc(d.code || '')}"></div><div class="form-row"><label>名称</label><input id="f_name" value="${esc(d.name || '')}"></div><div class="form-row"><label>负责人</label><input id="f_manager" value="${esc(d.manager || '')}"></div><div class="form-row"><label>排序</label><input id="f_sort" type="number" value="${d.sort || 0}"></div></div>`, async () => {
    const body = { code: $('#f_code').value, name: $('#f_name').value, manager: $('#f_manager').value, sort: +$('#f_sort').value || 0 };
    if (isEdit) await API.put('/api/departments/' + d.id, body); else await API.post('/api/departments', body);
    closeModal(); toast('已保存'); renderSysDepts();
  });
};

async function renderSysRoles() {
  const rows = await API.get('/api/sys_roles');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>描述</th><th>排序</th></tr></thead><tbody id="rTable"></tbody></table></div>`;
  $('#rTable').innerHTML = rows.map(r => `<tr><td>${esc(r.code)}</td><td>${esc(r.name)}</td><td>${esc(r.description || '-')}</td><td>${r.sort || 0}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">无记录</td></tr>';
}
async function renderSysPerms() {
  const rows = await API.get('/api/role_permissions');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>角色ID</th><th>资源</th><th>动作</th><th>允许</th></tr></thead><tbody id="pTable"></tbody></table></div>`;
  $('#pTable').innerHTML = rows.map(p => `<tr><td>${p.role_id}</td><td>${esc(p.resource)}</td><td>${esc(p.action)}</td><td>${p.allowed ? '是' : '否'}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">无记录</td></tr>';
}
async function renderSysMenus() {
  const rows = await API.get('/api/sys_menus');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>图标</th><th>父级</th><th>排序</th><th>可见</th></tr></thead><tbody id="mTable"></tbody></table></div>`;
  $('#mTable').innerHTML = rows.map(m => `<tr><td>${esc(m.code)}</td><td>${esc(m.name)}</td><td>${esc(m.icon || '-')}</td><td>${m.parent_id || '-'}</td><td>${m.sort || 0}</td><td>${m.visible ? '是' : '否'}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">无记录</td></tr>';
}
async function renderSysRules() {
  const rows = await API.get('/api/system_rules');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>值</th><th>说明</th></tr></thead><tbody id="ruleTable"></tbody></table></div>`;
  $('#ruleTable').innerHTML = rows.map(r => `<tr><td>${esc(r.code)}</td><td>${esc(r.name)}</td><td>${esc(r.value || '-')}</td><td>${esc(r.description || '-')}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">无记录</td></tr>';
}
async function renderSysDict() {
  const rows = await API.get('/api/data_dict');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>类型</th><th>编码</th><th>名称</th><th>排序</th><th>启用</th></tr></thead><tbody id="dictTable"></tbody></table></div>`;
  $('#dictTable').innerHTML = rows.map(d => `<tr><td>${esc(d.type)}</td><td>${esc(d.code)}</td><td>${esc(d.name)}</td><td>${d.sort || 0}</td><td>${d.enabled ? '是' : '否'}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">无记录</td></tr>';
}
async function renderSysAudit() {
  const rows = await API.get('/api/audit_logs');
  $('#sysView').innerHTML = `<div class="table-wrap"><table><thead><tr><th>时间</th><th>用户</th><th>动作</th><th>模块</th><th>详情</th></tr></thead><tbody id="auditTable"></tbody></table></div>`;
  $('#auditTable').innerHTML = rows.map(a => `<tr><td>${esc(a.created_at)}</td><td>${esc(a.user)}</td><td>${esc(a.action)}</td><td>${esc(a.module)}</td><td class="wrap">${esc(a.detail || '-')}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">无记录</td></tr>';
}

// ---------- 启动 ----------
document.addEventListener('DOMContentLoaded', () => {
  // 先绑定全局导航/弹窗事件，确保任何后续步骤出错都不会让整页不可交互
  $$('.nav-item').forEach(b => b.onclick = () => setView(b.dataset.view));
  $$('.bnav-item').forEach(b => b.onclick = () => setView(b.dataset.view));
  $$('.nav-sub-item').forEach(b => b.onclick = (e) => { e.stopPropagation(); SYS_TAB = b.dataset.sysTab; setView('system'); });
  $$('.nav-group-head').forEach(h => h.onclick = () => h.closest('.nav-group').classList.toggle('open'));
  $('#modalClose').onclick = closeModal;
  // 角色下拉
  const roleSel = $('#roleSel');
  ROLES.forEach(r => { const o = document.createElement('option'); o.value = r; o.textContent = r; roleSel.appendChild(o); });
  roleSel.value = ROLE;
  roleSel.onchange = () => { ROLE = roleSel.value; setView(CURRENT_VIEW); };
  setView('dashboard');
});
