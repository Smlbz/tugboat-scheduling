# agents/perception_agent.py
"""
SlaveAgent1 - 全域感知智能体
负责人: 成员C

职责:
- 泊位堆栈逻辑（内档/外档管理）
- 隐性任务生成
- 泊位间距离计算
"""

from typing import List, Dict, Optional
from agents.base_agent import BaseAgent
from interfaces.schemas import Berth, Position
from data.loader import load_berths
import math


class PerceptionAgent(BaseAgent):
    """全域感知智能体"""
    
    agent_name = "SlaveAgent1"
    
    def __init__(self):
        super().__init__()
        self.berths = {b.id: b for b in load_berths()}
        self.logger.info(f"加载了 {len(self.berths)} 个泊位")
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        action = request.get("action")
        if action == "get_berth_distance":
            return {"distance": self.get_berth_distance(
                request["berth1_id"], request["berth2_id"]
            )}
        elif action == "check_berth_availability":
            return self.check_berth_availability(request["berth_id"])
        return {"error": "Unknown action"}
    
    def get_berth_distance(self, berth1_id: str, berth2_id: str) -> float:
        """
        计算两个泊位之间的距离（海里）

        TODO [成员C]: 实现真实的距离计算
        当前使用简化的直线距离
        """
        b1 = self.berths.get(berth1_id)
        b2 = self.berths.get(berth2_id)
        if not b1 or not b2:
            return float('inf')

        # 简化计算: 1度纬度 ≈ 60海里
        lat_diff = abs(b1.position.lat - b2.position.lat) * 60
        lng_diff = abs(b1.position.lng - b2.position.lng) * 60 * math.cos(math.radians(b1.position.lat))
        return math.sqrt(lat_diff**2 + lng_diff**2)

    def estimate_distance_from_position(self, position, target_berth_id: str) -> float:
        """从当前位置到目标泊位的估算距离（海里）"""
        berth = self.berths.get(target_berth_id)
        if not berth:
            return 2.0
        lat_diff = abs(position.lat - berth.position.lat) * 60
        lng_diff = abs(position.lng - berth.position.lng) * 60 * math.cos(math.radians(position.lat))
        return math.sqrt(lat_diff ** 2 + lng_diff ** 2)
    
    def check_berth_availability(self, berth_id: str) -> Dict:
        """
        检查泊位可用性
        
        TODO [成员C]: 实现完整的泊位堆栈逻辑
        返回:
        - 可用拖轮列表
        - 需要移泊的拖轮列表
        """
        berth = self.berths.get(berth_id)
        if not berth:
            return {"available": False, "reason": "泊位不存在"}
        
        if not berth.tugs_stack:
            return {"available": True, "available_tugs": []}
        
        # 最后一个是外档，可直接出动
        outer_tug = berth.tugs_stack[-1]
        inner_tugs = berth.tugs_stack[:-1]
        
        return {
            "available": True,
            "outer_tug": outer_tug,
            "inner_tugs": inner_tugs,
            "need_shifting": len(inner_tugs) > 0
        }
    
    def get_berth_constraints(self) -> Dict[str, List[str]]:
        """
        获取所有泊位约束
        
        TODO [成员C]: 根据实际需求扩展
        """
        constraints = {}
        for berth_id, berth in self.berths.items():
            if len(berth.tugs_stack) > 1:
                constraints[berth_id] = {
                    "blocked_tugs": berth.tugs_stack[:-1],  # 内档船
                    "available_tug": berth.tugs_stack[-1] if berth.tugs_stack else None
                }
        return constraints
    
    def get_hidden_tasks(self) -> List[str]:
        """
        生成隐性任务（辅助带缆、航道清理等）
        
        TODO [成员C]: 实现隐性任务生成逻辑
        """
        # Demo版返回空列表
        return []
