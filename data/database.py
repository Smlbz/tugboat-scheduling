"""
data/database.py
SQLite 持久化层 — 存储运行时状态和调度历史
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from config import DB_PATH
from data.loader import load_tugs, load_berths, load_jobs


def get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接 (row_factory, WAL 模式)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """创建所有表 (IF NOT EXISTS)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tugs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            horsepower INTEGER NOT NULL,
            position_lng REAL NOT NULL,
            position_lat REAL NOT NULL,
            berth_id TEXT,
            berth_position TEXT,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            fatigue_value REAL NOT NULL DEFAULT 0.0,
            fatigue_level TEXT NOT NULL DEFAULT 'GREEN',
            today_work_hours REAL NOT NULL DEFAULT 0.0,
            ship_age INTEGER NOT NULL DEFAULT 0,
            crew_id TEXT
        );

        CREATE TABLE IF NOT EXISTS berths (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            position_lng REAL NOT NULL,
            position_lat REAL NOT NULL,
            max_capacity INTEGER NOT NULL DEFAULT 3,
            berth_type TEXT NOT NULL DEFAULT 'NORMAL'
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            ship_name TEXT NOT NULL,
            ship_type TEXT,
            ship_length REAL,
            ship_tonnage INTEGER,
            target_berth_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            required_horsepower INTEGER NOT NULL,
            required_tug_count INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 5,
            is_high_risk INTEGER NOT NULL DEFAULT 0,
            special_requirements TEXT
        );

        CREATE TABLE IF NOT EXISTS schedule_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            job_ids TEXT NOT NULL,
            solution_id TEXT,
            adopted INTEGER NOT NULL DEFAULT 0,
            metrics TEXT
        );

        CREATE TABLE IF NOT EXISTS tug_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tug_id TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            status TEXT NOT NULL,
            fatigue_value REAL NOT NULL DEFAULT 0.0
        );
    """)

    conn.commit()
    conn.close()


def import_json_to_db():
    """从 JSON 导入数据到 SQLite 表"""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # 导入拖轮数据
    tugs = load_tugs(force=True)
    for tug in tugs:
        cursor.execute(
            """
            INSERT OR REPLACE INTO tugs
            (id, name, horsepower, position_lng, position_lat, berth_id, berth_position,
             status, fatigue_value, fatigue_level, today_work_hours, ship_age, crew_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tug.id,
                tug.name,
                tug.horsepower,
                tug.position.lng,
                tug.position.lat,
                tug.berth_id,
                tug.berth_position if tug.berth_position else None,
                tug.status,
                tug.fatigue_value,
                tug.fatigue_level,
                tug.today_work_hours,
                tug.ship_age,
                tug.crew_id,
            ),
        )

    # 导入泊位数据
    berths = load_berths(force=True)
    for berth in berths:
        cursor.execute(
            """
            INSERT OR REPLACE INTO berths
            (id, name, position_lng, position_lat, max_capacity, berth_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                berth.id,
                berth.name,
                berth.position.lng,
                berth.position.lat,
                berth.max_capacity,
                berth.berth_type,
            ),
        )

    # 导入任务数据
    jobs = load_jobs(force=True)
    for job in jobs:
        cursor.execute(
            """
            INSERT OR REPLACE INTO jobs
            (id, job_type, ship_name, ship_type, ship_length, ship_tonnage,
             target_berth_id, start_time, end_time, required_horsepower,
             required_tug_count, priority, is_high_risk, special_requirements)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.job_type,
                job.ship_name,
                job.ship_type,
                job.ship_length,
                job.ship_tonnage,
                job.target_berth_id,
                job.start_time.isoformat(),
                job.end_time.isoformat(),
                job.required_horsepower,
                job.required_tug_count,
                job.priority,
                1 if job.is_high_risk else 0,
                json.dumps(job.special_requirements, ensure_ascii=False),
            ),
        )

    conn.commit()
    conn.close()


def ensure_db_sync():
    """确保 SQLite 数据库已初始化并同步 JSON 数据"""
    db_file = Path(DB_PATH)
    if not db_file.exists():
        import_json_to_db()


def save_schedule_history(
    job_ids: List[str],
    solution_id: str = "",
    metrics: Optional[Dict[str, Any]] = None,
    adopted: int = 0,
):
    """保存调度历史记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schedule_history (job_ids, solution_id, adopted, metrics) VALUES (?, ?, ?, ?)",
        (
            json.dumps(job_ids, ensure_ascii=False),
            solution_id,
            adopted,
            json.dumps(metrics, ensure_ascii=False) if metrics else None,
        ),
    )
    conn.commit()
    conn.close()


def get_schedule_history(limit: int = 50) -> List[Dict[str, Any]]:
    """查询调度历史 (按 created_at DESC)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM schedule_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
