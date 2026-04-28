/**
 * CMATSS 拖轮调度系统 - 弹窗模块
 * 违规弹窗、AI 解释弹窗、反事实推演、分配详情面板
 */

function showAssignmentDetails(solution) {
    renderAssignToFixedPanel(solution);
}

function renderAssignToFixedPanel(solution) {
    const container = document.getElementById('planning-assignment-list');
    if (!container) { setTimeout(() => renderAssignToFixedPanel(solution), 100); return; }
    try {
        const byJob = {};
        (solution.assignments || []).forEach(a => { if (!byJob[a.job_id]) byJob[a.job_id] = []; byJob[a.job_id].push(a); });
        const jobTypeMap = { BERTHING: '靠泊', UNBERTHING: '离泊', SHIFTING: '移泊', ESCORT: '护航' };
        let html = '';
        for (const [jobId, assigns] of Object.entries(byJob)) {
            const type = jobTypeMap[assigns[0].job_type] || assigns[0].job_type;
            html += `<div style="padding:0.3rem 0;border-bottom:1px solid var(--border-color);font-size:var(--font-sm);">
                <div style="color:var(--primary-color);font-weight:600;margin-bottom:0.1rem;">${jobId} (${type})</div>`;
            assigns.forEach(a => {
                const dotColor = (tugMarkers[a.tug_id]?.options?.fillColor) || '#22c55e';
                html += `<div style="display:flex;align-items:center;gap:0.4rem;padding:0.1rem 0.35rem;font-size:var(--font-xs);">
                    <span style="width:6px;height:6px;border-radius:50%;background:${dotColor};display:inline-block;"></span>
                    ${a.tug_name} <span style="margin-left:auto;color:var(--text-muted);">${(a.score*100).toFixed(0)}%</span></div>`;
            });
            html += `</div>`;
        }
        if (solution.chain_jobs && solution.chain_jobs.length > 0) {
            const saving = solution.chain_jobs.reduce((s, c) => s + c.cost_saving, 0);
            html += `<div style="padding:0.3rem 0;font-size:var(--font-xs);color:var(--success-color);">⛓️ 连活节省 ¥${saving.toFixed(0)}</div>`;
        }
        html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.2rem;padding:0.3rem 0;font-size:var(--font-xs);color:var(--text-secondary);text-align:center;">
            <div>💰 ¥${solution.metrics.total_cost.toFixed(0)}</div>
            <div>⚖️ ${(solution.metrics.balance_score*100).toFixed(0)}%</div>
            <div>⚡ ${(solution.metrics.efficiency_score*100).toFixed(0)}%</div>
            <div>🏆 ${(solution.metrics.overall_score*100).toFixed(0)}%</div>
        </div>`;
        container.innerHTML = html;
    } catch (e) { console.error('分配详情渲染失败:', e); container.innerHTML = '<div class="empty-state">渲染失败</div>'; }
}

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

    requestAnimationFrame(() => overlay.classList.add('visible'));
}

function closeViolationModal() {
    const overlay = document.getElementById('violation-modal');
    if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
    }
}

async function showExplainModal(solutionId) {
    try {
        if (!Array.isArray(currentSolutions) || currentSolutions.length === 0) {
            throw new Error('当前没有可用的调度方案数据，请先执行智能调度');
        }

        closeExplainModal();
        const solution = currentSolutions.find(s => s.solution_id === solutionId);
        if (!solution) {
            throw new Error('未找到方案 ' + solutionId + ' 的数据，请重新调度');
        }
        const name = solution.name ?? '未知方案';

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

        try {
            const resp = await fetch(`${API_BASE}/api/explain`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ solution_id: solutionId })
            });
            const data = await resp.json();
            const text = data.explanation || '无法生成解释';
            const el = document.getElementById('explain-text');
            if (el) el.textContent = text;
        } catch (e) {
            const el = document.getElementById('explain-text');
            if (el) el.textContent = '解释服务不可用: ' + e.message;
        }
    } catch (e) {
        console.error('[AI解释] 错误:', e);
        alert('AI解释暂不可用: ' + e.message);
    }
}

function closeExplainModal() {
    const overlay = document.getElementById('explain-modal');
    if (overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
    }
}

async function runCounterfactual(solutionId) {
    try {
        const textEl = document.getElementById('counterfactual-text');
        if (!textEl) return;
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

async function checkComplianceForAssignment(tugId, jobId) {
    try {
        const resp = await fetch(`${API_BASE}/api/compliance/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tug_id: tugId, job_id: jobId })
        });
        const data = await resp.json();
        showViolationModal('合规检查结果', data);
        return data;
    } catch (e) {
        showViolationModal('合规检查失败', [e.message || '无法连接到服务器']);
        return null;
    }
}

// window 挂载
window.showViolationModal = showViolationModal;
window.closeViolationModal = closeViolationModal;
window.showExplainModal = showExplainModal;
window.closeExplainModal = closeExplainModal;
window.runCounterfactual = runCounterfactual;
window.checkComplianceForAssignment = checkComplianceForAssignment;
