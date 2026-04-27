# data/loader.py
"""
数据加载模块
负责从 JSON 文件加载模拟数据
"""

import json
from pathlib import Path
from typing import List, Optional
from interfaces.schemas import Tug, Berth, Job, Rule

# 数据目录
DATA_DIR = Path(__file__).parent

# 模块级缓存 (惰性加载, 显式刷新可传 force=True)
_cache = {"tugs": None, "berths": None, "jobs": None, "rules": None}


def _invalidate_cache():
    for k in _cache:
        _cache[k] = None


def load_tugs(force: bool = False) -> List[Tug]:
    """加载拖轮数据 (带缓存)"""
    if _cache["tugs"] is None or force:
        file_path = DATA_DIR / "tugs.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache["tugs"] = [Tug(**item) for item in data["tugs"]]
    return list(_cache["tugs"])


def load_berths(force: bool = False) -> List[Berth]:
    """加载泊位数据 (带缓存)"""
    if _cache["berths"] is None or force:
        file_path = DATA_DIR / "berths.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache["berths"] = [Berth(**item) for item in data["berths"]]
    return list(_cache["berths"])


def load_jobs(force: bool = False) -> List[Job]:
    """加载任务数据 (带缓存)"""
    if _cache["jobs"] is None or force:
        file_path = DATA_DIR / "jobs.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache["jobs"] = [Job(**item) for item in data["jobs"]]
    return list(_cache["jobs"])


def load_rules(force: bool = False) -> List[Rule]:
    """加载规则数据 (带缓存)"""
    if _cache["rules"] is None or force:
        file_path = DATA_DIR / "rules.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache["rules"] = [Rule(**item) for item in data["rules"]]
    return list(_cache["rules"])


def _build_id_index(items):
    """从对象列表构建 {id: obj} 字典"""
    return {item.id: item for item in items}


def get_tug_by_id(tug_id: str) -> Optional[Tug]:
    """根据ID获取拖轮 (基于缓存索引 O(1))"""
    tugs = load_tugs()
    idx = _build_id_index(tugs)
    return idx.get(tug_id)


def get_berth_by_id(berth_id: str) -> Optional[Berth]:
    """根据ID获取泊位 (基于缓存索引 O(1))"""
    berths = load_berths()
    idx = _build_id_index(berths)
    return idx.get(berth_id)


def get_job_by_id(job_id: str) -> Optional[Job]:
    """根据ID获取任务 (基于缓存索引 O(1))"""
    jobs = load_jobs()
    idx = _build_id_index(jobs)
    return idx.get(job_id)


def ensure_db_sync():
    """确保 JSON 数据已同步到 SQLite"""
    from data.database import import_json_to_db
    db_file = DATA_DIR / "cmatss.db"
    if not db_file.exists():
        import_json_to_db()


if __name__ == "__main__":
    # 测试数据加载
    print(f"拖轮数量: {len(load_tugs())}")
    print(f"泊位数量: {len(load_berths())}")
    print(f"任务数量: {len(load_jobs())}")
    print(f"规则数量: {len(load_rules())}")
