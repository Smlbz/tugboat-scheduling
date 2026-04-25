# engine - 统一规则引擎
"""
规则引擎模块，管理三类规则：
- USAGE_SPEC: 参数型规则(CSV来源)，条件→需求值
- DISPATCH_FACTOR: 因素型规则(XLSX来源)，定性调度原则
- COMPLIANCE: 合规型规则(JSON来源)，条件→违规判定
"""

from engine.rule_engine import RuleEngine
from engine.spec_rule import ConditionSpec, UsageSpecResult

__all__ = ["RuleEngine", "ConditionSpec", "UsageSpecResult"]
