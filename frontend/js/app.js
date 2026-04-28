/**
 * CMATSS 拖轮调度系统 - 入口模块
 * 全局状态、导航切换、初始化编排
 */
const API_BASE = '';

// 全局状态
let map = null;
let mapInitialized = false;
let tugMarkers = {};
let berthMarkers = {};
let berthPositions = {};
let jobBerthMap = {};
let selectedJobs = [];
let currentSolutions = [];
let adoptedSolutionId = null;
let chainLayers = [];
let highlightedRestore = [];
let allJobIds = [];
let voiceEnabled = false;
// 缓存拖轮/泊位数据供懒加载地图使用
let _cachedTugs = null;
let _cachedBerths = null;

document.addEventListener('DOMContentLoaded', () => {
    // 不再自动 initMap() — 地图在作业助手视图首次激活时初始化
    loadData();
    bindEvents();
    initVoice();
    // 默认激活工作台
    switchNav('workbench');
});

function switchNav(view) {
    // 更新导航项
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-view="${view}"]`);
    if (navItem) navItem.classList.add('active');

    // 切换视图容器
    document.querySelectorAll('.view-container').forEach(el => el.classList.remove('active'));
    const container = document.getElementById(`view-${view}`);
    if (container) container.classList.add('active');

    // 延迟初始化地图（首次切换到作业助手视图时）
    if (view === 'assistant') {
        if (!mapInitialized) {
            mapInitialized = true;
            initMapLazy();
        } else if (map) {
            setTimeout(() => map.invalidateSize(), 200);
        }
    }
}

function initMapLazy() {
    const mapEl = document.getElementById('map');
    if (!mapEl || mapEl.offsetParent === null) {
        // 容器可能因动画不可见, 重试
        setTimeout(initMapLazy, 300);
        return;
    }
    map = L.map('map').setView([36.067, 120.385], 14);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // 渲染已缓存的拖轮和泊位
    if (_cachedTugs) renderTugsOnMap(_cachedTugs);
    if (_cachedBerths) renderBerthsOnMap(_cachedBerths);
}

function initMap() {
    // 兼容旧调用: 若 map 未初始化则跳过 (由 initMapLazy 接管)
    if (!mapInitialized) return;
}

async function loadData() {
    try {
        await Promise.all([
            loadTugs(),
            loadBerths(),
            loadJobs(),
            loadDashboard()
        ]);
    } catch (e) {
        console.error('数据加载失败:', e);
    }
}

function bindEvents() {
    const scheduleBtn = document.getElementById('schedule-btn');
    if (scheduleBtn) scheduleBtn.addEventListener('click', runSchedule);

    const refreshBtn = document.getElementById('refresh-jobs');
    if (refreshBtn) refreshBtn.addEventListener('click', loadJobs);

    const selectAllBtn = document.getElementById('select-all-btn');
    if (selectAllBtn) selectAllBtn.addEventListener('click', toggleSelectAll);
}

// 视图切换 (兼容旧的三列视图)
function switchView(view) {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.view-btn[data-view="${view}"]`);
    if (btn) btn.classList.add('active');

    const leftPanel = document.querySelector('.left-panel');
    const mapContainer = document.querySelector('.map-container');
    const rightPanel = document.querySelector('.right-panel');
    const mainContent = document.querySelector('.main-content');

    if (!leftPanel || !mapContainer || !rightPanel || !mainContent) return;

    leftPanel.style.display = '';
    mapContainer.style.display = '';
    rightPanel.style.display = '';
    mainContent.style.gridTemplateColumns = '280px 1fr 320px';

    if (view === 'map') {
        leftPanel.style.display = 'none';
        rightPanel.style.display = 'none';
        mainContent.style.gridTemplateColumns = '1fr';
        setTimeout(() => map && map.invalidateSize(), 100);
    } else if (view === 'solutions') {
        leftPanel.style.display = 'none';
        mainContent.style.gridTemplateColumns = '1fr 320px';
        setTimeout(() => map && map.invalidateSize(), 100);
    }
}

window.switchNav = switchNav;
window.switchView = switchView;
