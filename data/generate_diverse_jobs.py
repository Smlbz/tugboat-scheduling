"""
生成多样化任务数据 - 替代原有集中数据
产出 80 任务, 跨全天 06:00-03:00, 内含连活机会
"""
import json, random
from datetime import datetime, timedelta

random.seed(42)

SHIPS = [
    ("散货轮希望","散货船"),("散货轮发展","散货船"),("散货轮东方","散货船"),("散货轮振兴","散货船"),("散货轮远航","散货船"),
    ("客轮明珠","杂货船"),("客轮友谊","杂货船"),("客轮和谐","杂货船"),
    ("集装箱快运","集装箱船"),("集装箱先锋","集装箱船"),("集装箱领航","集装箱船"),("集装箱远航","集装箱船"),
    ("油轮安全","油船"),("油轮能源","油船"),("油轮海洋","油船"),("油轮奋进","油船"),
    ("化工运输1号","油船"),("化工运输2号","油船"),("LNG运输船","油船"),
    ("工程船建设","杂货船"),("工程船奋进","杂货船"),("工程船开拓","杂货船"),
    ("货轮诚信","杂货船"),("货轮卓越","杂货船"),("货轮辉煌","杂货船"),("远洋巨轮号","杂货船"),
    ("渔船丰收","杂货船"),("渔船远航","杂货船"),("渔船兴旺","杂货船"),
]

JOB_TYPES = ["BERTHING","UNBERTHING","SHIFTING","ESCORT"]
BERTHS = ["B001","B002","B003","B004","B005","B006","B007","B008","B009","B010"]

SPECIAL_REQ = [
    [], ["夜间作业"], ["禁止老旧拖轮"], ["需要有危化品作业资质"],
    ["需要最高马力拖轮"], ["需要有危化品作业资质","禁止老旧拖轮"],
]

def make_dt(h, m, day_offset=0):
    d = datetime(2025, 12, 11) + timedelta(days=day_offset)
    return d.replace(hour=h, minute=m, second=0)

jobs = []
used_ships = set()
ship_list_idx = 0

def next_ship():
    global ship_list_idx
    s = SHIPS[ship_list_idx % len(SHIPS)]
    ship_list_idx += 1
    return s

# === 定义 60 个任务的精确时间 ===
# 格式: (小时, 分钟, 持续分钟, 泊位倾向, 描述)
slots = [
    # --- 清晨 (06:00-08:00) ---
    (6, 0, 90, "B001", "清晨靠泊"),
    (6, 15, 60, "B002", "清晨护航"),
    (6, 30, 120, "B006", "早班离泊"),
    (7, 0, 60, "B003", "移泊"),
    (7, 30, 90, "B005", "护航"),
    (7, 45, 60, "B004", "清晨离泊"),
    # --- 上午 (08:00-11:30) ---
    (8, 0, 120, "B001", "上午靠泊"),
    (8, 30, 90, "B002", "护航"),
    (9, 0, 180, "B007", "大型船靠泊"),  # 长任务
    (9, 15, 60, "B009", "移泊"),
    (10, 0, 90, "B003", "护航"),
    (10, 0, 120, "B004", "离泊"),
    (10, 30, 60, "B005", "移泊"),
    (11, 0, 90, "B006", "护航"),
    (11, 30, 60, "B001", "午前靠泊"),
    # --- 午后高峰 (13:00-17:00) ---
    (13, 0, 120, "B008", "午后护航"),
    (13, 0, 90, "B003", "靠泊"),
    (13, 30, 60, "B004", "移泊"),
    (13, 45, 120, "B005", "离泊"),
    (14, 0, 180, "B007", "大型船作业"),
    (14, 0, 90, "B006", "护航"),
    (14, 30, 60, "B002", "移泊"),
    (15, 0, 120, "B001", "下午离泊"),
    (15, 0, 90, "B009", "护航"),
    (15, 30, 60, "B004", "短移泊"),
    (15, 45, 120, "B003", "靠泊"),
    (16, 0, 90, "B010", "董家口护航"),
    (16, 0, 60, "B006", "移泊"),
    (16, 30, 120, "B005", "离泊"),
    # --- 傍晚 (17:00-19:30) ---
    (17, 0, 90, "B002", "傍晚护航"),
    (17, 15, 60, "B008", "移泊"),
    (17, 45, 90, "B001", "傍晚靠泊"),
    (18, 0, 120, "B003", "离泊"),
    (18, 30, 90, "B010", "董家口作业"),
    (18, 45, 60, "B004", "护航"),
    (19, 0, 120, "B005", "夜间靠泊"),
    # --- 夜间 (20:00-23:30) ---
    (20, 0, 90, "B006", "夜间护航"),
    (20, 15, 120, "B009", "夜间离泊"),
    (20, 45, 60, "B002", "夜间移泊"),
    (21, 0, 120, "B001", "夜间作业"),
    (21, 30, 90, "B007", "大型船护航"),
    (22, 0, 120, "B003", "深夜离泊"),
    (22, 0, 90, "B010", "董家口夜间"),
    (22, 30, 60, "B005", "移泊"),
    (23, 0, 90, "B004", "深夜护航"),
    (23, 15, 120, "B006", "深夜靠泊"),
    (23, 45, 60, "B008", "深夜移泊"),
    # --- 跨天凌晨 (00:00-02:00) ---
    (0, 0, 90, "B001", "凌晨护航", 1),
    (0, 15, 60, "B002", "凌晨移泊", 1),
    (0, 45, 120, "B003", "凌晨靠泊", 1),
    (1, 0, 90, "B004", "凌晨作业", 1),
    (1, 30, 60, "B010", "董家口凌晨", 1),
    (2, 0, 60, "B005", "凌晨收尾", 1),
    (6, 45, 60, "B008", "老港区清晨", 0),
    (9, 0, 90, "B010", "董家口日间", 0),
    (11, 0, 60, "B009", "上午短移泊", 0),
    (22, 30, 90, "B007", "大型船深夜", 0),
    # --- 新增 20 任务填充分布 (以下) ---
    (5, 30, 60, "B005", "黎明护航"),
    (5, 45, 90, "B001", "黎明靠泊"),
    (6, 10, 60, "B009", "清晨移泊"),
    (7, 15, 90, "B007", "清晨大型作业"),
    (8, 15, 60, "B004", "早间移泊"),
    (9, 45, 90, "B006", "上午护航"),
    (10, 15, 60, "B008", "老港区作业"),
    (11, 15, 90, "B005", "午前离泊"),
    (12, 0, 60, "B001", "午间短任务"),
    (12, 30, 90, "B003", "午间护航"),
    (13, 15, 60, "B009", "午后移泊"),
    (14, 15, 90, "B004", "下午护航"),
    (15, 15, 60, "B002", "移泊"),
    (16, 15, 90, "B010", "董家口下午"),
    (17, 30, 60, "B003", "傍晚移泊"),
    (19, 15, 90, "B009", "晚班护航"),
    (20, 30, 60, "B004", "夜间移泊"),
    (21, 15, 90, "B006", "夜间护航"),
    (23, 30, 60, "B010", "董家口深夜"),
    (0, 30, 90, "B007", "凌晨大型作业", 1),
]

# === 额外制造明确连活对 ===
# 连活对1: JOB 结束10:00, 下个10:30同泊位
# 连活对2: JOB 结束14:00, 下个14:30近泊位
chain_pairs = [
    (10, 0, 60, "B003", "连活短任务A"),
    (11, 0, 60, "B003", "连活续接B"),  # gap=0, 同泊位 → 理想连活
    (14, 0, 60, "B006", "连活C"),
    (15, 0, 60, "B006", "连活D"),       # gap=0, 同泊位 → 理想连活
]

for h, m, dur, berth, desc, *rest in slots:
    day_off = rest[0] if rest else 0
    ship_name, ship_type = next_ship()
    start = make_dt(h, m, day_off)
    end = start + timedelta(minutes=dur)

    is_night = h >= 22 or h < 6
    is_high_risk = random.random() < 0.25 or ship_type == "油船"
    tug_count = random.choices([1,2,3,4], weights=[5,50,30,15])[0]
    if berth == "B007":
        tug_count = max(tug_count, 3)
        is_high_risk = True

    hp = random.choice([4000,5000,5200,6000,7000,8000])
    reqs = random.choice(SPECIAL_REQ)
    if is_night:
        reqs = list(set(reqs + ["夜间作业"]))

    jobs.append({
        "id": "",  # 后面重编号
        "job_type": random.choice(JOB_TYPES),
        "ship_name": ship_name,
        "ship_length": random.randint(100, 300),
        "ship_tonnage": random.randint(10000, 75000),
        "target_berth_id": berth,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "required_horsepower": hp * tug_count,
        "required_tug_count": tug_count,
        "priority": random.choices([1,2,3,4,5,6,7,8,9,10], weights=[2,3,5,8,15,12,10,8,5,2])[0],
        "is_high_risk": is_high_risk,
        "special_requirements": reqs,
        "ship_type": ship_type,
    })

# 插入连活对
for h, m, dur, berth, desc in chain_pairs:
    ship_name, ship_type = next_ship()
    start = make_dt(h, m)
    end = start + timedelta(minutes=dur)
    jobs.append({
        "id": "",
        "job_type": "SHIFTING",
        "ship_name": ship_name,
        "ship_length": random.randint(100, 300),
        "ship_tonnage": random.randint(10000, 75000),
        "target_berth_id": berth,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "required_horsepower": 5000 * 2,
        "required_tug_count": 2,
        "priority": 7,
        "is_high_risk": False,
        "special_requirements": [],
        "ship_type": ship_type,
    })

# 排序 + 重编号
jobs.sort(key=lambda j: j["start_time"])
for i, j in enumerate(jobs):
    j["id"] = f"JOB{i+1:03d}"

# 截断到正好 80
jobs = jobs[:80]
for i, j in enumerate(jobs):
    j["id"] = f"JOB{i+1:03d}"

# 输出
output = {"jobs": jobs}
out_path = __file__ and "jobs.json" or "jobs.json"
with open("jobs.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# 统计
print(f"生成 {len(jobs)} 任务")
print(f"时间范围: {jobs[0]['start_time']} ~ {jobs[-1]['end_time']}")
print(f"泊位分布: {sorted(set(j['target_berth_id'] for j in jobs))}")

# 连活分析
from datetime import datetime as dt
chain_ok = 0
for i in range(len(jobs)):
    for k in range(i+1, len(jobs)):
        t1 = dt.fromisoformat(jobs[i]["end_time"])
        t2 = dt.fromisoformat(jobs[k]["start_time"])
        gap_h = (t2 - t1).total_seconds() / 3600
        if 0 < gap_h < 2 and jobs[i]["target_berth_id"] == jobs[k]["target_berth_id"]:
            chain_ok += 1
            if chain_ok <= 5:
                print(f"  连活: {jobs[i]['id']}->{jobs[k]['id']} gap={gap_h:.1f}h @{jobs[i]['target_berth_id']}")

print(f"连活对 (同泊位且gap<2h): {chain_ok}")

hour_dist = {}
for j in jobs:
    h = int(j["start_time"][11:13])
    hour_dist[h] = hour_dist.get(h, 0) + 1
print(f"小时分布: {dict(sorted(hour_dist.items()))}")
