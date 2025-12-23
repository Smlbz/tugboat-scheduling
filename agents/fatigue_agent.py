# agents/fatigue_agent.py
"""
SlaveAgent3 - 疲劳度管理智能体
负责人: 成员C

职责:
- 疲劳模型 BFM 实现
- 实时疲劳状态维护
- 状态锁管理
"""

from typing import Dict
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


class FatigueAgent(BaseAgent):
    """疲劳度管理智能体"""
    
    agent_name = "SlaveAgent3"
    
    def __init__(self):
        super().__init__()
        # 从数据文件初始化疲劳表
        self.fatigue_table: Dict[str, float] = {}
        self._init_fatigue_table()
    
    def _init_fatigue_table(self):
        """初始化疲劳值"""
        tugs = load_tugs()
        for tug in tugs:
            self.fatigue_table[tug.id] = tug.fatigue_value
        self.logger.info(f"初始化 {len(self.fatigue_table)} 艘拖轮疲劳状态")
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        action = request.get("action", "get_fatigue")
        if action == "get_fatigue":
            result = self.get_fatigue(request.get("tug_id"))
            return result.model_dump()
        elif action == "update_fatigue":
            self.update_fatigue(
                request["tug_id"],
                request["work_hours"],
                request.get("is_night", False)
            )
            return {"success": True}
        return {"error": "Unknown action"}
    
    def get_fatigue(self, tug_id: str) -> FatigueCheckResponse:
        """获取拖轮疲劳状态"""
        fatigue = self.fatigue_table.get(tug_id, 0.0)
        level = self._calc_level(fatigue)
        
        return FatigueCheckResponse(
            tug_id=tug_id,
            fatigue_value=fatigue,
            fatigue_level=level,
            is_available=(level != FatigueLevel.RED),
            lock_reason="疲劳值超过阈值，需要休息" if level == FatigueLevel.RED else None
        )
    
    def _calc_level(self, fatigue: float) -> FatigueLevel:
        """计算疲劳等级"""
        if fatigue > FATIGUE_LOCK_THRESHOLD:
            return FatigueLevel.RED
        elif fatigue > FATIGUE_WARNING_THRESHOLD:
            return FatigueLevel.YELLOW
        return FatigueLevel.GREEN
    
    def update_fatigue(self, tug_id: str, work_hours: float, is_night: bool = False):
        """
        更新疲劳值
        
        公式: 当前疲劳 = 现有值 + (工作时长 * 系数)
        夜间系数 = 1.5, 白天系数 = 1.0
        
        TODO [成员C]: 
        1. 实现更复杂的疲劳模型
        2. 考虑休息恢复
        3. 考虑连续工作时长
        """
        current = self.fatigue_table.get(tug_id, 0.0)
        multiplier = FATIGUE_NIGHT_MULTIPLIER if is_night else FATIGUE_DAY_MULTIPLIER
        new_fatigue = current + (work_hours * multiplier)
        self.fatigue_table[tug_id] = min(new_fatigue, 15.0)  # 上限15
        
        self.logger.info(f"更新拖轮 {tug_id} 疲劳值: {current:.1f} -> {new_fatigue:.1f}")
    
    def reset_fatigue(self, tug_id: str, rest_hours: float):
        """
        休息恢复疲劳值
        
        TODO [成员C]: 实现休息恢复逻辑
        """
        current = self.fatigue_table.get(tug_id, 0.0)
        recovery = rest_hours * 0.5  # 每小时休息恢复0.5疲劳
        self.fatigue_table[tug_id] = max(0, current - recovery)
    
    def get_all_fatigue_status(self) -> Dict[str, FatigueCheckResponse]:
        """获取所有拖轮疲劳状态"""
        return {tug_id: self.get_fatigue(tug_id) for tug_id in self.fatigue_table}
    
    def get_locked_tugs(self) -> list:
        """获取被疲劳锁定的拖轮列表"""
        locked = []
        for tug_id in self.fatigue_table:
            status = self.get_fatigue(tug_id)
            if not status.is_available:
                locked.append(tug_id)
        return locked
