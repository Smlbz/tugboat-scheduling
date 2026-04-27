"""RuleEngine 合规检查器单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import unittest
from engine.rule_engine import RuleEngine
from interfaces.schemas import Tug, Job, Position, TugStatus, FatigueLevel, JobType
from datetime import datetime


def _make_tug(**kwargs):
    defaults = dict(
        id="TUG-T", name="测试拖轮", horsepower=5000,
        position=Position(lng=120.3, lat=36.1),
        status=TugStatus.AVAILABLE,
        fatigue_value=5.0, fatigue_level=FatigueLevel.YELLOW,
        today_work_hours=6, ship_age=15,
    )
    defaults.update(kwargs)
    return Tug(**defaults)


def _make_job(high_risk=False, hp=4000, tug_count=2, special_req=None,
              ship_type=None, ship_length=None):
    return Job(
        id="JOB-T", job_type=JobType.BERTHING,
        ship_name="测试船", ship_type=ship_type, ship_length=ship_length,
        target_berth_id="B001",
        start_time=datetime(2026, 1, 1, 8, 0),
        end_time=datetime(2026, 1, 1, 12, 0),
        required_horsepower=hp, required_tug_count=tug_count,
        is_high_risk=high_risk,
        special_requirements=special_req or [],
    )


class TestRuleEngineCheckers(unittest.TestCase):
    """测试 RuleEngine 的 8 个合规检查器"""

    @classmethod
    def setUpClass(cls):
        cls.RE = RuleEngine

    def test_r001_name_similarity(self):
        tug1 = _make_tug()
        ctx = {"assigned_tugs": [_make_tug(id="TUG-T2", name="测试拖轮2")]}
        self.assertTrue(self.RE._check_name_similarity(tug1, _make_job(), ctx, {}))

    def test_r001_no_similarity(self):
        tug = _make_tug(name="青港拖1")
        ctx = {"assigned_tugs": [_make_tug(id="TUG-T2", name="大港拖1")]}
        self.assertFalse(self.RE._check_name_similarity(tug, _make_job(), ctx, {}))

    def test_r002_old_tug_high_risk(self):
        old = _make_tug(ship_age=25)
        job = _make_job(high_risk=True)
        self.assertTrue(self.RE._check_old_tug_high_risk(old, job, {}, {}))

    def test_r002_young_tug_high_risk_ok(self):
        young = _make_tug(ship_age=10)
        job = _make_job(high_risk=True)
        self.assertFalse(self.RE._check_old_tug_high_risk(young, job, {}, {}))

    def test_r003_horsepower_insufficient(self):
        weak_tug = _make_tug(horsepower=1000)
        job = _make_job(hp=5000)
        self.assertTrue(self.RE._check_horsepower(weak_tug, job, {}, {}))

    def test_r003_horsepower_sufficient(self):
        strong_tug = _make_tug(horsepower=5000)
        job = _make_job(hp=3000)
        self.assertFalse(self.RE._check_horsepower(strong_tug, job, {}, {}))

    def test_r004_fatigue_red(self):
        tired = _make_tug(fatigue_level=FatigueLevel.RED)
        self.assertTrue(self.RE._check_fatigue(tired, _make_job(), {}, {}))

    def test_r004_fatigue_green_ok(self):
        fresh = _make_tug(fatigue_level=FatigueLevel.GREEN)
        self.assertFalse(self.RE._check_fatigue(fresh, _make_job(), {}, {}))

    def test_r005_night_no_qualification(self):
        night_job = _make_job()
        night_job.start_time = datetime(2026, 1, 1, 23, 0)
        tug = _make_tug(today_work_hours=10)
        helpers = {"check_night_qualification": lambda t: False}
        self.assertTrue(self.RE._check_night_operation(tug, night_job, {}, helpers))

    def test_r005_daytime_ok(self):
        day_job = _make_job()
        day_job.start_time = datetime(2026, 1, 1, 10, 0)
        self.assertFalse(self.RE._check_night_operation(_make_tug(), day_job, {}, {}))

    def test_r006_inner_berth_always_pass(self):
        """R006 内档船仅警告不阻止，始终返回 False"""
        self.assertFalse(self.RE._check_inner_berth(_make_tug(), _make_job(), {}, {}))

    def test_r007_continuous_work(self):
        overworked = _make_tug(today_work_hours=6)
        self.assertTrue(self.RE._check_continuous_work(overworked, _make_job(), {}, {}))

    def test_r007_continuous_work_ok(self):
        normal = _make_tug(today_work_hours=2)
        self.assertFalse(self.RE._check_continuous_work(normal, _make_job(), {}, {}))

    def test_r008_hazmat_no_qualification(self):
        weak = _make_tug(horsepower=3000)
        hazmat_job = _make_job(high_risk=True, special_req=["危化品"])
        helpers = {"check_hazmat_qualification": lambda t: False}
        self.assertTrue(self.RE._check_hazmat(weak, hazmat_job, {}, helpers))

    def test_r008_hazmat_qualified_ok(self):
        strong = _make_tug(horsepower=6000)
        hazmat_job = _make_job(high_risk=True, special_req=["危化品"])
        helpers = {"check_hazmat_qualification": lambda t: True}
        self.assertFalse(self.RE._check_hazmat(strong, hazmat_job, {}, helpers))

    def test_r008_not_hazmat_no_violation(self):
        normal_job = _make_job(high_risk=False)
        self.assertFalse(self.RE._check_hazmat(_make_tug(), normal_job, {}, {}))


class TestRuleEngineIntegration(unittest.TestCase):
    """RuleEngine 集成测试"""

    def setUp(self):
        self.engine = RuleEngine()

    def test_get_all_rules_merged(self):
        all_rules = self.engine.get_all_rules()
        self.assertGreaterEqual(len(all_rules), 8)
        rule_ids = [r["id"] for r in all_rules]
        self.assertIn("R001", rule_ids)
        self.assertIn("R002", rule_ids)

    def test_enrich_job_sets_horsepower(self):
        job = _make_job(ship_type="集装箱船", ship_length=200, hp=0)
        enriched = self.engine.enrich_job(job)
        self.assertGreater(enriched.required_horsepower, 0)

    def test_enrich_job_missing_type_unchanged(self):
        job = _make_job(ship_type=None, hp=4000)
        enriched = self.engine.enrich_job(job)
        self.assertEqual(enriched.required_horsepower, 4000)

    def test_check_compliance_within_rule_engine(self):
        tug = _make_tug()
        job = _make_job()
        violations = self.engine.check_compliance(tug, job)
        self.assertIsInstance(violations, list)

    def test_compliance_r001_via_engine(self):
        tug = _make_tug(name="青港拖1")
        job = _make_job()
        assigned = [_make_tug(id="TUG-X", name="青港拖11")]
        violations = self.engine.check_compliance(tug, job, assigned_tugs=assigned)
        self.assertIn("R001", violations)

    def test_dispatch_factors_returns_list(self):
        factors = self.engine.get_dispatch_factors(_make_tug(), _make_job())
        self.assertIsInstance(factors, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
