"""
TidePredictor — 潮汐预测与缆绳风险预警
基于简谐波模型, 青岛港半日潮参数
"""

import math
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


# 青岛港潮汐谐波参数 (近似值)
A0 = 2.5        # 平均海平面 (m)
AM2 = 1.4       # M2 分潮振幅 (主太阴半日分潮)
AS2 = 0.6       # S2 分潮振幅 (主太阳半日分潮)
PHI_M2 = 1.8    # M2 初始相位 (rad)
PHI_S2 = 0.5    # S2 初始相位 (rad)
T_M2 = 12.42    # M2 周期 (小时)
T_S2 = 12.00    # S2 周期 (小时)

# 缆绳风险阈值
CABLE_LOW_WARN = 1.0    # 低潮警告 (m)
CABLE_LOW_DANGER = 0.5  # 低潮危险 (m)
CABLE_HIGH_WARN = 3.8   # 高潮警告 (m)
CABLE_HIGH_DANGER = 4.2 # 高潮危险 (m)


class TidePoint:
    """单点潮位"""
    def __init__(self, time: datetime, level: float):
        self.time = time
        self.level = round(level, 2)

    @property
    def status(self) -> str:
        if self.level >= CABLE_HIGH_DANGER:
            return "DANGER_HIGH"
        elif self.level >= CABLE_HIGH_WARN:
            return "HIGH"
        elif self.level <= CABLE_LOW_DANGER:
            return "DANGER_LOW"
        elif self.level <= CABLE_LOW_WARN:
            return "LOW"
        return "NORMAL"

    @property
    def cable_risk(self) -> str:
        if self.level >= CABLE_HIGH_DANGER or self.level <= CABLE_LOW_DANGER:
            return "DANGER"
        elif self.level >= CABLE_HIGH_WARN or self.level <= CABLE_LOW_WARN:
            return "WARNING"
        return "SAFE"

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "level": self.level,
            "status": self.status,
            "cable_risk": self.cable_risk,
        }


class TidePredictor:
    """潮汐预测器 (简谐波模型, 含日期相位修正)"""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "tide_data.json"
        # 参考日期: 2025-01-01 的初始相位
        self._ref_date = datetime(2025, 1, 1)

    def _day_angle(self, dt: datetime) -> float:
        """计算日序相位偏移 (弧度)"""
        days = (dt - self._ref_date).days
        return days * 2 * math.pi / 365.25

    def predict(self, dt: datetime) -> TidePoint:
        """预测指定时刻潮位 (含日期相位修正)"""
        t = dt.hour + dt.minute / 60
        day_angle = self._day_angle(dt)
        omega_m2 = 2 * math.pi / T_M2
        omega_s2 = 2 * math.pi / T_S2
        # 每天相位偏移约 50 分钟 (M2 分潮)
        phase_m2 = PHI_M2 + day_angle * (T_M2 / 24.0)
        phase_s2 = PHI_S2 + day_angle * (T_S2 / 24.0)
        level = (A0
                 + AM2 * math.cos(omega_m2 * t + phase_m2)
                 + AS2 * math.cos(omega_s2 * t + phase_s2))
        return TidePoint(dt, level)

    def get_tide_schedule(self, date: str) -> List[dict]:
        """获取指定日期全天潮汐 (每30分钟)"""
        try:
            base = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        points = []
        for minute in range(0, 24 * 60, 30):
            dt = base + timedelta(minutes=minute)
            pt = self.predict(dt)
            points.append(pt.to_dict())

        # 计算高低潮
        extremes = self._find_extremes(points)
        return {
            "date": base.strftime("%Y-%m-%d"),
            "points": points,
            "high_tides": [e for e in extremes if e["type"] == "high"],
            "low_tides": [e for e in extremes if e["type"] == "low"],
            "max_level": max(p["level"] for p in points),
            "min_level": min(p["level"] for p in points),
        }

    def get_cable_risk_for_berth(self, tide_level: float,
                                 ship_draft: float = 10.0,
                                 berth_depth: float = 15.0) -> dict:
        """缆绳风险评估"""
        risk = "SAFE"
        detail = "安全"

        if tide_level <= CABLE_LOW_DANGER:
            risk = "DANGER"
            detail = f"潮位过低 ({tide_level:.1f}m), 缆绳松弛风险, 需调整系缆"
        elif tide_level <= CABLE_LOW_WARN:
            risk = "WARNING"
            detail = f"潮位偏低 ({tide_level:.1f}m), 注意缆绳松紧"
        elif tide_level >= CABLE_HIGH_DANGER:
            risk = "DANGER"
            detail = f"潮位过高 ({tide_level:.1f}m), 缆绳过紧风险, 需松缆"
        elif tide_level >= CABLE_HIGH_WARN:
            risk = "WARNING"
            detail = f"潮位偏高 ({tide_level:.1f}m), 注意缆绳受力"

        return {
            "tide_level": tide_level,
            "risk_level": risk,
            "detail": detail,
            "ship_draft": ship_draft,
            "berth_depth": berth_depth,
        }

    def _find_extremes(self, points: List[dict]) -> List[dict]:
        """识别高低潮"""
        extremes = []
        n = len(points)
        for i in range(1, n - 1):
            prev_lvl = points[i - 1]["level"]
            curr_lvl = points[i]["level"]
            next_lvl = points[i + 1]["level"]

            if curr_lvl > prev_lvl and curr_lvl > next_lvl:
                extremes.append({"time": points[i]["time"], "level": curr_lvl, "type": "high"})
            elif curr_lvl < prev_lvl and curr_lvl < next_lvl:
                extremes.append({"time": points[i]["time"], "level": curr_lvl, "type": "low"})
        return extremes

    def is_low_tide_period(self, dt: datetime, threshold: float = 1.0) -> bool:
        """判断是否为低潮期 (潮位 < threshold)"""
        pt = self.predict(dt)
        return pt.level < threshold


# 全局单例
tide_predictor = TidePredictor()
