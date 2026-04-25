"""条件匹配器 — 匹配船舶参数与CSV规则条件"""
import logging
from typing import List, Optional
from engine.spec_rule import ConditionSpec, UsageSpecResult

logger = logging.getLogger("ConditionMatcher")


class ConditionMatcher:
    """CSV规则条件匹配"""

    @staticmethod
    def match_usage_spec(
        ship_type: str,
        ship_length: Optional[float],
        operation: str,
        draft: Optional[float],
        rules: List[dict]
    ) -> Optional[UsageSpecResult]:
        """匹配最佳CSV规则"""
        candidates = []
        for r in rules:
            cond = r.get("conditions", {})
            if cond.get("ship_type") != ship_type:
                continue
            # 作业匹配: 规则op=靠离 匹配任何; 输入op=靠离 匹配任何规则; 否则精确匹配
            rule_op = cond.get("operation", "靠离")
            if not (rule_op == "靠离" or operation == "靠离" or rule_op == operation):
                continue
            # 长度匹配
            if not ConditionMatcher._match_length(ship_length, cond):
                continue
            # 吃水匹配
            if not ConditionMatcher._match_draft(draft, cond):
                continue
            # 计算匹配分
            score = ConditionMatcher._calc_match_score(cond, ship_length, draft)
            candidates.append((score, r))

        if not candidates:
            return None

        # 最高分胜出
        candidates.sort(key=lambda x: -x[0])
        best = candidates[0][1]
        res = best.get("result", {})
        return UsageSpecResult(
            horsepower_min=res.get("horsepower_min", 0),
            horsepower_max=res.get("horsepower_max", 0),
            tug_count=res.get("tug_count_min") or res.get("tug_count_max"),
            tug_operation=res.get("tug_operation"),
        )

    @staticmethod
    def _match_length(ship_length: Optional[float], cond: dict) -> bool:
        """检查长度是否匹配条件 [min, max)"""
        special = cond.get("length_special")
        if special:
            return True

        length_min = cond.get("length_min")
        length_max = cond.get("length_max")

        if length_min is None and length_max is None:
            return True
        if ship_length is None:
            return False

        if length_min is not None and ship_length < length_min:
            return False
        if length_max is not None and ship_length >= length_max:
            return False
        return True

    @staticmethod
    def _match_draft(draft: Optional[float], cond: dict) -> bool:
        """检查吃水是否匹配条件 [min, max)"""
        empty_draft = cond.get("empty_draft", False)
        if empty_draft:
            return draft is None or draft <= 0.5

        draft_min = cond.get("draft_min")
        draft_max = cond.get("draft_max")

        if draft_min is None and draft_max is None:
            return True
        if draft is None:
            return False

        if draft_min is not None and draft < draft_min:
            return False
        if draft_max is not None and draft >= draft_max:
            return False

        return True

    @staticmethod
    def _calc_match_score(cond: dict, ship_length: Optional[float], draft: Optional[float]) -> int:
        """计算匹配精度分（越高越精确）"""
        score = 1
        if cond.get("length_min") is not None or cond.get("length_max") is not None:
            score += 2
        if cond.get("length_special"):
            score += 2
        if cond.get("draft_min") is not None or cond.get("draft_max") is not None:
            score += 2
        if cond.get("empty_draft"):
            score += 2
        return score
