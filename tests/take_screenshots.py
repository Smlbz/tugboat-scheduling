"""
系统截图脚本 — Playwright v3
拦截API返回mock数据，避免NSGA-II长等待
"""

import sys, os, json, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = Path(__file__).parent.parent / "docs" / "figures" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1440, "height": 960}

# ============ Mock 数据 ============

MOCK_TUGS = {
    "data": [
        {"id": "TUG001", "name": "日港拖16", "position": {"lat": 36.068, "lng": 120.386}, "horsepower": 5000, "status": "AVAILABLE", "fatigue_value": 12.5, "fatigue_level": "RED"},
        {"id": "TUG002", "name": "日港拖30", "position": {"lat": 36.070, "lng": 120.388}, "horsepower": 6000, "status": "AVAILABLE", "fatigue_value": 8.5, "fatigue_level": "YELLOW"},
        {"id": "TUG003", "name": "氢电拖1", "position": {"lat": 36.065, "lng": 120.382}, "horsepower": 4000, "status": "AVAILABLE", "fatigue_value": 3.2, "fatigue_level": "GREEN"},
        {"id": "TUG004", "name": "青港拖30", "position": {"lat": 36.072, "lng": 120.390}, "horsepower": 5200, "status": "AVAILABLE", "fatigue_value": 14.0, "fatigue_level": "RED"},
        {"id": "TUG005", "name": "青港拖1", "position": {"lat": 36.066, "lng": 120.384}, "horsepower": 4800, "status": "AVAILABLE", "fatigue_value": 2.1, "fatigue_level": "GREEN"},
        {"id": "TUG006", "name": "青港拖31", "position": {"lat": 36.071, "lng": 120.389}, "horsepower": 5500, "status": "BUSY", "fatigue_value": 6.0, "fatigue_level": "GREEN"},
        {"id": "TUG007", "name": "亚洲19号", "position": {"lat": 36.064, "lng": 120.381}, "horsepower": 7000, "status": "AVAILABLE", "fatigue_value": 11.2, "fatigue_level": "RED"},
        {"id": "TUG008", "name": "日港拖27", "position": {"lat": 36.069, "lng": 120.387}, "horsepower": 4500, "status": "AVAILABLE", "fatigue_value": 3.8, "fatigue_level": "GREEN"},
        {"id": "TUG009", "name": "日港拖17", "position": {"lat": 36.073, "lng": 120.391}, "horsepower": 5000, "status": "AVAILABLE", "fatigue_value": 9.5, "fatigue_level": "YELLOW"},
        {"id": "TUG010", "name": "新时代", "position": {"lat": 36.067, "lng": 120.383}, "horsepower": 6000, "status": "AVAILABLE", "fatigue_value": 1.5, "fatigue_level": "GREEN"},
        {"id": "TUG011", "name": "日港拖31", "position": {"lat": 36.074, "lng": 120.392}, "horsepower": 4800, "status": "LOCKED_BY_FRMS", "fatigue_value": 13.0, "fatigue_level": "RED"},
        {"id": "TUG012", "name": "日港拖2", "position": {"lat": 36.062, "lng": 120.379}, "horsepower": 4800, "status": "AVAILABLE", "fatigue_value": 5.0, "fatigue_level": "GREEN"},
        {"id": "TUG013", "name": "青港吊2", "position": {"lat": 36.070, "lng": 120.387}, "horsepower": 4000, "status": "AVAILABLE", "fatigue_value": 6.5, "fatigue_level": "GREEN"},
        {"id": "TUG014", "name": "新迎宾", "position": {"lat": 36.066, "lng": 120.384}, "horsepower": 5200, "status": "AVAILABLE", "fatigue_value": 7.2, "fatigue_level": "YELLOW"},
        {"id": "TUG016", "name": "安德", "position": {"lat": 36.072, "lng": 120.390}, "horsepower": 3000, "status": "AVAILABLE", "fatigue_value": 4.0, "fatigue_level": "GREEN"},
        {"id": "TUG017", "name": "日港拖18", "position": {"lat": 36.065, "lng": 120.383}, "horsepower": 5500, "status": "AVAILABLE", "fatigue_value": 9.0, "fatigue_level": "YELLOW"},
        {"id": "TUG018", "name": "安泰", "position": {"lat": 36.071, "lng": 120.389}, "horsepower": 4500, "status": "AVAILABLE", "fatigue_value": 2.5, "fatigue_level": "GREEN"},
        {"id": "TUG020", "name": "新贵宾", "position": {"lat": 36.068, "lng": 120.386}, "horsepower": 6000, "status": "AVAILABLE", "fatigue_value": 3.8, "fatigue_level": "GREEN"},
        {"id": "TUG022", "name": "青港拖2", "position": {"lat": 36.063, "lng": 120.380}, "horsepower": 5000, "status": "AVAILABLE", "fatigue_value": 14.0, "fatigue_level": "RED"},
    ],
    "total": 19
}

MOCK_BERTHS = {
    "data": [
        {"id": "B001", "name": "B001", "position": {"lat": 36.067, "lng": 120.385}, "tugs_stack": []},
        {"id": "B002", "name": "B002", "position": {"lat": 36.069, "lng": 120.388}, "tugs_stack": []},
        {"id": "B003", "name": "B003", "position": {"lat": 36.065, "lng": 120.382}, "tugs_stack": []},
        {"id": "B004", "name": "B004", "position": {"lat": 36.071, "lng": 120.390}, "tugs_stack": []},
        {"id": "B005", "name": "B005", "position": {"lat": 36.063, "lng": 120.380}, "tugs_stack": []},
    ],
    "total": 5
}

MOCK_JOBS = {
    "data": [
        {"id": "JOB001", "ship_name": "MSC 伊斯坦布尔", "job_type": "BERTHING", "target_berth_id": "B005", "required_horsepower": 10400, "start_time": "2026-04-28T05:30:00", "end_time": "2026-04-28T06:30:00"},
        {"id": "JOB002", "ship_name": "散货轮希望", "job_type": "SHIFTING", "target_berth_id": "B001", "required_horsepower": 12000, "start_time": "2026-04-28T05:45:00", "end_time": "2026-04-28T07:15:00"},
        {"id": "JOB003", "ship_name": "散货轮发展", "job_type": "UNBERTHING", "target_berth_id": "B001", "required_horsepower": 5200, "start_time": "2026-04-28T06:00:00", "end_time": "2026-04-28T07:30:00"},
        {"id": "JOB004", "ship_name": "散货轮东方", "job_type": "SHIFTING", "target_berth_id": "B009", "required_horsepower": 16000, "start_time": "2026-04-28T06:10:00", "end_time": "2026-04-28T07:10:00"},
        {"id": "JOB005", "ship_name": "散货轮远航", "job_type": "BERTHING", "target_berth_id": "B002", "required_horsepower": 14000, "start_time": "2026-04-28T06:15:00", "end_time": "2026-04-28T07:15:00"},
        {"id": "JOB006", "ship_name": "货轮辉煌", "job_type": "ESCORT", "target_berth_id": "B006", "required_horsepower": 5000, "start_time": "2026-04-28T06:30:00", "end_time": "2026-04-28T08:30:00"},
        {"id": "JOB007", "ship_name": "集装箱快运", "job_type": "SHIFTING", "target_berth_id": "B007", "required_horsepower": 15600, "start_time": "2026-04-28T06:45:00", "end_time": "2026-04-28T07:45:00"},
        {"id": "JOB008", "ship_name": "散货轮振兴", "job_type": "ESCORT", "target_berth_id": "B003", "required_horsepower": 5000, "start_time": "2026-04-28T07:00:00", "end_time": "2026-04-28T08:00:00"},
        {"id": "JOB009", "ship_name": "客轮明珠", "job_type": "BERTHING", "target_berth_id": "B004", "required_horsepower": 6000, "start_time": "2026-04-28T07:15:00", "end_time": "2026-04-28T08:15:00"},
        {"id": "JOB010", "ship_name": "客轮友谊", "job_type": "UNBERTHING", "target_berth_id": "B001", "required_horsepower": 15600, "start_time": "2026-04-28T07:30:00", "end_time": "2026-04-28T09:30:00"},
        {"id": "JOB011", "ship_name": "远洋巨轮号", "job_type": "BERTHING", "target_berth_id": "B010", "required_horsepower": 5200, "start_time": "2026-04-28T08:00:00", "end_time": "2026-04-28T09:30:00"},
        {"id": "JOB012", "ship_name": "集装箱先锋", "job_type": "UNBERTHING", "target_berth_id": "B009", "required_horsepower": 21000, "start_time": "2026-04-28T08:15:00", "end_time": "2026-04-28T09:15:00"},
        {"id": "JOB013", "ship_name": "集装箱领航", "job_type": "SHIFTING", "target_berth_id": "B003", "required_horsepower": 21000, "start_time": "2026-04-28T08:30:00", "end_time": "2026-04-28T10:00:00"},
        {"id": "JOB014", "ship_name": "集装箱远航", "job_type": "BERTHING", "target_berth_id": "B004", "required_horsepower": 18000, "start_time": "2026-04-28T09:00:00", "end_time": "2026-04-28T11:00:00"},
        {"id": "JOB015", "ship_name": "工程船建设", "job_type": "SHIFTING", "target_berth_id": "B003", "required_horsepower": 10000, "start_time": "2026-04-28T09:15:00", "end_time": "2026-04-28T10:45:00"},
    ],
    "total": 15
}

MOCK_DASHBOARD = {
    "total_tugs": 12,
    "available_tugs": 8,
    "total_jobs": 15,
    "status_distribution": {"AVAILABLE": 8, "BUSY": 1, "LOCKED_BY_FRMS": 3},
    "fatigue_distribution": {"GREEN": 6, "YELLOW": 2, "RED": 4},
    "fatigue_warning_threshold": 7.0,
    "fatigue_lock_threshold": 10.0,
}

MOCK_TIDE = {
    "date": "2026-04-28",
    "points": [
        {"time": "2026-04-28T00:00:00", "level": 2.1, "status": "FALLING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T02:00:00", "level": 0.8, "status": "LOW", "cable_risk": "CAUTION"},
        {"time": "2026-04-28T04:00:00", "level": 1.5, "status": "RISING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T06:00:00", "level": 3.2, "status": "RISING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T08:00:00", "level": 4.5, "status": "HIGH", "cable_risk": "CAUTION"},
        {"time": "2026-04-28T10:00:00", "level": 3.8, "status": "FALLING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T12:00:00", "level": 2.5, "status": "FALLING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T14:00:00", "level": 1.2, "status": "LOW", "cable_risk": "CAUTION"},
        {"time": "2026-04-28T16:00:00", "level": 2.8, "status": "RISING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T18:00:00", "level": 4.0, "status": "HIGH", "cable_risk": "SAFE"},
        {"time": "2026-04-28T20:00:00", "level": 3.5, "status": "FALLING", "cable_risk": "SAFE"},
        {"time": "2026-04-28T22:00:00", "level": 1.8, "status": "FALLING", "cable_risk": "SAFE"},
    ]
}

MOCK_COMPLIANCE = {
    "violation_reason": "拖轮 TUG022 (青港拖2) 疲劳值 14.0 超过锁定阈值 10.0，不允许分配新任务 JOB001",
    "violation_rules": ["R003: 疲劳值≥10 的拖轮禁止分配", "R001: 每艘拖轮连续作业时间不超过 12 小时"],
    "severity": "HIGH"
}

MOCK_SOLUTIONS = {
    "success": True,
    "solutions": [
        {
            "solution_id": "SOL-MOCK-001",
            "name": "省油方案",
            "assignments": [
                {"tug_id": "TUG001", "tug_name": "日港拖16", "job_id": "JOB001", "job_type": "BERTHING", "score": 0.85},
                {"tug_id": "TUG003", "tug_name": "氢电拖1", "job_id": "JOB001", "job_type": "BERTHING", "score": 0.92},
                {"tug_id": "TUG005", "tug_name": "青港拖1", "job_id": "JOB002", "job_type": "UNBERTHING", "score": 0.78},
                {"tug_id": "TUG008", "tug_name": "日港拖27", "job_id": "JOB002", "job_type": "UNBERTHING", "score": 0.81},
                {"tug_id": "TUG010", "tug_name": "新时代", "job_id": "JOB003", "job_type": "SHIFTING", "score": 0.74},
                {"tug_id": "TUG012", "tug_name": "日港拖2", "job_id": "JOB003", "job_type": "SHIFTING", "score": 0.88},
                {"tug_id": "TUG022", "tug_name": "青港拖2", "job_id": "JOB004", "job_type": "BERTHING", "score": 0.65},
                {"tug_id": "TUG004", "tug_name": "青港拖30", "job_id": "JOB004", "job_type": "BERTHING", "score": 0.79},
                {"tug_id": "TUG002", "tug_name": "日港拖30", "job_id": "JOB005", "job_type": "ESCORT", "score": 0.91},
            ],
            "metrics": {"total_cost": 18742, "balance_score": 0.69, "efficiency_score": 0.76, "overall_score": 0.71},
            "chain_jobs": [
                {"job1_id": "JOB001", "job2_id": "JOB005", "interval_hours": 0.8, "distance_nm": 1.2, "cost_saving": 3200}
            ],
            "hidden_tasks": []
        },
        {
            "solution_id": "SOL-MOCK-002",
            "name": "均衡方案",
            "assignments": [
                {"tug_id": "TUG002", "tug_name": "日港拖30", "job_id": "JOB001", "job_type": "BERTHING", "score": 0.83},
                {"tug_id": "TUG006", "tug_name": "青港拖31", "job_id": "JOB001", "job_type": "BERTHING", "score": 0.76},
                {"tug_id": "TUG009", "tug_name": "日港拖17", "job_id": "JOB002", "job_type": "UNBERTHING", "score": 0.72},
                {"tug_id": "TUG011", "tug_name": "日港拖31", "job_id": "JOB002", "job_type": "UNBERTHING", "score": 0.85},
                {"tug_id": "TUG014", "tug_name": "新迎宾", "job_id": "JOB003", "job_type": "SHIFTING", "score": 0.69},
                {"tug_id": "TUG016", "tug_name": "安德", "job_id": "JOB003", "job_type": "SHIFTING", "score": 0.77},
            ],
            "metrics": {"total_cost": 21450, "balance_score": 0.85, "efficiency_score": 0.68, "overall_score": 0.76},
            "chain_jobs": [
                {"job1_id": "JOB001", "job2_id": "JOB005", "interval_hours": 0.8, "distance_nm": 1.2, "cost_saving": 3200},
                {"job1_id": "JOB002", "job2_id": "JOB004", "interval_hours": 1.5, "distance_nm": 2.8, "cost_saving": 1800}
            ],
            "hidden_tasks": []
        },
        {
            "solution_id": "SOL-MOCK-003",
            "name": "综合最优",
            "assignments": [
                {"tug_id": "TUG007", "tug_name": "亚洲19号", "job_id": "JOB001", "job_type": "BERTHING", "score": 0.88},
                {"tug_id": "TUG013", "tug_name": "青港吊2", "job_id": "JOB002", "job_type": "UNBERTHING", "score": 0.71},
                {"tug_id": "TUG018", "tug_name": "安泰", "job_id": "JOB003", "job_type": "SHIFTING", "score": 0.82},
                {"tug_id": "TUG017", "tug_name": "日港拖18", "job_id": "JOB004", "job_type": "BERTHING", "score": 0.79},
                {"tug_id": "TUG020", "tug_name": "新贵宾", "job_id": "JOB005", "job_type": "ESCORT", "score": 0.84},
            ],
            "metrics": {"total_cost": 16580, "balance_score": 0.78, "efficiency_score": 0.85, "overall_score": 0.82},
            "chain_jobs": [],
            "hidden_tasks": []
        }
    ]
}


def save(page, name):
    path = SCREENSHOTS_DIR / f"sc_{name}.png"
    page.screenshot(path=str(path), full_page=False)
    size_kb = path.stat().st_size / 1024
    print(f"  Saved: {path} ({size_kb:.1f} KB)")


# ============ Route handlers ============

def handle_schedule(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_SOLUTIONS))

def handle_tugs(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_TUGS))

def handle_berths(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_BERTHS))

def handle_jobs(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_JOBS))

def handle_dashboard(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_DASHBOARD))

def handle_tide(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_TIDE))

def handle_compliance(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(MOCK_COMPLIANCE))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        # 拦截所有API
        page.route("**/api/schedule", handle_schedule)
        page.route("**/api/tugs", handle_tugs)
        page.route("**/api/berths", handle_berths)
        page.route("**/api/jobs", handle_jobs)
        page.route("**/api/dashboard", handle_dashboard)
        page.route("**/api/tide*", handle_tide)
        page.route("**/api/compliance/check", handle_compliance)

        # #11 GIS地图主界面 → 默认工作台视图
        print("\n[B1] 调度工作台主界面...")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(4)
        save(page, "gis_map_main")

        # #13 动态看板 (工作台视图, KPI + 图表已渲染)
        print("\n[B5] 动态看板...")
        save(page, "dashboard")

        # 选任务
        print("\n[B2] 选任务+调度...")
        job_cards = page.query_selector_all('.job-card')
        print(f"  {len(job_cards)} job cards")
        for card in job_cards[:15]:
            card.click()
            time.sleep(0.05)

        # 点调度
        sched_btn = page.query_selector('#schedule-btn')
        if sched_btn:
            sched_btn.click()
            time.sleep(4)

            # 调度后自动切到方案比选视图
            # #12 Top-3方案对比卡片 (含雷达图)
            print("\n[B3] Top-3方案对比...")
            save(page, "top3_solutions")

            # #16 疲劳预警界面 (切回工作台看疲劳条)
            print("\n[B4] 疲劳预警界面...")
            page.evaluate("switchNav('workbench')")
            time.sleep(1)
            save(page, "fatigue_warning")

        # #14 方案详情+地图路径 (切到作业助手看地图)
        print("\n[B6] 方案详情+地图路径...")
        page.evaluate("switchNav('assistant')")
        time.sleep(2)
        # 采纳方案
        accepted = page.evaluate("""() => {
            const cards = document.querySelectorAll('.solution-card');
            if (!cards.length) return false;
            const sid = cards[0].getAttribute('data-id');
            if (typeof adoptSolution === 'function') {
                adoptSolution(sid);
                return true;
            }
            return false;
        }""")
        print(f"  adoptSolution: {accepted}")
        time.sleep(3)
        save(page, "solution_detail_map")

        # #15 合规检查违规弹窗
        print("\n[B7] 合规检查违规弹窗...")
        page.evaluate("""async () => {
            try {
                const r = await fetch('/api/compliance/check', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tug_id: 'TUG022', job_id: 'JOB001'})
                });
                const d = await r.json();
                if (typeof showViolationModal === 'function')
                    showViolationModal('合规检查结果', d);
            } catch(e) { console.error(e); }
        }""")
        time.sleep(2)
        save(page, "compliance_check")

        # #17 连活任务可视化 (聚焦连活区域)
        print("\n[B8] 连活任务可视化...")
        page.evaluate("""() => {
            if (typeof map === 'undefined' || !map) return 0;
            var bounds = null;
            if (typeof chainLayers !== 'undefined' && chainLayers.length > 0) {
                chainLayers.forEach(function(layer) {
                    if (layer.getLatLng) {
                        var ll = layer.getLatLng();
                        if (!bounds) bounds = L.latLngBounds([ll, ll]);
                        else bounds.extend(ll);
                    }
                });
            }
            if (!bounds) {
                bounds = L.latLngBounds([
                    [36.063, 120.380],
                    [36.074, 120.392]
                ]);
            }
            map.fitBounds(bounds, {padding: [50, 50], maxZoom: 15});
            return bounds.isValid() ? 1 : 0;
        }""")
        time.sleep(2)
        save(page, "chain_visualization")
        browser.close()

    print(f"\nDone! {len(list(SCREENSHOTS_DIR.glob('*.png')))} screenshots")


if __name__ == "__main__":
    main()
