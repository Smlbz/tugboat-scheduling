/**
 * CMATSS 拖轮调度系统 - 前端逻辑
 * 负责人: 成员D
 */

// API 基础地址
const API_BASE = '';

// 状态
let map = null;
let tugMarkers = {};
let berthMarkers = {};
let berthPositions = {};
let jobBerthMap = {};
let selectedJobs = [];
let currentSolutions = [];
let adoptedSolutionId = null;
let chainLayers = [];
let highlightedRestore = [];

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadData();
    bindEvents();
    initVoice();
});

function initMap() {
    map = L.map('map').setView([36.067, 120.385], 14);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);
}

// ============ 数据加载 ============

async function loadData() {
    try {
        await Promise.all([
            loadTugs(),
            loadBerths(),
            loadJobs(),
            loadDashboard()
        ]);
        console.log('数据加载完成');
    } catch (error) {
        console.error('数据加载失败:', error);
    }
}

async function loadTugs() {
    try {
        const response = await fetch(`${API_BASE}/api/tugs`);
        const data = await response.json();
        renderTugsOnMap(data.data);
    } catch (e) {
        console.error('[加载] 拖轮数据失败:', e);
    }
}

async function loadBerths() {
    try {
        const response = await fetch(`${API_BASE}/api/berths`);
        const data = await response.json();
        data.data.forEach(b => { berthPositions[b.id] = b.position; });
        renderBerthsOnMap(data.data);
    } catch (e) {
        console.error('[加载] 泊位数据失败:', e);
    }
}

async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE}/api/jobs`);
        const data = await response.json();
        data.data.forEach(j => { jobBerthMap[j.id] = j.target_berth_id; });
        renderJobList(data.data);
    } catch (e) {
        console.error('[加载] 任务数据失败:', e);
    }
}

async function loadDashboard() {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard`);
        const data = await response.json();
        renderDashboard(data);
    } catch (e) {
        console.warn('看板加载失败:', e);
    }
    // 同时加载潮汐
    loadTideInfo();
}

async function loadTideInfo() {
    try {
        const today = new Date().toISOString().slice(0, 10);
        const resp = await fetch(`${API_BASE}/api/tide?date=${today}`);
        const data = await resp.json();
        if (!data.points || data.points.length === 0) return;

        // 找到当前最近的潮位点
        const now = new Date();
        const nowMin = now.getHours() * 60 + now.getMinutes();
        const closest = data.points.reduce((best, p) => {
            const pt = new Date(p.time);
            const ptMin = pt.getHours() * 60 + pt.getMinutes();
            return Math.abs(ptMin - nowMin) < Math.abs(best.diff) ? {pt: p, diff: ptMin - nowMin} : best;
        }, {diff: Infinity});

        if (!closest.pt) return;

        const el = document.getElementById('dash-tide');
        const level = closest.pt.level;
        const status = closest.pt.status;
        const emoji = status.includes('DANGER') ? '🔴' : status === 'HIGH' || status === 'LOW' ? '🟡' : '🟢';
        el.textContent = `${emoji} ${level.toFixed(1)}m`;

        // 缆绳风险
        const riskEl = document.getElementById('dash-cable-risk');
        const labelEl = document.getElementById('dash-cable-label');
        if (closest.pt.cable_risk !== 'SAFE') {
            riskEl.style.display = 'flex';
            const riskEmoji = closest.pt.cable_risk === 'DANGER' ? '🔴' : '🟡';
            const riskText = closest.pt.cable_risk === 'DANGER' ? '危险' : '注意';
            labelEl.textContent = `${riskEmoji} ${riskText}`;
            labelEl.style.color = closest.pt.cable_risk === 'DANGER' ? 'var(--danger-color)' : 'var(--warning-color)';
        } else {
            riskEl.style.display = 'none';
        }

        // 潮位-色标
        if (status.includes('DANGER')) el.style.color = 'var(--danger-color)';
        else if (status === 'HIGH' || status === 'LOW') el.style.color = 'var(--warning-color)';
        else el.style.color = 'var(--success-color)';
    } catch (e) {
        console.warn('潮汐加载失败:', e);
    }
}

function renderDashboard(d) {
    document.getElementById('dash-available').textContent = d.available_tugs ?? '--';
    document.getElementById('dash-total').textContent = d.total_tugs ?? '--';
    document.getElementById('dash-jobs').textContent = d.total_jobs ?? '--';
    document.getElementById('dash-green').textContent = d.fatigue_distribution?.GREEN ?? 0;
    document.getElementById('dash-yellow').textContent = d.fatigue_distribution?.YELLOW ?? 0;
    document.getElementById('dash-red').textContent = d.fatigue_distribution?.RED ?? 0;
}

// ============ 地图渲染 ============

function renderTugsOnMap(tugs) {
    tugs.forEach(tug => {
        const color = getTugColor(tug);
        const marker = L.circleMarker([tug.position.lat, tug.position.lng], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);

        marker.bindPopup(`
            <strong>${tug.name}</strong><br>
            马力: ${tug.horsepower}<br>
            状态: ${tug.status}<br>
            疲劳值: ${tug.fatigue_value.toFixed(1)}
        `);

        tugMarkers[tug.id] = marker;
    });
}

function getTugColor(tug) {
    if (tug.status === 'LOCKED_BY_FRMS') return '#ef4444';
    if (tug.status === 'BUSY') return '#3b82f6';
    if (tug.fatigue_level === 'YELLOW') return '#eab308';
    return '#22c55e';
}

function renderBerthsOnMap(berths) {
    berths.forEach(berth => {
        const marker = L.marker([berth.position.lat, berth.position.lng], {
            icon: L.divIcon({
                className: 'berth-icon',
                html: `<div style="background:#475569;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;">${berth.name}</div>`,
                iconSize: [60, 20]
            })
        }).addTo(map);

        marker.bindPopup(`
            <strong>${berth.name}</strong><br>
            停靠拖轮: ${berth.tugs_stack.length}
        `);

        berthMarkers[berth.id] = marker;
    });
}

// ============ 任务列表 ============

let allJobIds = [];

function renderJobList(jobs) {
    allJobIds = jobs.map(j => j.id);
    const container = document.getElementById('job-list');
    container.innerHTML = jobs.map(job => `
        <div class="job-card" data-id="${job.id}" onclick="toggleJobSelection('${job.id}')">
            <span class="job-type">${getJobTypeLabel(job.job_type)}</span>
            <h3>${job.ship_name}</h3>
            <p>泊位: ${job.target_berth_id} | 马力需求: ${job.required_horsepower}</p>
            <p>${formatTime(job.start_time)} - ${formatTime(job.end_time)}</p>
        </div>
    `).join('');
    updateSelectAllBtn();
}

function getJobTypeLabel(type) {
    const labels = {
        'BERTHING': '靠泊',
        'UNBERTHING': '离泊',
        'SHIFTING': '移泊',
        'ESCORT': '护航'
    };
    return labels[type] || type;
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function toggleJobSelection(jobId) {
    const card = document.querySelector(`.job-card[data-id="${jobId}"]`);
    if (selectedJobs.includes(jobId)) {
        selectedJobs = selectedJobs.filter(id => id !== jobId);
        card.classList.remove('selected');
    } else {
        selectedJobs.push(jobId);
        card.classList.add('selected');
    }
    updateSelectAllBtn();
}

function toggleSelectAll() {
    const allSelected = selectedJobs.length === allJobIds.length;
    const cards = document.querySelectorAll('.job-card');
    if (allSelected) {
        // 取消全选
        selectedJobs = [];
        cards.forEach(c => c.classList.remove('selected'));
    } else {
        // 全选
        selectedJobs = [...allJobIds];
        cards.forEach(c => c.classList.add('selected'));
    }
    updateSelectAllBtn();
}

function updateSelectAllBtn() {
    const btn = document.getElementById('select-all-btn');
    if (!btn) return;
    const allSelected = allJobIds.length > 0 && selectedJobs.length === allJobIds.length;
    btn.textContent = allSelected ? '☑ 取消全选' : '☑ 全选';
}

// ============ 调度 ============

async function runSchedule() {
    const btn = document.getElementById('schedule-btn');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '⏳ 计算中...';

    try {
        const response = await fetch(`${API_BASE}/api/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_ids: selectedJobs.length ? selectedJobs : null })
        });

        const data = await response.json();
        if (data.success) {
            currentSolutions = data.solutions;
            clearAdoption();
            renderSolutions(data.solutions);
        } else {
            alert('调度失败: ' + (data.error_message || data.detail || '未知错误'));
        }
    } catch (error) {
        console.error('调度请求失败:', error);
        alert('调度请求失败');
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 智能调度';
    }
}

function renderSolutions(solutions) {
    const container = document.getElementById('solution-list');

    if (!solutions || solutions.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无可用方案</div>';
        return;
    }

    container.innerHTML = solutions.map((sol, index) => `
        <div class="solution-card" data-id="${sol.solution_id}">
            <h3>${getEmoji(index)} ${sol.name}</h3>
            <div class="solution-metrics">
                <div class="metric">
                    成本: <span class="metric-value">¥${sol.metrics.total_cost.toFixed(0)}</span>
                </div>
                <div class="metric">
                    均衡度: <span class="metric-value">${(sol.metrics.balance_score * 100).toFixed(0)}%</span>
                </div>
                <div class="metric">
                    效率: <span class="metric-value">${(sol.metrics.efficiency_score * 100).toFixed(0)}%</span>
                </div>
                <div class="metric">
                    综合: <span class="metric-value">${(sol.metrics.overall_score * 100).toFixed(0)}%</span>
                </div>
            </div>
            ${sol.chain_jobs.length > 0 ? `
                <div style="color:#22c55e;font-size:0.75rem;margin-bottom:0.5rem;">
                    ✨ 识别到 ${sol.chain_jobs.length} 对连活，节省 ¥${sol.chain_jobs.reduce((sum, c) => sum + c.cost_saving, 0).toFixed(0)}
                </div>
            ` : ''}
            <div class="solution-actions">
                <button class="btn-adopt" onclick="adoptSolution('${sol.solution_id}')">✓ 采纳</button>
                <button class="btn-explain" onclick="showExplainModal('${sol.solution_id}')">🧠 AI 解释</button>
            </div>
        </div>
    `).join('');
}

function getEmoji(index) {
    return ['💰', '⚖️', '🏆'][index] || '📋';
}

// ============ 方案采纳 ============

function adoptSolution(solutionId) {
    const solution = currentSolutions.find(s => s.solution_id === solutionId);
    if (!solution) return;

    adoptedSolutionId = solutionId;
    clearAdoption();

    highlightAssignedTugs(solution.assignments);
    drawChainLines(solution.chain_jobs || []);
    showAssignmentDetails(solution);

    // 语音播报
    speakTugAssignment(solution);

    // 高亮选中的方案卡片
    document.querySelectorAll('.solution-card').forEach(c => c.classList.remove('adopted'));
    const card = document.querySelector(`.solution-card[data-id="${solutionId}"]`);
    if (card) card.classList.add('adopted');
}

function clearAdoption() {
    adoptedSolutionId = null;

    // 恢复拖轮样式
    highlightedRestore.forEach(fn => fn());
    highlightedRestore = [];

    // 移除连线
    chainLayers.forEach(layer => map.removeLayer(layer));
    chainLayers = [];

    // 移除详情面板
    const panel = document.getElementById('assignment-details');
    if (panel) panel.remove();

    // 移除违规弹窗
    closeViolationModal();

    // 取消卡片高亮
    document.querySelectorAll('.solution-card').forEach(c => c.classList.remove('adopted'));
}

function highlightAssignedTugs(assignments) {
    assignments.forEach(a => {
        const marker = tugMarkers[a.tug_id];
        if (!marker || !marker.getElement()) return;

        const el = marker.getElement();
        const origColor = marker.options.color;
        const origFillColor = marker.options.fillColor;
        const origRadius = marker.options.radius;
        const origWeight = marker.options.weight;

        highlightedRestore.push(() => {
            marker.setStyle({
                color: origColor,
                fillColor: origFillColor,
                radius: origRadius,
                weight: origWeight,
                fillOpacity: 0.8
            });
            el.classList.remove('tug-highlighted');
        });

        marker.setStyle({
            color: '#22c55e',
            fillColor: '#22c55e',
            radius: 12,
            weight: 3,
            fillOpacity: 1
        });
        el.classList.add('tug-highlighted');

        const jobLabel = { BERTHING: '靠泊', UNBERTHING: '离泊', SHIFTING: '移泊', ESCORT: '护航' };
        marker.bindPopup(`
            <strong>${a.tug_name}</strong><br>
            任务: ${a.job_id} (${jobLabel[a.job_type] || a.job_type})<br>
            评分: ${(a.score * 100).toFixed(0)}%
        `);
        marker.openPopup();
    });
}

function drawChainLines(chainJobs) {
    chainJobs.forEach(chain => {
        const berth1 = jobBerthMap[chain.job1_id];
        const berth2 = jobBerthMap[chain.job2_id];
        const pos1 = berthPositions[berth1];
        const pos2 = berthPositions[berth2];
        if (!pos1 || !pos2) return;

        const latlngs = [[pos1.lat, pos1.lng], [pos2.lat, pos2.lng]];

        // 虚线连线
        const polyline = L.polyline(latlngs, {
            color: '#22c55e',
            weight: 3,
            opacity: 0.85,
            dashArray: '10, 8',
            lineCap: 'round'
        }).addTo(map);

        // 连线动画（通过 JS 动态修改 dashOffset）
        const el = polyline.getElement();
        if (el) {
            el.style.animation = 'chainDashMove 1s linear infinite';
        }

        // 中点标签
        const midLat = (pos1.lat + pos2.lat) / 2;
        const midLng = (pos1.lng + pos2.lng) / 2;
        const label = L.marker([midLat, midLng], {
            icon: L.divIcon({
                className: 'chain-label',
                html: `<div class="chain-label-inner">
                    <div>⛓️ 连活</div>
                    <div>节省 ¥${chain.cost_saving.toFixed(0)}</div>
                    <div class="chain-label-sub">${chain.interval_hours.toFixed(1)}h间隔 / ${chain.distance_nm.toFixed(1)}nm</div>
                </div>`,
                iconSize: [130, 54],
                iconAnchor: [65, 27]
            })
        }).addTo(map);

        chainLayers.push(polyline, label);
    });

    // 调整视野包含所有连线
    if (chainJobs.length > 0) {
        const bounds = [];
        chainJobs.forEach(chain => {
            const b1 = jobBerthMap[chain.job1_id];
            const b2 = jobBerthMap[chain.job2_id];
            const p1 = berthPositions[b1];
            const p2 = berthPositions[b2];
            if (p1) bounds.push([p1.lat, p1.lng]);
            if (p2) bounds.push([p2.lat, p2.lng]);
        });
        if (bounds.length > 0) {
            // 仅当拖轮高亮后才调整视野
        }
    }
}

function showAssignmentDetails(solution) {
    const existing = document.getElementById('assignment-details');
    if (existing) existing.remove();

    const panel = document.createElement('div');
    panel.id = 'assignment-details';
    panel.className = 'assignment-details-panel';

    // 按作业分组
    const byJob = {};
    solution.assignments.forEach(a => {
        if (!byJob[a.job_id]) byJob[a.job_id] = [];
        byJob[a.job_id].push(a);
    });

    let html = `<div class="assignment-header">
        <h3>${solution.name} - 分配详情</h3>
        <button onclick="clearAdoption()" class="btn-close" title="关闭">✕</button>
    </div>`;

    const jobTypeMap = { BERTHING: '靠泊', UNBERTHING: '离泊', SHIFTING: '移泊', ESCORT: '护航' };

    for (const [jobId, assigns] of Object.entries(byJob)) {
        const type = jobTypeMap[assigns[0].job_type] || assigns[0].job_type;
        html += `<div class="assignment-group">
            <div class="assignment-job">${jobId} (${type})</div>`;
        assigns.forEach(a => {
            const marker = tugMarkers[a.tug_id];
            const dotColor = marker ? marker.options.fillColor : '#22c55e';
            html += `<div class="assignment-tug" onclick="map.panTo(tugMarkers['${a.tug_id}'].getLatLng())">
                <span class="tug-dot" style="background:${dotColor}"></span>
                ${a.tug_name}
                <span class="assignment-score">${(a.score * 100).toFixed(0)}%</span>
            </div>`;
        });
        html += `</div>`;
    }

    if (solution.chain_jobs && solution.chain_jobs.length > 0) {
        const totalSaving = solution.chain_jobs.reduce((s, c) => s + c.cost_saving, 0);
        html += `<div class="assignment-chains">
            <span style="color:#22c55e;">⛓️ ${solution.chain_jobs.length} 对连活，节省 ¥${totalSaving.toFixed(0)}</span>
        </div>`;
    }

    html += `<div class="assignment-metrics">
        <div>💰 ¥${solution.metrics.total_cost.toFixed(0)}</div>
        <div>⚖️ ${(solution.metrics.balance_score * 100).toFixed(0)}%</div>
        <div>⚡ ${(solution.metrics.efficiency_score * 100).toFixed(0)}%</div>
        <div>🏆 ${(solution.metrics.overall_score * 100).toFixed(0)}%</div>
    </div>`;

    panel.innerHTML = html;
    document.body.appendChild(panel);

    // 初始定位右下角
    panel.style.bottom = '20px';
    panel.style.right = '20px';

    // 拖拽逻辑
    const header = panel.querySelector('.assignment-header');
    let isDragging = false, startX, startY, origLeft, origTop;

    header.addEventListener('mousedown', (e) => {
        if (e.target.tagName === 'BUTTON') return; // 不干扰关闭按钮
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        origLeft = panel.offsetLeft;
        origTop = panel.offsetTop;
        panel.style.transition = 'none';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        panel.style.left = (origLeft + e.clientX - startX) + 'px';
        panel.style.top = (origTop + e.clientY - startY) + 'px';
        panel.style.bottom = 'auto';
        panel.style.right = 'auto';
    });

    document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        document.body.style.userSelect = '';
    });
}

// ============ 语音提醒 ============

let voiceEnabled = false;

function initVoice() {
    const btn = document.getElementById('voice-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        voiceEnabled = !voiceEnabled;
        btn.textContent = voiceEnabled ? '🔊 语音开' : '🔇 语音关';
        if (voiceEnabled) {
            // 测试语音
            const test = new SpeechSynthesisUtterance('语音播报已开启');
            test.lang = 'zh-CN';
            test.rate = 0.9;
            speechSynthesis.speak(test);
        } else {
            speechSynthesis.cancel();
        }
    });
}

function speakTugAssignment(solution) {
    if (!voiceEnabled || !window.speechSynthesis) return;

    speechSynthesis.cancel();

    const assignments = solution.assignments || [];
    const chainJobs = solution.chain_jobs || [];

    // 按作业分组
    const byJob = {};
    assignments.forEach(a => {
        if (!byJob[a.job_id]) byJob[a.job_id] = [];
        byJob[a.job_id].push(a);
    });

    // 逐任务播报
    let idx = 0;
    for (const [jobId, assigns] of Object.entries(byJob)) {
        const tugNames = assigns.map(a => a.tug_name || a.tug_id).join('、');
        const text = `任务 ${jobId}, 指派 ${tugNames} 执行`;
        setTimeout(() => {
            if (!voiceEnabled) return;
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'zh-CN';
            u.rate = 0.85;
            speechSynthesis.speak(u);
        }, idx * 3000);
        idx++;
    }

    // 连活提示
    if (chainJobs.length > 0) {
        setTimeout(() => {
            if (!voiceEnabled) return;
            const u = new SpeechSynthesisUtterance(
                `识别到 ${chainJobs.length} 对连活任务, 预计节省成本`
            );
            u.lang = 'zh-CN';
            u.rate = 0.85;
            speechSynthesis.speak(u);
        }, idx * 3000 + 1000);
    }
}

// ============ 违规弹窗 ============

function showViolationModal(title, violations) {
    closeViolationModal();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'violation-modal';
    overlay.onclick = e => { if (e.target === overlay) closeViolationModal(); };

    const modal = document.createElement('div');
    modal.className = 'modal-content';

    let bodyHtml = '';
    if (typeof violations === 'string') {
        bodyHtml = `<p>${violations}</p>`;
    } else if (Array.isArray(violations)) {
        bodyHtml = violations.map(v => `<div class="violation-item">
            <span class="violation-icon">⚠️</span>
            <span>${v}</span>
        </div>`).join('');
    } else if (violations && violations.violation_reason) {
        bodyHtml = `<p>${violations.violation_reason}</p>`;
        if (violations.violation_rules) {
            bodyHtml += `<div style="margin-top:0.5rem;font-size:0.75rem;color:#94a3b8;">
                违反规则: ${violations.violation_rules.join(', ')}
            </div>`;
        }
    }

    modal.innerHTML = `
        <div class="modal-header">
            <span class="modal-icon">🚨</span>
            <h3>${title || '合规检查'}</h3>
            <button onclick="closeViolationModal()" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
            ${bodyHtml || '<p>无违规信息</p>'}
        </div>
        <div class="modal-footer">
            <button onclick="closeViolationModal()" class="btn-primary" style="margin:0;">确认</button>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // 弹窗出现动画
    requestAnimationFrame(() => overlay.classList.add('visible'));
}

function closeViolationModal() {
    const overlay = document.getElementById('violation-modal');
    if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
    }
}

// ============ AI 解释 ============

async function showExplainModal(solutionId) {
    try {
        console.log('[AI解释] 点击 solutionId:', solutionId);
        if (!Array.isArray(currentSolutions) || currentSolutions.length === 0) {
            throw new Error('当前没有可用的调度方案数据，请先执行智能调度');
        }
        console.log('[AI解释] currentSolutions:', currentSolutions.length, '条');

        closeExplainModal();
        const solution = currentSolutions.find(s => s.solution_id === solutionId);
        if (!solution) {
            throw new Error('未找到方案 ' + solutionId + ' 的数据，请重新调度');
        }
        console.log('[AI解释] 找到方案:', solution.name);
        const name = solution.name ?? '未知方案';

        // 创建遮罩+模态框
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'explain-modal';
        overlay.onclick = e => { if (e.target === overlay) closeExplainModal(); };

        const modal = document.createElement('div');
        modal.className = 'modal-content explain-modal';

        const m = solution.metrics || {};
        const costStr = m.total_cost?.toFixed?.(0) ?? 'N/A';
        const balStr = m.balance_score != null ? (m.balance_score * 100).toFixed(0) + '%' : 'N/A';
        const effStr = m.efficiency_score != null ? (m.efficiency_score * 100).toFixed(0) + '%' : 'N/A';
        const ovrStr = m.overall_score != null ? (m.overall_score * 100).toFixed(0) + '%' : 'N/A';

        modal.innerHTML = `
            <div class="modal-header">
                <span class="modal-icon">🧠</span>
                <h3>AI 调度解释 — ${name}</h3>
                <button onclick="closeExplainModal()" class="btn-close">✕</button>
            </div>
            <div class="modal-body">
                <div class="explain-section">
                    <h4>📊 方案指标</h4>
                    <div class="explain-metrics">
                        <span>成本: ¥${costStr}</span>
                        <span>均衡: ${balStr}</span>
                        <span>效率: ${effStr}</span>
                        <span>综合: ${ovrStr}</span>
                    </div>
                </div>
                <div class="explain-section">
                    <h4>💬 解释</h4>
                    <div id="explain-text" class="explain-text">正在生成解释...</div>
                </div>
                <div class="explain-section">
                    <h4>🔄 反事实推演</h4>
                    <div class="counterfactual-controls">
                        <button class="btn-small" onclick="runCounterfactual('${solutionId}')">推演: 替换拖轮</button>
                    </div>
                    <div id="counterfactual-text" class="counterfactual-text">点击按钮查看反事实分析</div>
                </div>
            </div>
            <div class="modal-footer">
                <button onclick="closeExplainModal()" class="btn-primary" style="margin:0;">关闭</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        requestAnimationFrame(() => overlay.classList.add('visible'));

        // 调用 API 获取解释
        try {
            console.log('[AI解释] 请求API, solutionId:', solutionId);
            const resp = await fetch(`${API_BASE}/api/explain`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ solution_id: solutionId })
            });
            const data = await resp.json();
            console.log('[AI解释] 响应:', data);
            const text = data.explanation || '无法生成解释';
            const el = document.getElementById('explain-text');
            if (el) {
                el.textContent = text;
                console.log('[AI解释] 已更新文本');
            } else {
                console.warn('[AI解释] DOM元素explain-text不存在');
            }
        } catch (e) {
            console.error('[AI解释] 请求失败:', e);
            const el = document.getElementById('explain-text');
            if (el) el.textContent = '解释服务不可用: ' + e.message;
        }
    } catch (e) {
        console.error('[AI解释] 错误:', e);
        alert('AI解释暂不可用: ' + e.message);
    }
}

async function runCounterfactual(solutionId) {
    try {
        const textEl = document.getElementById('counterfactual-text');
        if (!textEl) {
            console.error('[反事实] 找不到 counterfactual-text DOM 元素');
            return;
        }
        textEl.textContent = '正在推演...';

        try {
            const resp = await fetch(`${API_BASE}/api/counterfactual`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ solution_id: solutionId })
            });
            const data = await resp.json();
            textEl.textContent = data.counterfactual || '推演结果不可用';
        } catch (e) {
            textEl.textContent = '推演服务不可用: ' + e.message;
        }
    } catch (e) {
        console.error('[反事实] 错误:', e);
        alert('反事实推演暂不可用: ' + e.message);
    }
}

function closeExplainModal() {
    const overlay = document.getElementById('explain-modal');
    if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
    }
}

async function checkComplianceForAssignment(tugId, jobId) {
    try {
        const response = await fetch(`${API_BASE}/api/compliance/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tug_id: tugId, job_id: jobId })
        });
        const data = await response.json();
        showViolationModal('合规检查结果', data);
        return data;
    } catch (error) {
        showViolationModal('合规检查失败', [error.message || '无法连接到服务器']);
        return null;
    }
}

// ============ 事件绑定 ============

function bindEvents() {
    document.getElementById('schedule-btn').addEventListener('click', runSchedule);
    document.getElementById('refresh-jobs').addEventListener('click', loadJobs);
    document.getElementById('select-all-btn').addEventListener('click', toggleSelectAll);
}
