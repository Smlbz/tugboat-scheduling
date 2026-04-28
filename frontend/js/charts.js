/**
 * CMATSS 拖轮调度系统 - 图表模块
 * ECharts 可视化: 雷达图、趋势图、柱状图、环形图
 */

const MOCK_TREND = (() => {
    const times = [], values = [];
    for (let i = 0; i < 24; i++) {
        times.push(`${String(i).padStart(2, '0')}:00`);
        values.push(Math.floor(28 + Math.sin(i / 4) * 5 + (Math.random() - 0.5) * 3));
    }
    return { times, values };
})();

// 图表实例缓存 + ResizeObserver
const _chartInstances = [];
function observeResize(container, chart) {
    _chartInstances.push(chart);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(container);
    // 也绑 window resize 作为后备
    window.addEventListener('resize', () => chart.resize());
}

function renderRadarChart(solutions) {
    const container = document.getElementById('radar-chart');
    if (!container || !solutions || solutions.length === 0) return;

    const chart = echarts.init(container, 'dark');
    observeResize(container, chart);

    const maxCost = Math.max(...solutions.map(s => s.metrics.total_cost)) * 1.5;
    const colors = ['#1890ff', '#52c41a', '#fa8c16'];
    const option = {
        backgroundColor: 'transparent',
        color: colors,
        legend: {
            data: solutions.map(s => s.name),
            bottom: 0,
            textStyle: { color: '#94a3b8', fontSize: 9 },
            itemWidth: 12,
            itemHeight: 8
        },
        radar: {
            indicator: [
                { name: '成本(反向)', max: maxCost },
                { name: '均衡度', max: 1 },
                { name: '效率', max: 1 },
                { name: '综合', max: 1 }
            ],
            center: ['50%', '48%'],
            radius: '55%',
            shape: 'polygon',
            splitArea: { areaStyle: { color: ['rgba(51,65,85,0.3)', 'rgba(30,41,59,0.3)'] } },
            axisLine: { lineStyle: { color: 'rgba(71,85,105,0.4)' } },
            axisName: { color: '#94a3b8', fontSize: 9 }
        },
        series: [{
            type: 'radar',
            data: solutions.map((s, i) => ({
                name: s.name,
                value: [
                    maxCost - s.metrics.total_cost,
                    s.metrics.balance_score,
                    s.metrics.efficiency_score,
                    s.metrics.overall_score
                ],
                lineStyle: { width: 2 },
                areaStyle: { opacity: 0.08 }
            })),
            symbol: 'circle',
            symbolSize: 4,
            label: { show: false }
        }]
    };
    chart.setOption(option);
}

function renderDashboardCharts(dashboardData) {
    renderTrendChart();
    renderBarChart();
    renderRingChart(dashboardData.fatigue_distribution);
}

function renderTrendChart() {
    const container = document.getElementById('trend-chart');
    if (!container) return;

    const chart = echarts.init(container, 'dark');
    observeResize(container, chart);

    const option = {
        backgroundColor: 'transparent',
        grid: { left: '10%', right: '5%', bottom: '18%', top: '8%' },
        xAxis: {
            type: 'category',
            data: MOCK_TREND.times.filter((_, i) => i % 6 === 0),
            axisLabel: { color: '#8896aa', fontSize: 7, interval: 0 },
            axisLine: { show: false },
            splitLine: { show: false }
        },
        yAxis: {
            type: 'value',
            min: 20, max: 40,
            splitLine: { lineStyle: { color: 'rgba(71,85,105,0.15)' } },
            axisLabel: { color: '#8896aa', fontSize: 7 },
            axisLine: { show: false }
        },
        series: [{
            type: 'line', data: MOCK_TREND.values,
            smooth: true, showSymbol: false,
            lineStyle: { color: '#1890ff', width: 2 },
            areaStyle: { color: 'rgba(24,144,255,0.12)' }
        }]
    };
    chart.setOption(option);
}

function renderBarChart() {
    const container = document.getElementById('bar-chart');
    if (!container) return;

    const jobCards = document.querySelectorAll('.job-card');
    const typeMap = { BERTHING: 0, UNBERTHING: 0, SHIFTING: 0, ESCORT: 0 };
    jobCards.forEach(card => {
        const typeEl = card.querySelector('.job-type');
        if (!typeEl) return;
        const label = typeEl.textContent;
        for (const [key, val] of Object.entries({ BERTHING: '靠泊', UNBERTHING: '离泊', SHIFTING: '移泊', ESCORT: '护航' })) {
            if (val === label) typeMap[key]++;
        }
    });

    const chart = echarts.init(container, 'dark');
    observeResize(container, chart);

    const option = {
        backgroundColor: 'transparent',
        grid: { left: '8%', right: '5%', bottom: '18%', top: '8%' },
        xAxis: {
            type: 'category',
            data: ['靠泊', '离泊', '移泊', '护航'],
            axisLabel: { color: '#8896aa', fontSize: 7, fontWeight: 600 },
            axisLine: { show: false }
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(71,85,105,0.15)' } },
            axisLabel: { color: '#8896aa', fontSize: 7 },
            axisLine: { show: false }
        },
        series: [{
            type: 'bar',
            data: [
                { value: typeMap.BERTHING, itemStyle: { color: '#52c41a' } },
                { value: typeMap.UNBERTHING, itemStyle: { color: '#fa8c16' } },
                { value: typeMap.SHIFTING, itemStyle: { color: '#1890ff' } },
                { value: typeMap.ESCORT, itemStyle: { color: '#7c3aed' } }
            ],
            barWidth: '50%',
            label: { show: true, position: 'top', color: '#e6f0ff', fontSize: 8 }
        }]
    };
    chart.setOption(option);
}

function renderRingChart(fatigueDist) {
    const container = document.getElementById('ring-chart');
    if (!container || !fatigueDist) return;

    const total = (fatigueDist.GREEN || 0) + (fatigueDist.YELLOW || 0) + (fatigueDist.RED || 0);
    const chart = echarts.init(container, 'dark');
    observeResize(container, chart);

    const option = {
        backgroundColor: 'transparent',
        tooltip: { show: false },
        series: [{
            type: 'pie',
            radius: ['40%', '65%'],
            avoidLabelOverlap: false,
            label: {
                show: true, color: '#8896aa', fontSize: 7,
                formatter: (p) => `${p.percent.toFixed(0)}%`
            },
            labelLine: { lineStyle: { color: '#475569' } },
            emphasis: { scale: false },
            data: [
                { value: fatigueDist.GREEN || 0, name: '健康', itemStyle: { color: '#52c41a' } },
                { value: fatigueDist.YELLOW || 0, name: '警告', itemStyle: { color: '#fa8c16' } },
                { value: fatigueDist.RED || 0, name: '锁定', itemStyle: { color: '#ff4d4f' } }
            ]
        }],
        graphic: [{
            type: 'text', left: 'center', top: 'center',
            style: { text: `${total}`, fill: '#e6f0ff', fontSize: 14, fontWeight: 700 },
            z: 100
        }]
    };
    chart.setOption(option);
}
