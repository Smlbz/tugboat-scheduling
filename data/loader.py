# data/loader.py
"""
数据加载模块
负责从 JSON 文件加载模拟数据
"""

import json
from pathlib import Path
from typing import List
from interfaces.schemas import Tug, Berth, Job, Rule

# 数据目录
DATA_DIR = Path(__file__).parent


def load_tugs() -> List[Tug]:
    """加载拖轮数据"""
    file_path = DATA_DIR / "tugs.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Tug(**item) for item in data["tugs"]]


def load_berths() -> List[Berth]:
    """加载泊位数据"""
    file_path = DATA_DIR / "berths.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Berth(**item) for item in data["berths"]]


def load_jobs() -> List[Job]:
    """加载任务数据"""
    file_path = DATA_DIR / "jobs.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Job(**item) for item in data["jobs"]]


def load_rules() -> List[Rule]:
    """加载规则数据"""
    file_path = DATA_DIR / "rules.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Rule(**item) for item in data["rules"]]


def get_tug_by_id(tug_id: str) -> Tug | None:
    """根据ID获取拖轮"""
    tugs = load_tugs()
    for tug in tugs:
        if tug.id == tug_id:
            return tug
    return None


def get_berth_by_id(berth_id: str) -> Berth | None:
    """根据ID获取泊位"""
    berths = load_berths()
    for berth in berths:
        if berth.id == berth_id:
            return berth
    return None


def get_job_by_id(job_id: str) -> Job | None:
    """根据ID获取任务"""
    jobs = load_jobs()
    for job in jobs:
        if job.id == job_id:
            return job
    return None


if __name__ == "__main__":
    # 测试数据加载
    print(f"拖轮数量: {len(load_tugs())}")
    print(f"泊位数量: {len(load_berths())}")
    print(f"任务数量: {len(load_jobs())}")
    print(f"规则数量: {len(load_rules())}")
