# agents/perception_agent.py
"""
SlaveAgent1 - 全域感知智能体
负责人: 成员C

职责:
- 泊位堆栈逻辑（内档/外档管理）
- 隐性任务生成（移泊、辅助带缆等）
- 泊位间距离计算
"""

from typing import List, Dict, Optional
from agents.base_agent import BaseAgent
from interfaces.schemas import Berth, Position
from data.loader import load_berths, get_berth_by_id
import math


class BerthStack:
    """
    泊位堆栈 - 后进先出（LIFO）

    外档船 = 栈顶（最后停靠），可直接出动
    内档船 = 被外档船阻挡，需先移走外档才能出动

    TODO [成员C]: 扩展实际港口操作逻辑
    """

    def __init__(self, berth_id: str, tugs: List[str]):
        self.berth_id = berth_id
        self.stack = list(tugs)

    @property
    def outer_tug(self) -> Optional[str]:
        """外档拖轮（栈顶）"""
        return self.stack[-1] if self.stack else None

    @property
    def inner_tugs(self) -> List[str]:
        """内档拖轮列表（除栈顶外所有）"""
        return self.stack[:-1] if len(self.stack) > 1 else []

    @property
    def tug_count(self) -> int:
        return len(self.stack)

    def can_dispatch(self, tug_id: str) -> bool:
        """tug_id 是否可以直接出动（必须是外档）"""
        return bool(self.stack) and self.stack[-1] == tug_id

    def get_blocking_tugs(self, tug_id: str) -> List[str]:
        """
        获取阻挡 tug_id 的拖轮

        如果 tug_id 不在栈中，返回空列表
        排在 tug_id 之后（outer侧）的都是阻挡船，需先移泊
        """
        if tug_id not in self.stack:
            return []
        idx = self.stack.index(tug_id)
        return list(reversed(self.stack[idx + 1:]))

    def dispatch(self, tug_id: str) -> bool:
        """出动拖轮（必须从栈顶取出）"""
        if not self.stack or self.stack[-1] != tug_id:
            return False
        self.stack.pop()
        return True

    def berth(self, tug_id: str) -> None:
        """新拖轮靠泊（入栈，成为新的外档）"""
        self.stack.append(tug_id)

    def shift_out(self) -> Optional[str]:
        """将外档船移泊（弹出栈顶）"""
        return self.stack.pop() if self.stack else None

    def get_shift_plan(self, target_tug: str) -> List[str]:
        """
        获取将 target_tug 移泊到外档所需的操作序列

        返回: 需要依次移泊的 tug_id 列表（按移出顺序）
        如果 target_tug 已在栈顶，返回空列表
        """
        if not self.stack or self.stack[-1] == target_tug:
            return []
        return self.get_blocking_tugs(target_tug)


class PerceptionAgent(BaseAgent):
    """全域感知智能体"""

    agent_name = "SlaveAgent1"

    def __init__(self):
        super().__init__()
        self.berths = {b.id: b for b in load_berths()}
        # 初始化堆栈
        self.berth_stacks: Dict[str, BerthStack] = {
            b.id: BerthStack(b.id, list(b.tugs_stack))
            for b in load_berths()
        }
        self.logger.info(f"加载了 {len(self.berths)} 个泊位，{sum(len(s.stack) for s in self.berth_stacks.values())} 艘在泊拖轮")

    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        action = request.get("action")
        if action == "get_berth_distance":
            return {"distance": self.get_berth_distance(
                request["berth1_id"], request["berth2_id"]
            )}
        elif action == "check_berth_availability":
            return self.check_berth_availability(request["berth_id"])
        elif action == "check_tug_dispatch":
            return self.check_tug_dispatch(
                request["tug_id"], request.get("target_berth_id")
            )
        return {"error": "Unknown action"}

    def get_berth_distance(self, berth1_id: str, berth2_id: str) -> float:
        """
        计算两个泊位之间的距离（海里）

        使用 Haversine 公式计算大圆距离
        1 海里 = 1.852 公里
        """
        b1 = self.berths.get(berth1_id)
        b2 = self.berths.get(berth2_id)
        if not b1 or not b2:
            return float('inf')

        lat1 = math.radians(b1.position.lat)
        lat2 = math.radians(b2.position.lat)
        lng1 = math.radians(b1.position.lng)
        lng2 = math.radians(b2.position.lng)

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # 地球半径 ≈ 3440 海里
        distance_nm = 3440 * c
        return round(distance_nm, 2)

    def estimate_distance_from_position(self, position, target_berth_id: str) -> float:
        """从当前位置到目标泊位的估算距离（海里）"""
        berth = self.berths.get(target_berth_id)
        if not berth:
            return 2.0

        lat1 = math.radians(position.lat)
        lat2 = math.radians(berth.position.lat)
        lng1 = math.radians(position.lng)
        lng2 = math.radians(berth.position.lng)

        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(3440 * c, 2)

    def check_berth_availability(self, berth_id: str) -> Dict:
        """
        检查泊位可用性

        返回:
        - available: 泊位是否存在
        - outer_tug: 外档拖轮ID（可直接出动）
        - inner_tugs: 内档拖轮列表（需先移泊）
        - need_shifting: 是否需移泊操作
        - capacity_remaining: 剩余可用泊位容量
        """
        berth = self.berths.get(berth_id)
        if not berth:
            return {"available": False, "reason": "泊位不存在"}

        stack = self.berth_stacks.get(berth_id)
        if not stack or stack.tug_count == 0:
            return {
                "available": True,
                "outer_tug": None,
                "inner_tugs": [],
                "need_shifting": False,
                "capacity_remaining": berth.max_capacity
            }

        return {
            "available": True,
            "outer_tug": stack.outer_tug,
            "inner_tugs": stack.inner_tugs,
            "need_shifting": len(stack.inner_tugs) > 0,
            "capacity_remaining": max(0, berth.max_capacity - stack.tug_count)
        }

    def check_tug_dispatch(self, tug_id: str, target_berth_id: str = None) -> Dict:
        """
        检查某艘拖轮是否能从当前泊位出动

        如 target_berth_id 有值，同时返回到目标泊位的距离

        返回:
        - can_dispatch: 能否直接出动
        - current_berth: 当前泊位
        - blocking_tugs: 阻挡的拖轮列表（需先移泊）
        - shift_plan: 移泊操作序列
        - distance_to_target: 到目标泊位的距离（海里）
        """
        # 查找拖轮所在的泊位
        tug_berth_id = None
        for berth_id, stack in self.berth_stacks.items():
            if any(t == tug_id for t in stack.stack):
                tug_berth_id = berth_id
                break

        if not tug_berth_id:
            return {"can_dispatch": False, "reason": "拖轮不在任何泊位"}

        stack = self.berth_stacks[tug_berth_id]
        blocking = stack.get_blocking_tugs(tug_id)

        result = {
            "can_dispatch": len(blocking) == 0,
            "current_berth": tug_berth_id,
            "blocking_tugs": blocking,
            "shift_plan": stack.get_shift_plan(tug_id),
            "is_outer": stack.outer_tug == tug_id
        }

        if target_berth_id:
            result["distance_to_target"] = self.get_berth_distance(tug_berth_id, target_berth_id)

        return result

    def get_berth_constraints(self) -> Dict[str, Dict]:
        """
        获取所有泊位约束

        返回: { berth_id: { blocked_tugs, available_tug, shift_required } }
        """
        constraints = {}
        for berth_id, stack in self.berth_stacks.items():
            if stack.tug_count > 1:
                constraints[berth_id] = {
                    "blocked_tugs": stack.inner_tugs,
                    "available_tug": stack.outer_tug,
                    "shift_required": True,
                    "inner_count": len(stack.inner_tugs),
                    "total_count": stack.tug_count
                }
            elif stack.tug_count == 1:
                constraints[berth_id] = {
                    "blocked_tugs": [],
                    "available_tug": stack.outer_tug,
                    "shift_required": False,
                    "inner_count": 0,
                    "total_count": 1
                }
        return constraints

    def get_hidden_tasks(self) -> List[str]:
        """
        生成隐性任务

        隐性任务包括:
        1. 移泊任务: 内档船需先移泊才能出动，生成 SHIFT_{tug_id} 任务
        2. 辅助带缆: 大型船舶靠泊时需要的辅助拖轮
        3. 航道清理: 大型船舶进出港时的航道保障

        返回: 隐性任务ID列表
        """
        hidden = []

        # 1. 移泊任务: 为每个泊位的内档船生成移泊任务
        for berth_id, stack in self.berth_stacks.items():
            for inner_tug in stack.inner_tugs:
                hidden.append(f"SHIFT_{inner_tug}")

        # 2. 辅助任务: 对繁忙泊位（拖轮数量较多）生成辅助带缆任务
        for berth_id, stack in self.berth_stacks.items():
            if stack.tug_count >= 3:
                # 拖轮密集停靠的泊位，需要辅助带缆
                hidden.append(f"LINEHANDLE_{berth_id}")

        # 3. 大型泊位（LARGE类型）生成航道清理任务
        for berth_id, berth in self.berths.items():
            if berth.berth_type == "LARGE" and berth.tugs_stack:
                hidden.append(f"CHANNEL_CLEAR_{berth_id}")

        if hidden:
            self.logger.debug(f"生成 {len(hidden)} 个隐性任务: {hidden}")

        return hidden
