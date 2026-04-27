# agents/fatigue_agent.py
"""
SlaveAgent3 - 疲劳度管理智能体
负责人: 成员C

职责:
- 疲劳模型 BFM (Bio-mathematical Fatigue Model) 实现
- 实时疲劳状态维护
- 连续工作惩罚
- 休息恢复机制
- 状态锁管理
"""

from typing import Dict, List
from agents.base_agent import BaseAgent
from interfaces.schemas import FatigueCheckResponse, FatigueLevel, TugStatus
from data.loader import load_tugs
from config import (
    FATIGUE_WARNING_THRESHOLD,
    FATIGUE_LOCK_THRESHOLD,
    FATIGUE_DAY_MULTIPLIER,
    FATIGUE_NIGHT_MULTIPLIER,
    NIGHT_START_HOUR,
    NIGHT_END_HOUR,
)
from datetime import datetime


class FatigueAgent(BaseAgent):
    """疲劳度管理智能体"""

    agent_name = "SlaveAgent3"

    # 连续工作惩罚阈值（小时）
    CONSECUTIVE_PENALTY_THRESHOLD = 4.0
    # 超过阈值后每小时的额外疲劳惩罚
    CONSECUTIVE_PENALTY_RATE = 0.5
    # 休息恢复速率（每休息1小时恢复）
    REST_RECOVERY_RATE = 0.5
    # 深度休息恢复速率（休息超过2小时后额外加速）
    DEEP_REST_THRESHOLD = 2.0
    DEEP_REST_BONUS = 0.3
    # 疲劳自然衰减速率（每小时间歇）
    NATURAL_DECAY_RATE = 0.1
    # 最大疲劳值
    MAX_FATIGUE = 15.0

    def __init__(self):
        super().__init__()
        self.fatigue_table: Dict[str, float] = {}
        # 追踪每艘拖轮的连续工作时长
        self.consecutive_work: Dict[str, float] = {}
        # 追踪作业历史
        self.work_history: Dict[str, List[Dict]] = {}
        self._init_fatigue_table()

    def _init_fatigue_table(self):
        """初始化疲劳值"""
        tugs = load_tugs()
        for tug in tugs:
            self.fatigue_table[tug.id] = tug.fatigue_value
            self.consecutive_work[tug.id] = tug.today_work_hours
            self.work_history[tug.id] = []
        self.logger.info(f"初始化 {len(self.fatigue_table)} 艘拖轮疲劳状态")
        locked = sum(1 for t in tugs if t.status == "LOCKED_BY_FRMS")
        if locked:
            self.logger.warning(f"其中 {locked} 艘处于疲劳锁定状态")

    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        action = request.get("action", "get_fatigue")
        if action == "get_fatigue":
            result = self.get_fatigue(request.get("tug_id"))
            return result.model_dump()
        elif action == "update_fatigue":
            tug_id = request.get("tug_id")
            work_hours = request.get("work_hours")
            if not tug_id or work_hours is None:
                return {"error": "缺少 tug_id 或 work_hours"}
            self.update_fatigue(tug_id, work_hours, request.get("is_night", False))
            return {"success": True}
        elif action == "reset_fatigue":
            tug_id = request.get("tug_id")
            rest_hours = request.get("rest_hours")
            if not tug_id or rest_hours is None:
                return {"error": "缺少 tug_id 或 rest_hours"}
            self.reset_fatigue(tug_id, rest_hours)
            return {"success": True}
        return {"error": "Unknown action"}

    def get_fatigue(self, tug_id: str) -> FatigueCheckResponse:
        """获取拖轮疲劳状态"""
        fatigue = self.fatigue_table.get(tug_id, 0.0)
        level = self._calc_level(fatigue)

        result = FatigueCheckResponse(
            tug_id=tug_id,
            fatigue_value=round(fatigue, 1),
            fatigue_level=level,
            is_available=(level != FatigueLevel.RED),
        )

        if level == FatigueLevel.RED:
            result.lock_reason = f"疲劳值 {fatigue:.1f} 超过锁定阈值 {FATIGUE_LOCK_THRESHOLD}，需强制休息"
        elif level == FatigueLevel.YELLOW:
            result.lock_reason = f"疲劳值 {fatigue:.1f} 进入黄色警告区间，建议安排休息"
        else:
            result.lock_reason = None

        return result

    def _calc_level(self, fatigue: float) -> FatigueLevel:
        """计算疲劳等级"""
        if fatigue > FATIGUE_LOCK_THRESHOLD:
            return FatigueLevel.RED
        elif fatigue > FATIGUE_WARNING_THRESHOLD:
            return FatigueLevel.YELLOW
        return FatigueLevel.GREEN

    def update_fatigue(self, tug_id: str, work_hours: float, is_night: bool = False):
        """
        更新疲劳值（BFM 模型）

        公式:
        base_increment = 工作时长 × 时段系数
        连续工作惩罚: 连续 >4h 后，每小时 +0.5 额外疲劳
        夜间系数: 1.5x
        白天系数: 1.0x
        """
        current = self.fatigue_table.get(tug_id, 0.0)
        consecutive = self.consecutive_work.get(tug_id, 0.0)
        multiplier = FATIGUE_NIGHT_MULTIPLIER if is_night else FATIGUE_DAY_MULTIPLIER

        # 基础增量
        base_increment = work_hours * multiplier

        # 连续工作惩罚: 连续工作 >4h 后额外增加
        new_consecutive = consecutive + work_hours
        penalty = 0.0
        if new_consecutive > self.CONSECUTIVE_PENALTY_THRESHOLD:
            over_time = new_consecutive - self.CONSECUTIVE_PENALTY_THRESHOLD
            penalty = over_time * self.CONSECUTIVE_PENALTY_RATE
            self.logger.warning(f"拖轮 {tug_id} 连续工作 {new_consecutive:.1f}h，超过阈值 {self.CONSECUTIVE_PENALTY_THRESHOLD}h，附加惩罚 +{penalty:.1f}")

        new_fatigue = current + base_increment + penalty
        new_fatigue = min(new_fatigue, self.MAX_FATIGUE)

        # 更新状态
        self.fatigue_table[tug_id] = new_fatigue
        self.consecutive_work[tug_id] = new_consecutive

        # 记录作业历史
        self.work_history[tug_id].append({
            "time": datetime.now().isoformat(),
            "hours": work_hours,
            "is_night": is_night,
            "increment": round(base_increment + penalty, 2),
            "result": round(new_fatigue, 1)
        })

        self.logger.debug(
            f"更新拖轮 {tug_id} 疲劳值: {current:.1f} -> {new_fatigue:.1f} "
            f"(基础:{base_increment:.2f}, 惩罚:{penalty:.2f}, 连续:{new_consecutive:.1f}h)"
        )

    def reset_fatigue(self, tug_id: str, rest_hours: float):
        """
        休息恢复疲劳值

        公式:
        基础恢复 = 休息时长 × 0.5
        深度休息加成: 休息超过 DEEP_REST_THRESHOLD 小时后，额外 +0.3/h
        """
        current = self.fatigue_table.get(tug_id, 0.0)
        if current <= 0:
            return

        # 基础恢复
        recovery = rest_hours * self.REST_RECOVERY_RATE

        # 深度休息加成
        if rest_hours > self.DEEP_REST_THRESHOLD:
            deep_hours = rest_hours - self.DEEP_REST_THRESHOLD
            recovery += deep_hours * self.DEEP_REST_BONUS
            self.logger.debug(f"拖轮 {tug_id} 深度休息加成: +{deep_hours * self.DEEP_REST_BONUS:.1f}")

        # 自然衰减（即使不休息也缓慢恢复）
        natural_decay = rest_hours * self.NATURAL_DECAY_RATE
        recovery += natural_decay

        new_fatigue = max(0, current - recovery)
        self.fatigue_table[tug_id] = new_fatigue

        # 重置连续工作时长
        if rest_hours >= 1.0:
            self.consecutive_work[tug_id] = max(0, self.consecutive_work[tug_id] - rest_hours * 0.5)

        self.logger.debug(
            f"拖轮 {tug_id} 休息 {rest_hours:.1f}h，疲劳恢复 {recovery:.1f} 点: "
            f"{current:.1f} -> {new_fatigue:.1f}"
        )

    def get_all_fatigue_status(self) -> Dict[str, FatigueCheckResponse]:
        """获取所有拖轮疲劳状态"""
        return {tug_id: self.get_fatigue(tug_id) for tug_id in self.fatigue_table}

    def get_locked_tugs(self) -> List[str]:
        """获取被疲劳锁定的拖轮列表"""
        return [tug_id for tug_id in self.fatigue_table if not self.get_fatigue(tug_id).is_available]

    def get_warning_tugs(self) -> List[str]:
        """获取黄色警告状态的拖轮列表"""
        result = []
        for tug_id in self.fatigue_table:
            status = self.get_fatigue(tug_id)
            if status.fatigue_level == FatigueLevel.YELLOW:
                result.append(tug_id)
        return result

    def get_fatigue_statistics(self) -> Dict:
        """获取疲劳统计概览"""
        all_status = self.get_all_fatigue_status()
        levels = {"GREEN": 0, "YELLOW": 0, "RED": 0}
        values = []
        for tug_id, status in all_status.items():
            levels[status.fatigue_level] += 1
            values.append(status.fatigue_value)
        avg = sum(values) / len(values) if values else 0
        return {
            "total": len(all_status),
            "by_level": levels,
            "average_fatigue": round(avg, 2),
            "locked_count": len(self.get_locked_tugs()),
            "warning_count": len(self.get_warning_tugs()),
        }

    def get_tug_work_history(self, tug_id: str) -> List[Dict]:
        """获取拖轮作业历史"""
        return self.work_history.get(tug_id, [])
