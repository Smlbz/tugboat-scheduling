"""参数规则数据类 - CSV规则(USAGE_SPEC)结构化表示"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ConditionSpec:
    """CSV规则条件"""
    ship_type: str                                 # 船型: 油船/杂货船/集装箱船/散货船
    length_min: Optional[float] = None             # 船长下限(米)
    length_max: Optional[float] = None             # 船长上限(米)
    operation: str = "靠离"                         # 作业类型: 靠/离/靠离
    draft_min: Optional[float] = None              # 吃水下限(米)
    draft_max: Optional[float] = None              # 吃水上限(米)
    empty_draft: bool = False                      # 是否空载


@dataclass
class UsageSpecResult:
    """CSV规则结果"""
    horsepower_min: int = 0                         # 最小需求马力
    horsepower_max: int = 0                         # 最大需求马力
    tug_count: Optional[int] = None                # 拖轮条数
    tug_operation: Optional[str] = None            # 拖轮靠离泊方式
