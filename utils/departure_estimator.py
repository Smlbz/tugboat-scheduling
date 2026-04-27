"""
DepartureEstimator — 备车出发时间估算

基于拖轮系统操作流程文档公式:
  提前备车时间 = 航行时间 + 辅助时间(12min) + 提前就位时间(10min)
  航行时间(min) = 距离(海里) / 航速(节) * 60

查表法: 预置青岛港备车时间表精确值
距离法: 任意两点间估算 (8节港内, 10节港外)
"""

import math
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

from utils.tide_predictor import tide_predictor


# ============ 备车时间查表 (来自拖轮备车时间表) ============
# (始发基地, 目标区域) -> 航程海里
BASE_DISTANCES: Dict[Tuple[str, str], float] = {
    ("镰湾河", "63区"): 3.0,
    ("镰湾河", "302浮"): 3.9,
    ("镰湾河", "301浮"): 4.5,
    ("镰湾河", "1#锚地"): 8.7,
    ("镰湾河", "501浮"): 16.5,
    ("镰湾河", "201浮"): 5.7,
    ("镰湾河", "大小公岛引航站"): 20.1,
    ("大港", "101浮"): 3.4,
    ("大港", "201浮"): 3.6,
    ("大港", "302浮"): 5.0,
    ("大港", "63区"): 5.9,
    ("大港", "1#锚地"): 9.5,
    ("大港", "501浮"): 16.5,
    ("大港", "大小公岛引航站"): 20.2,
    ("前湾南港拖轮基地", "63区"): 0.5,
    ("前湾南港拖轮基地", "302浮"): 1.1,
    ("前湾南港拖轮基地", "301浮"): 1.5,
    ("前湾南港拖轮基地", "1#锚地"): 6.0,
    ("前湾南港拖轮基地", "501浮"): 13.6,
    ("前湾南港拖轮基地", "201浮"): 2.8,
    ("前湾南港拖轮基地", "大小公岛引航站"): 17.5,
    ("董家口基地", "119浮"): 19.0,
    ("董家口基地", "131浮"): 12.0,
    ("董家口基地", "141浮"): 7.5,
    ("董家口基地", "P5浮"): 2.5,
}

# 始发基地坐标 (lng, lat) — 用于距离法估算
BASE_POSITIONS: Dict[str, Tuple[float, float]] = {
    "镰湾河": (120.22, 36.01),
    "大港": (120.32, 36.10),
    "前湾南港拖轮基地": (120.30, 36.08),
    "董家口基地": (119.54, 35.37),
}

# 辅助常量
AUX_TIME_MIN = 12       # 辅助时间: 备车+解岸电+解缆+离码头
EARLY_ARRIVAL_MIN = 10  # 提前就位时间
SPEED_KNOTS_IN_PORT = 8    # 港内航速(节)
SPEED_KNOTS_OUTSIDE = 10   # 港外航速(节)


def haversine_nm(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Haversine 公式计算海里距离"""
    R_KM = 6371.0
    d_lng = math.radians(lng2 - lng1)
    d_lat = math.radians(lat2 - lat1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R_KM * c / 1.852  # km to nautical miles


class DepartureCalcResult:
    """备车时间计算结果"""
    def __init__(self,
                 distance_nm: float,
                 travel_time_min: float,
                 aux_time_min: float = AUX_TIME_MIN,
                 early_arrival_min: float = EARLY_ARRIVAL_MIN,
                 prep_time_min: float = None,
                 base_name: str = None,
                 target_name: str = None,
                 is_low_tide: bool = False,
                 note: str = None):
        self.distance_nm = round(distance_nm, 1)
        self.travel_time_min = round(travel_time_min)
        self.aux_time_min = aux_time_min
        self.early_arrival_min = early_arrival_min
        if prep_time_min is None:
            prep_time_min = travel_time_min + aux_time_min + early_arrival_min
        self.prep_time_min = round(prep_time_min)
        self.base_name = base_name
        self.target_name = target_name
        self.is_low_tide = is_low_tide
        self.note = note

    @property
    def departure_time(self) -> str:
        """返回 '提前XX分钟' 描述"""
        return f"提前{self.prep_time_min}分钟"

    def estimate_departure(self, job_start_time: datetime) -> datetime:
        """根据任务开始时间反推最晚出发时间"""
        return job_start_time - timedelta(minutes=self.prep_time_min)

    def to_dict(self) -> dict:
        d = {
            "distance_nm": self.distance_nm,
            "travel_time_min": self.travel_time_min,
            "aux_time_min": self.aux_time_min,
            "early_arrival_min": self.early_arrival_min,
            "prep_time_min": self.prep_time_min,
            "departure_time_desc": self.departure_time,
        }
        if self.base_name:
            d["base_name"] = self.base_name
        if self.target_name:
            d["target_name"] = self.target_name
        if self.note:
            d["note"] = self.note
        return d


class DepartureEstimator:
    """备车时间估算器"""

    def estimate_by_table(self, base_name: str, target_name: str,
                          is_low_tide: bool = False,
                          from_75_area: bool = False) -> Optional[DepartureCalcResult]:
        """查表法: 根据始发基地和目标区域查备车时间表"""
        distance = BASE_DISTANCES.get((base_name, target_name))
        if distance is None:
            return None

        travel_min = distance / SPEED_KNOTS_IN_PORT * 60
        prep_min = travel_min + AUX_TIME_MIN + EARLY_ARRIVAL_MIN

        # 特殊规则
        note_parts = []
        if is_low_tide:
            prep_min += 5
            note_parts.append("低潮+5分钟(放舷梯)")
        if from_75_area:
            prep_min -= 15
            note_parts.append("75区出发-15分钟")

        return DepartureCalcResult(
            distance_nm=distance,
            travel_time_min=travel_min,
            prep_time_min=prep_min,
            base_name=base_name,
            target_name=target_name,
            is_low_tide=is_low_tide,
            note="; ".join(note_parts) if note_parts else None,
        )

    def estimate_by_position(self,
                             tug_lng: float, tug_lat: float,
                             target_lng: float, target_lat: float,
                             speed_knots: float = SPEED_KNOTS_IN_PORT,
                             is_low_tide: bool = False,
                             from_75_area: bool = False) -> DepartureCalcResult:
        """距离法: 根据坐标计算备车时间"""
        distance = haversine_nm(tug_lng, tug_lat, target_lng, target_lat)
        travel_min = distance / speed_knots * 60
        prep_min = travel_min + AUX_TIME_MIN + EARLY_ARRIVAL_MIN

        note_parts = []
        if is_low_tide:
            prep_min += 5
            note_parts.append("低潮+5分钟(放舷梯)")
        if from_75_area:
            prep_min -= 15
            note_parts.append("75区出发-15分钟")

        return DepartureCalcResult(
            distance_nm=distance,
            travel_time_min=travel_min,
            prep_time_min=prep_min,
            is_low_tide=is_low_tide,
            note="; ".join(note_parts) if note_parts else None,
        )

    def estimate_for_tug_job(self,
                             tug_lng: float, tug_lat: float,
                             tug_name: str,
                             target_lng: float, target_lat: float,
                             target_name: str,
                             is_low_tide: bool = False,
                             job_start_time: Optional[datetime] = None) -> DepartureCalcResult:
        """综合估算: 优先查表, 回退距离法
           is_low_tide=None 时根据 job_start_time 自动检测潮汐"""
        # 自动检测低潮
        if is_low_tide is None and job_start_time is not None:
            is_low_tide = tide_predictor.is_low_tide_period(job_start_time)
        # 尝试匹配始发基地
        base_name = self._match_base(tug_lng, tug_lat)
        target_area = self._match_target(target_lng, target_lat, target_name)

        result = None
        if base_name and target_area:
            result = self.estimate_by_table(base_name, target_area, is_low_tide)

        if result is None:
            result = self.estimate_by_position(tug_lng, tug_lat, target_lng, target_lat, is_low_tide=is_low_tide)
            if base_name:
                result.base_name = base_name
            if target_area:
                result.target_name = target_area
            else:
                result.target_name = target_name

        return result

    def _match_base(self, lng: float, lat: float) -> Optional[str]:
        """匹配最近始发基地"""
        best_base = None
        best_dist = float("inf")
        for base, (blng, blat) in BASE_POSITIONS.items():
            d = haversine_nm(lng, lat, blng, blat)
            if d < best_dist:
                best_dist = d
                best_base = base
        return best_base if best_dist < 10 else None  # 10海里内才匹配

    def _match_target(self, lng: float, lat: float, name: str) -> Optional[str]:
        """将泊位名映射到备车时间表目标区域"""
        # 查表目标区域列表
        table_targets = set(t for (_, t) in BASE_DISTANCES.keys())
        # 检查泊位名是否直接匹配
        for t in table_targets:
            if t in name or name in t:
                return t
        # 按坐标最近匹配
        # 这里简化: 把B001-B010映射到63区(青岛港主港池)
        if 120.3 < lng < 120.5 and 36.0 < lat < 36.2:
            return "63区"
        if lng < 120.0:  # 董家口区域
            return "119浮"
        return None


# 全局单例
departure_estimator = DepartureEstimator()
