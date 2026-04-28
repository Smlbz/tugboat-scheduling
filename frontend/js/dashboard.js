/**
 * CMATSS 拖轮调度系统 - 看板模块
 * KPI 卡片、看板数据、潮汐、拖轮监控
 */

async function loadDashboard() {
    try {
        const resp = await fetch(`${API_BASE}/api/dashboard`);
        const data = await resp.json();
        renderDashboard(data);
        renderDashboardCharts(data);
        renderFatigueSummary(data);
        renderPortStatus();
        renderPadTugs();
    } catch (e) { console.warn('看板加载失败:', e); }
    loadTideInfo();
}

function renderDashboard(d) {
    setText('kpi-jobs', d.total_jobs ?? '--');
    setText('kpi-available', d.available_tugs ?? '--');
    setText('kpi-busy', d.status_distribution?.BUSY ?? 0);
    setText('kpi-locked', d.fatigue_distribution?.RED ?? 0);
    setText('plan-total-jobs', d.total_jobs ?? '--');
    setText('plan-available-tugs', d.available_tugs ?? '--');
    const redCount = d.fatigue_distribution?.RED ?? 0;
    const alertBar = document.getElementById('fatigue-alert-bar');
    const alertCount = document.getElementById('fatigue-alert-count');
    if (alertBar && alertCount) {
        alertBar.style.display = redCount > 0 ? 'flex' : 'none';
        alertCount.textContent = redCount;
    }
}

function renderFatigueSummary(d) {
    const container = document.getElementById('fatigue-summary');
    if (!container) return;
    const fd = d.fatigue_distribution || {};
    container.innerHTML = `
        <div class="fatigue-bar green">🟢 ${fd.GREEN ?? 0}</div>
        <div class="fatigue-bar yellow">🟡 ${fd.YELLOW ?? 0}</div>
        <div class="fatigue-bar red">🔴 ${fd.RED ?? 0}</div>`;
    setText('plan-restrictions', fd.RED ?? 0);
}

async function loadTideInfo() {
    try {
        const today = new Date().toISOString().slice(0, 10);
        const resp = await fetch(`${API_BASE}/api/tide?date=${today}`);
        const data = await resp.json();
        if (!data.points || data.points.length === 0) return;
        const now = new Date();
        const nowMin = now.getHours() * 60 + now.getMinutes();
        const closest = data.points.reduce((best, p) => {
            const pt = new Date(p.time);
            const ptMin = pt.getHours() * 60 + pt.getMinutes();
            const diff = ptMin - nowMin;
            return Math.abs(diff) < Math.abs(best.diff) ? { pt: p, diff } : best;
        }, { diff: Infinity });
        if (!closest.pt) return;
        const level = closest.pt.level;
        const status = (closest.pt.status || '').toUpperCase();
        const emoji = status.includes('DANGER') ? '🔴' : status === 'HIGH' || status === 'LOW' ? '🟡' : '🟢';
        const color = status.includes('DANGER') ? 'var(--danger-color)' : status === 'HIGH' || status === 'LOW' ? 'var(--warning-color)' : 'var(--success-color)';
        const kpiTide = document.getElementById('kpi-tide');
        if (kpiTide) { kpiTide.textContent = `${emoji} ${level.toFixed(1)}m`; kpiTide.style.color = color; }
        const envTide = document.getElementById('env-tide');
        if (envTide) envTide.textContent = `${level.toFixed(1)}m ${status}`;
        const envCable = document.getElementById('env-cable');
        if (envCable) {
            const risk = closest.pt.cable_risk || 'SAFE';
            envCable.textContent = risk === 'SAFE' ? '安全' : risk === 'DANGER' ? '⚠️ 危险' : '⚠️ 注意';
            envCable.style.color = risk === 'SAFE' ? 'var(--success-color)' : 'var(--warning-color)';
        }
    } catch (e) { console.warn('潮汐加载失败:', e); }
}

// 港区态势: 显示全部拖轮, 计数器与KPI一致
async function renderPortStatus() {
    try {
        const resp = await fetch(`${API_BASE}/api/tugs`);
        const data = await resp.json();
        const tugs = data.data || [];
        // 计数器使用 status_distribution (与KPI相同来源)
        const avail = tugs.filter(t => t.status === 'AVAILABLE').length;
        const busy = tugs.filter(t => t.status === 'BUSY').length;
        const locked = tugs.filter(t => t.status === 'LOCKED_BY_FRMS').length;
        setText('port-incoming', avail);
        setText('port-departing', busy);
        setText('port-berthed', locked);
        // 显示全部拖轮状态
        const tugList = document.getElementById('port-tug-list');
        if (tugList) {
            tugList.innerHTML = tugs.map(t => {
                const dot = t.status === 'AVAILABLE' ? 'green' : t.status === 'BUSY' ? 'yellow' : 'red';
                const label = t.status === 'AVAILABLE' ? '可用' : t.status === 'BUSY' ? '作业中' : '锁定';
                return `<div class="info-row"><span class="info-dot ${dot}"></span>${t.name} <span style="margin-left:auto;font-size:var(--font-xs);color:var(--text-muted);">${label}</span></div>`;
            }).join('');
        }
    } catch (e) { console.warn('港区态势加载失败:', e); }
}

// 拖轮监控: 全部拖轮 + 任务/定位
async function renderPadTugs() {
    try {
        const resp = await fetch(`${API_BASE}/api/tugs`);
        const data = await resp.json();
        const grid = document.getElementById('pad-grid');
        if (!grid) return;
        const tugs = data.data || [];
        setText('pad-total', tugs.length);
        grid.innerHTML = tugs.map(t => {
            const badgeClass = t.status === 'AVAILABLE' ? 'green' : t.status === 'BUSY' ? 'yellow' : 'red';
            const badgeText = t.status === 'AVAILABLE' ? '可用' : t.status === 'BUSY' ? '作业中' : '锁定';
            const hl = t.fatigue_level === 'RED' || t.fatigue_level === 'YELLOW';
            return `<div class="pad-tug-card ${hl ? 'highlight' : ''}">
                <div class="pad-tug-header">
                    <span class="pad-tug-name">🚢 ${t.name}</span>
                    <span class="pad-tug-badge ${badgeClass}">${badgeText}</span>
                </div>
                <div class="pad-tug-detail">⚡${t.horsepower}HP | 💪${t.fatigue_value.toFixed(1)} | 📍${t.berth_id || '航行中'}</div>
                <div class="pad-tug-actions">
                    <span class="pad-tug-btn" onclick="padShowTask('${t.id}','${t.name}')">📋 任务</span>
                    <span class="pad-tug-btn" onclick="padFlyTo('${t.id}',${t.position.lat},${t.position.lng})">📍 定位</span>
                </div>
            </div>`;
        }).join('');
    } catch (e) { console.warn('拖轮监控加载失败:', e); }
}

function padFlyTo(tugId, lat, lng) {
    switchNav('assistant');
    setTimeout(() => {
        if (map) { map.flyTo([lat, lng], 15, { duration: 1 }); const marker = tugMarkers[tugId]; if (marker) marker.openPopup(); }
    }, 500);
}

function padShowTask(tugId, tugName) {
    let info = `${tugName} 当前无任务分配`;
    if (currentSolutions && currentSolutions.length > 0) {
        const match = currentSolutions[0].assignments.filter(a => a.tug_id === tugId);
        if (match.length > 0) info = match.map(a => `任务 ${a.job_id} (${a.job_type}) 评分:${(a.score*100).toFixed(0)}%`).join('<br>');
    }
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;';
    overlay.onclick = function() { this.remove(); };
    overlay.innerHTML = `<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;padding:1rem;max-width:380px;width:90%;" onclick="event.stopPropagation()">
        <h3 style="margin-bottom:0.5rem;">📋 ${tugName}</h3>
        <div style="font-size:0.85rem;line-height:1.6;">${info}</div>
        <button style="margin-top:0.75rem;padding:0.3rem 1rem;background:var(--primary-color);color:white;border:none;border-radius:4px;cursor:pointer;" onclick="this.closest('div[onclick]').parentElement.remove()">关闭</button>
    </div>`;
    document.body.appendChild(overlay);
}

window.padFlyTo = padFlyTo;
window.padShowTask = padShowTask;

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}
