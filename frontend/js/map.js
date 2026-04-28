/**
 * CMATSS 拖轮调度系统 - 地图模块
 * Leaflet 地图渲染、拖轮/泊位标记、连活连线、方案高亮
 */

async function loadTugs() {
    try {
        const resp = await fetch(`${API_BASE}/api/tugs`);
        const data = await resp.json();
        _cachedTugs = data.data;
        if (typeof map !== 'undefined' && map) renderTugsOnMap(data.data);
    } catch (e) {
        console.error('[加载] 拖轮数据失败:', e);
    }
}

async function loadBerths() {
    try {
        const resp = await fetch(`${API_BASE}/api/berths`);
        const data = await resp.json();
        data.data.forEach(b => { berthPositions[b.id] = b.position; });
        _cachedBerths = data.data;
        if (typeof map !== 'undefined' && map) renderBerthsOnMap(data.data);
    } catch (e) {
        console.error('[加载] 泊位数据失败:', e);
    }
}

function renderTugsOnMap(tugs) {
    if (!map) return;
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
    if (!map) return;
    berths.forEach(berth => {
        const marker = L.marker([berth.position.lat, berth.position.lng], {
            icon: L.divIcon({
                className: 'berth-icon',
                html: `<div style="background:#1a3a5c;color:#e6f0ff;padding:2px 6px;border-radius:4px;font-size:10px;border:1px solid #1890ff;">${berth.name}</div>`,
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

function adoptSolution(solutionId) {
    const solution = currentSolutions.find(s => s.solution_id === solutionId);
    if (!solution) return;

    adoptedSolutionId = solutionId;
    clearAdoption();

    highlightAssignedTugs(solution.assignments);
    drawChainLines(solution.chain_jobs || []);
    showAssignmentDetails(solution);

    speakTugAssignment(solution);

    document.querySelectorAll('.solution-card').forEach(c => c.classList.remove('adopted'));
    const card = document.querySelector(`.solution-card[data-id="${solutionId}"]`);
    if (card) card.classList.add('adopted');
}

function clearAdoption() {
    adoptedSolutionId = null;

    highlightedRestore.forEach(fn => fn());
    highlightedRestore = [];

    chainLayers.forEach(layer => { if (map) map.removeLayer(layer); });
    chainLayers = [];

    closeViolationModal();

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
        const polyline = L.polyline(latlngs, {
            color: '#22c55e',
            weight: 3,
            opacity: 0.85,
            dashArray: '10, 8',
            lineCap: 'round'
        }).addTo(map);

        const el = polyline.getElement();
        if (el) el.style.animation = 'chainDashMove 1s linear infinite';

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
}

window.adoptSolution = adoptSolution;
window.clearAdoption = clearAdoption;
