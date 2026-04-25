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
            loadJobs()
        ]);
        console.log('数据加载完成');
    } catch (error) {
        console.error('数据加载失败:', error);
    }
}

async function loadTugs() {
    const response = await fetch(`${API_BASE}/api/tugs`);
    const data = await response.json();
    renderTugsOnMap(data.data);
}

async function loadBerths() {
    const response = await fetch(`${API_BASE}/api/berths`);
    const data = await response.json();
    data.data.forEach(b => { berthPositions[b.id] = b.position; });
    renderBerthsOnMap(data.data);
}

async function loadJobs() {
    const response = await fetch(`${API_BASE}/api/jobs`);
    const data = await response.json();
    data.data.forEach(j => { jobBerthMap[j.id] = j.target_berth_id; });
    renderJobList(data.data);
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

function renderJobList(jobs) {
    const container = document.getElementById('job-list');
    container.innerHTML = jobs.map(job => `
        <div class="job-card" data-id="${job.id}" onclick="toggleJobSelection('${job.id}')">
            <span class="job-type">${getJobTypeLabel(job.job_type)}</span>
            <h3>${job.ship_name}</h3>
            <p>泊位: ${job.target_berth_id} | 马力需求: ${job.required_horsepower}</p>
            <p>${formatTime(job.start_time)} - ${formatTime(job.end_time)}</p>
        </div>
    `).join('');
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
}

// ============ 调度 ============

async function runSchedule() {
    const btn = document.getElementById('schedule-btn');
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
            alert('调度失败: ' + data.error_message);
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
            <button class="btn-adopt" onclick="adoptSolution('${sol.solution_id}')">✓ 采纳此方案</button>
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
    document.querySelector('.right-panel').appendChild(panel);
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

// ============ Chatbot ============

async function sendChat() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question) return;

    addChatMessage(question, 'user');
    input.value = '';

    try {
        const solutionId = currentSolutions[0]?.solution_id || '';
        const response = await fetch(`${API_BASE}/api/explain?solution_id=${solutionId}&question=${encodeURIComponent(question)}`, {
            method: 'POST'
        });
        const data = await response.json();
        addChatMessage(data.explanation, 'bot');
    } catch (error) {
        addChatMessage('抱歉，无法获取回答。', 'bot');
    }
}

function addChatMessage(text, type) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ============ 事件绑定 ============

function bindEvents() {
    document.getElementById('schedule-btn').addEventListener('click', runSchedule);
    document.getElementById('refresh-jobs').addEventListener('click', loadJobs);
    document.getElementById('send-chat').addEventListener('click', sendChat);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChat();
    });
    document.getElementById('toggle-chat').addEventListener('click', () => {
        const messages = document.getElementById('chat-messages');
        const input = document.querySelector('.chat-input');
        if (messages.style.display === 'none') {
            messages.style.display = 'block';
            input.style.display = 'flex';
        } else {
            messages.style.display = 'none';
            input.style.display = 'none';
        }
    });
}
