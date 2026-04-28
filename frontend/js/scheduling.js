/**
 * CMATSS 拖轮调度系统 - 调度模块
 * 任务列表、选择、调度请求、方案渲染
 */

async function loadJobs() {
    try {
        const resp = await fetch(`${API_BASE}/api/jobs`);
        const data = await resp.json();
        data.data.forEach(j => { jobBerthMap[j.id] = j.target_berth_id; });
        renderJobList(data.data);
        renderAssistantJobList(data.data);
    } catch (e) {
        console.error('[加载] 任务数据失败:', e);
    }
}

function renderJobList(jobs) {
    allJobIds = jobs.map(j => j.id);
    const container = document.getElementById('job-list');
    if (!container) return;
    const displayJobs = jobs.slice(0, 15);
    container.innerHTML = displayJobs.map(job => `
        <div class="job-card" data-id="${job.id}" onclick="toggleJobSelection('${job.id}')">
            <span class="job-type">${getJobTypeLabel(job.job_type)}</span>
            <h3>${job.ship_name}</h3>
            <p>泊位: ${job.target_berth_id} | 马力需求: ${job.required_horsepower}</p>
            <p>${formatTime(job.start_time)} - ${formatTime(job.end_time)}</p>
        </div>
    `).join('');
    updateSelectAllBtn();
    renderAttentionPoints();
}

function updateAssistantJobs(jobIds) {
    // 调度后: 只显示已分配任务的记录
    const container = document.getElementById('assistant-job-list');
    if (!container) return;
    const allJobs = document.querySelectorAll('#job-list .job-card, #assistant-job-list .job-card');
    const jobs = [];
    jobIds.forEach(id => {
        const card = document.querySelector(`.job-card[data-id="${id}"]`);
        if (card) {
            const text = card.innerHTML;
            const name = card.querySelector('h3')?.textContent || id;
            const type = card.querySelector('.job-type')?.textContent || '';
            const info = card.querySelectorAll('p');
            jobs.push({ id, ship_name: name, job_type: type, info: info.length > 0 ? info[0].textContent : '' });
        }
    });
    container.innerHTML = jobs.slice(0, 8).map(j => `
        <div class="job-card" data-id="${j.id}" onclick="flyToJob('${j.id}')" style="border-left-color:var(--success-color);">
            <span class="job-type">${j.job_type}</span>
            <h3>✅ ${j.ship_name}</h3>
            <p>${j.info}</p>
        </div>
    `).join('') || '<div class="empty-state">暂无调度任务</div>';
}

function renderAssistantJobList(jobs) {
    const container = document.getElementById('assistant-job-list');
    if (!container) return;
    container.innerHTML = jobs.slice(0, 5).map(job => `
        <div class="job-card" data-id="${job.id}" data-berth="${job.target_berth_id}" onclick="flyToJob('${job.id}')">
            <span class="job-type">${getJobTypeLabel(job.job_type)}</span>
            <h3>${job.ship_name}</h3>
            <p>泊位: ${job.target_berth_id} | ${formatTime(job.start_time)}-${formatTime(job.end_time)}</p>
            <p>马力需求: ${job.required_horsepower}HP | 拖轮: ${job.required_tug_count}艘</p>
        </div>
    `).join('');
}

function flyToJob(jobId) {
    const berthId = jobBerthMap[jobId];
    const pos = berthPositions[berthId];
    if (map && pos) {
        map.flyTo([pos.lat, pos.lng], 15, { duration: 1 });
        // 在专注任务面板显示
        renderFocusTask(jobId);
    }
}

function renderFocusTask(jobId) {
    const container = document.getElementById('focus-task');
    if (!container) return;
    // 从 DOM 缓存找任务数据
    const card = document.querySelector(`.job-card[data-id="${jobId}"]`);
    if (!card) {
        container.innerHTML = '<div class="empty-state">选择任务</div>';
        return;
    }
    const clone = card.cloneNode(true);
    container.innerHTML = '';
    container.appendChild(clone);
}

function getJobTypeLabel(type) {
    const labels = { BERTHING: '靠泊', UNBERTHING: '离泊', SHIFTING: '移泊', ESCORT: '护航' };
    return labels[type] || type;
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function toggleJobSelection(jobId) {
    const card = document.querySelector(`.job-card[data-id="${jobId}"]`);
    if (!card) return;
    if (selectedJobs.includes(jobId)) {
        selectedJobs = selectedJobs.filter(id => id !== jobId);
        card.classList.remove('selected');
    } else {
        selectedJobs.push(jobId);
        card.classList.add('selected');
    }
    updateSelectAllBtn();
    renderAttentionPoints();
}

function toggleSelectAll() {
    const allSelected = selectedJobs.length === allJobIds.length;
    const cards = document.querySelectorAll('.job-card');
    if (allSelected) {
        selectedJobs = [];
        cards.forEach(c => c.classList.remove('selected'));
    } else {
        selectedJobs = [...allJobIds];
        cards.forEach(c => c.classList.add('selected'));
    }
    updateSelectAllBtn();
    renderAttentionPoints();
}

function renderAttentionPoints() {
    const container = document.getElementById('attention-points');
    if (!container) return;
    if (!selectedJobs.length) {
        container.innerHTML = '<div class="attention-item" style="color:var(--text-muted);">选择任务后显示关注点</div>';
        return;
    }
    // 从 DOM 卡片提取选中任务信息
    const cards = document.querySelectorAll('.job-card.selected');
    let totalHp = 0, totalTugs = 0, timeRanges = [], highRiskCount = 0;
    cards.forEach(c => {
        const text = c.textContent;
        const hpMatch = text.match(/马力需求:\s*(\d+)/);
        if (hpMatch) totalHp += parseInt(hpMatch[1]);
        const tugMatch = text.match(/拖轮:\s*(\d+)/);
        if (tugMatch) totalTugs += parseInt(tugMatch[1]);
        const timeMatch = text.match(/(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})/);
        if (timeMatch) timeRanges.push({ start: timeMatch[1], end: timeMatch[2] });
    });
    // 检查重叠
    let overlapCount = 0;
    for (let i = 0; i < timeRanges.length; i++) {
        for (let j = i + 1; j < timeRanges.length; j++) {
            if (timeRanges[i].start < timeRanges[j].end && timeRanges[j].start < timeRanges[i].end) overlapCount++;
        }
    }
    const items = [
        { icon: '🔧', label: `总马力需求: ${totalHp.toLocaleString()}HP` },
        { icon: '🚢', label: `需拖轮: ~${Math.max(totalTugs, Math.ceil(totalHp / 5000))} 艘` },
    ];
    if (overlapCount > 0) items.push({ icon: '⚠️', label: `${overlapCount} 对任务时间重叠`, cls: 'red' });
    items.push({ icon: '📊', label: `已选 ${selectedJobs.length}/${allJobIds.length} 任务` });

    container.innerHTML = items.map(item =>
        `<div class="attention-item" style="${item.cls === 'red' ? 'color:var(--warning-color);' : ''}">${item.icon} ${item.label}</div>`
    ).join('');
}

function updateSelectAllBtn() {
    const btn = document.getElementById('select-all-btn');
    if (!btn) return;
    const allSelected = allJobIds.length > 0 && selectedJobs.length === allJobIds.length;
    btn.textContent = allSelected ? '☑ 取消全选' : '☑ 全选';
}

async function runSchedule() {
    const btn = document.getElementById('schedule-btn');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '⏳ 计算中...';

    try {
        const resp = await fetch(`${API_BASE}/api/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_ids: selectedJobs.length ? selectedJobs : null })
        });

        const data = await resp.json();
        if (data.success) {
            currentSolutions = data.solutions;
            clearAdoption();
            renderSolutions(data.solutions);
            renderRadarChart(data.solutions);
            // 更新方案比选 KPI
            const planCount = document.getElementById('plan-solution-count');
            if (planCount) planCount.textContent = data.solutions.length;
            // 更新重点任务列表: 只显示已调度的任务
            const scheduledJobIds = new Set();
            data.solutions.forEach(s => (s.assignments || []).forEach(a => scheduledJobIds.add(a.job_id)));
            updateAssistantJobs(Array.from(scheduledJobIds));
            // 切换到方案比选视图
            switchNav('planning');
        } else {
            alert('调度失败: ' + (data.error_message || data.detail || '未知错误'));
        }
    } catch (e) {
        console.error('调度请求失败:', e);
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
                <div class="metric">成本: <span class="metric-value">¥${sol.metrics.total_cost.toFixed(0)}</span></div>
                <div class="metric">均衡度: <span class="metric-value">${(sol.metrics.balance_score * 100).toFixed(0)}%</span></div>
                <div class="metric">效率: <span class="metric-value">${(sol.metrics.efficiency_score * 100).toFixed(0)}%</span></div>
                <div class="metric">综合: <span class="metric-value">${(sol.metrics.overall_score * 100).toFixed(0)}%</span></div>
            </div>
            ${sol.chain_jobs.length > 0 ? `
                <div style="color:#22c55e;font-size:0.7rem;margin-bottom:0.4rem;">
                    ✨ ${sol.chain_jobs.length} 对连活, 节省 ¥${sol.chain_jobs.reduce((s, c) => s + c.cost_saving, 0).toFixed(0)}
                </div>
            ` : ''}
            <div class="solution-actions">
                <button class="btn-adopt" onclick="adoptSolution('${sol.solution_id}')">📋 分配详细</button>
                <button class="btn-explain" onclick="showExplainModal('${sol.solution_id}')">🧠 AI 解释</button>
            </div>
        </div>
    `).join('');
}

function getEmoji(index) {
    return ['💰', '⚖️', '🏆'][index] || '📋';
}

window.toggleJobSelection = toggleJobSelection;
window.toggleSelectAll = toggleSelectAll;
window.runSchedule = runSchedule;
window.flyToJob = flyToJob;
