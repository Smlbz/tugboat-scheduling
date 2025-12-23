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
let selectedJobs = [];
let currentSolutions = [];

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadData();
    bindEvents();
});

function initMap() {
    // 初始化地图 (青岛港区域)
    map = L.map('map').setView([36.067, 120.385], 14);

    // 使用暗色地图底图
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
    renderBerthsOnMap(data.data);
}

async function loadJobs() {
    const response = await fetch(`${API_BASE}/api/jobs`);
    const data = await response.json();
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

function adoptSolution(solutionId) {
    // TODO [成员D]: 实现方案采纳逻辑
    // 1. 高亮地图上的分配
    // 2. 显示连活连线
    alert('已采纳方案: ' + solutionId);
}

// ============ Chatbot ============

async function sendChat() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question) return;

    // 显示用户消息
    addChatMessage(question, 'user');
    input.value = '';

    // 调用解释接口
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
        const chatbot = document.getElementById('chatbot');
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

// TODO [成员D]: 添加更多交互功能
// - 点击拖轮显示详情
// - 方案采纳后的连线动画
// - 违规弹窗特效
