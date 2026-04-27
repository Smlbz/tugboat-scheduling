"""统一规则引擎 — 管理三类规则：USAGE_SPEC / DISPATCH_FACTOR / COMPLIANCE"""
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Callable, Dict
from interfaces.schemas import Tug, Job, Assignment
from engine.spec_rule import UsageSpecResult
from engine.condition_matcher import ConditionMatcher

logger = logging.getLogger("RuleEngine")

BASE_DIR = Path(__file__).parent.parent  # tugboat-scheduling/

# 合规检查器注册表
# key=规则ID, value=函数(tug, job, context, helpers) -> bool (True=违规)
RuleChecker = Callable[[Tug, Job, dict, dict], bool]


class RuleEngine:
    def __init__(self):
        self.usage_rules = self._load_usage_rules()
        self.factor_rules = self._load_factor_rules()
        self.compliance_rules = self._load_compliance_rules()
        self.condition_matcher = ConditionMatcher()
        self.checkers = self._register_checkers()
        logger.info(f"引擎加载: {len(self.usage_rules)} 参数规则, "
                    f"{len(self.factor_rules)} 因素规则, "
                    f"{len(self.compliance_rules)} 合规规则")

    def _load_usage_rules(self) -> list:
        path = BASE_DIR / "data" / "rules_usage.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["rules"]
        return []

    def _load_factor_rules(self) -> list:
        path = BASE_DIR / "data" / "rules_factors.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["rules"]
        return []

    def _load_compliance_rules(self) -> list:
        path = BASE_DIR / "data" / "rules.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["rules"]
        return []

    def _register_checkers(self) -> Dict[str, RuleChecker]:
        """注册所有合规检查器"""
        return {
            "R001": self._check_name_similarity,
            "R002": self._check_old_tug_high_risk,
            "R003": self._check_horsepower,
            "R004": self._check_fatigue,
            "R005": self._check_night_operation,
            "R006": self._check_inner_berth,
            "R007": self._check_continuous_work,
            "R008": self._check_hazmat,
        }

    def get_all_rules(self) -> list:
        """返回全部规则（三类合并）"""
        return self.usage_rules + self.factor_rules + self.compliance_rules

    def lookup_spec(
        self,
        ship_type: str,
        ship_length: Optional[float],
        operation: str,
        draft: Optional[float] = None
    ) -> Optional[UsageSpecResult]:
        """根据船舶参数查马力需求 (CSV规则)"""
        return self.condition_matcher.match_usage_spec(
            ship_type, ship_length, operation, draft, self.usage_rules
        )

    def enrich_job(self, job: Job) -> Job:
        """用CSV规则自动填充job的required_horsepower和required_tug_count"""
        if not job.ship_type or not job.ship_length:
            return job

        op_map = {
            "BERTHING": "靠",
            "UNBERTHING": "离",
            "SHIFTING": "靠离",
            "ESCORT": "靠离",
        }
        operation = op_map.get(job.job_type.value if hasattr(job.job_type, 'value') else job.job_type, "靠离")

        spec = self.lookup_spec(
            ship_type=job.ship_type,
            ship_length=job.ship_length,
            operation=operation,
            draft=job.draft_depth,
        )
        if spec:
            hp_min = spec.horsepower_min or 0
            hp_max = spec.horsepower_max or 0
            if hp_max > 0:
                job.required_horsepower = (hp_min + hp_max) // 2
            elif hp_min > 0:
                job.required_horsepower = hp_min
            if spec.tug_count:
                job.required_tug_count = spec.tug_count
        return job

    def enrich_jobs(self, jobs: List[Job]) -> List[Job]:
        """批量填充job需求"""
        return [self.enrich_job(j) for j in jobs]

    def check_compliance(
        self,
        tug: Tug,
        job: Job,
        assigned_tugs: Optional[List[Tug]] = None,
        helpers: Optional[dict] = None
    ) -> List[str]:
        """检查所有合规规则，返回违规ID列表"""
        violations = []
        context = {"assigned_tugs": assigned_tugs or []}
        helpers = helpers or {}

        for rule in self.compliance_rules:
            rid = rule["id"]
            checker = self.checkers.get(rid)
            if checker and rule.get("enabled", True):
                try:
                    if checker(tug, job, context, helpers):
                        violations.append(rid)
                except Exception as e:
                    logger.warning(f"规则 {rid} 检查异常: {e}")
                    violations.append(f"{rid}_ERROR")
        return violations

    def get_dispatch_factors(self, tug: Tug, job: Job, context: dict = None) -> list:
        """获取所有影响因素及其评分"""
        results = []
        for rule in self.factor_rules:
            results.append({
                "id": rule["id"],
                "name": rule["name"],
                "description": rule["description"],
                "category": rule.get("category", "EFFICIENCY"),
            })
        return results

    # ---- 检查器实现 ----

    @staticmethod
    def _check_name_similarity(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R001: 名称混淆"""
        assigned = ctx.get("assigned_tugs", [])
        if not assigned:
            return False

        def normalize(name: str) -> str:
            return re.sub(r'[\d]+号?$', '', name).strip()

        base = normalize(tug.name)
        for other in assigned:
            if isinstance(other, Tug):
                other_base = normalize(other.name)
                if base and base == other_base:
                    return True
                if len(base) >= 2 and len(other_base) >= 2 and (base in other_base or other_base in base):
                    return True
        return False

    @staticmethod
    def _check_old_tug_high_risk(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R002: 老旧拖轮高危"""
        return tug.ship_age > 20 and job.is_high_risk

    @staticmethod
    def _check_horsepower(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R003: 马力匹配"""
        per_tug_hp = job.required_horsepower / max(job.required_tug_count, 1)
        return tug.horsepower < per_tug_hp

    @staticmethod
    def _check_fatigue(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R004: 疲劳禁派"""
        fl = tug.fatigue_level
        if hasattr(fl, 'value'):
            return fl.value == "RED"
        return fl == "RED"

    @staticmethod
    def _check_night_operation(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R005: 夜间资质"""
        hour = job.start_time.hour if hasattr(job.start_time, 'hour') else 0
        if hour >= 22 or hour < 6:
            # 使用helper检查夜间资质
            night_check = helpers.get("check_night_qualification")
            if night_check:
                return not night_check(tug)
            return tug.today_work_hours >= 8  # 默认逻辑
        return False

    @staticmethod
    def _check_inner_berth(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R006: 内档船（仅警告）"""
        return False  # 不阻止调度，仅记录

    @staticmethod
    def _check_continuous_work(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R007: 连续作业限制"""
        return tug.today_work_hours > 4

    @staticmethod
    def _check_hazmat(tug: Tug, job: Job, ctx: dict, helpers: dict) -> bool:
        """R008: 危化品资质"""
        if job.is_high_risk and "危化品" in job.special_requirements:
            hazmat_check = helpers.get("check_hazmat_qualification")
            if hazmat_check:
                return not hazmat_check(tug)
            return tug.horsepower < 5000
        return False
