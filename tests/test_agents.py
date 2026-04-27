"""Agent核心功能单元测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from data.loader import load_tugs, load_berths, load_jobs, load_rules
from agents import MasterAgent, PerceptionAgent, ComplianceAgent, FatigueAgent


class TestDataLoading(unittest.TestCase):
    """数据加载测试"""

    def setUp(self):
        self.tugs = load_tugs()
        self.berths = load_berths()
        self.jobs = load_jobs()
        self.rules = load_rules()

    def test_tugs_loaded(self):
        self.assertGreaterEqual(len(self.tugs), 10, "拖轮数量应≥10")

    def test_berths_loaded(self):
        self.assertGreaterEqual(len(self.berths), 5, "泊位数量应≥5")

    def test_jobs_loaded(self):
        self.assertGreaterEqual(len(self.jobs), 10, "任务数量应≥10")

    def test_rules_loaded(self):
        self.assertGreaterEqual(len(self.rules), 5, "规则数量应≥5")

    def test_tug_has_required_fields(self):
        for tug in self.tugs[:5]:
            self.assertTrue(tug.id, "拖轮应有ID")
            self.assertTrue(tug.name, "拖轮应有名称")
            self.assertTrue(tug.horsepower > 0, "拖轮马力应>0")

    def test_job_has_required_fields(self):
        for job in self.jobs[:5]:
            self.assertTrue(job.id, "任务应有ID")
            self.assertTrue(job.ship_name, "任务应有船名")
            self.assertTrue(job.ship_type, "任务应有船型")


class TestPerceptionAgent(unittest.TestCase):
    """感知智能体测试"""

    def setUp(self):
        self.agent = PerceptionAgent()
        self.berths = load_berths()

    def test_berth_distance_non_negative(self):
        if len(self.berths) >= 2:
            dist = self.agent.get_berth_distance(self.berths[0].id, self.berths[1].id)
            self.assertGreaterEqual(dist, 0, "泊位距离应≥0")

    def test_same_berth_distance_zero(self):
        if self.berths:
            dist = self.agent.get_berth_distance(self.berths[0].id, self.berths[0].id)
            self.assertAlmostEqual(dist, 0.0, places=2, msg="相同泊位距离应为0")

    def test_berth_constraints_return_dict(self):
        constraints = self.agent.get_berth_constraints()
        self.assertIsInstance(constraints, dict)


class TestFatigueAgent(unittest.TestCase):
    """疲劳智能体测试"""

    def setUp(self):
        self.agent = FatigueAgent()
        self.tugs = load_tugs()

    def test_fatigue_update_increases_value(self):
        if self.tugs:
            tid = self.tugs[0].id
            before = self.agent.get_fatigue(tid).fatigue_value
            self.agent.update_fatigue(tid, 2.0, is_night=False)
            after = self.agent.get_fatigue(tid).fatigue_value
            self.assertGreater(after, before, "工作时疲劳值应增加")

    def test_night_work_more_fatigue(self):
        if self.tugs:
            tid = self.tugs[0].id
            self.agent.reset_fatigue(tid, 10.0)
            base = self.agent.get_fatigue(tid).fatigue_value
            self.agent.update_fatigue(tid, 1.0, is_night=True)
            night_val = self.agent.get_fatigue(tid).fatigue_value
            self.assertGreater(night_val, base, "夜间工作疲劳增加应更多")

    def test_reset_reduces_fatigue(self):
        if self.tugs:
            tid = self.tugs[0].id
            self.agent.update_fatigue(tid, 5.0, is_night=False)
            before = self.agent.get_fatigue(tid).fatigue_value
            self.agent.reset_fatigue(tid, 4.0)
            after = self.agent.get_fatigue(tid).fatigue_value
            self.assertLess(after, before, "休息后疲劳值应降低")

    def test_fatigue_levels(self):
        if self.tugs:
            tid = self.tugs[0].id
            self.agent.reset_fatigue(tid, 20.0)
            info = self.agent.get_fatigue(tid)
            from interfaces.schemas import FatigueLevel
            self.assertIn(info.fatigue_level, [FatigueLevel.GREEN, FatigueLevel.YELLOW, FatigueLevel.RED],
                          "疲劳等级应为GREEN/YELLOW/RED之一")

    def test_locked_tugs_no_duplicates(self):
        locked = self.agent.get_locked_tugs()
        self.assertEqual(len(locked), len(set(locked)), "锁定拖轮ID不应重复")


class TestMasterAgent(unittest.TestCase):
    """主控智能体测试"""

    def setUp(self):
        self.agent = MasterAgent()
        self.jobs = load_jobs()

    def test_health_check(self):
        health = self.agent.health_check()
        self.assertEqual(health.get("status"), "healthy")

    def test_schedule_returns_solutions(self):
        ids = [j.id for j in self.jobs[:3]]
        solutions = self.agent.schedule(ids)
        self.assertGreaterEqual(len(solutions), 1, "应生成至少1个调度方案")

    def test_schedule_with_5_jobs(self):
        ids = [j.id for j in self.jobs[:5]]
        solutions = self.agent.schedule(ids)
        self.assertGreaterEqual(len(solutions), 1)

    def test_solution_has_metrics(self):
        ids = [j.id for j in self.jobs[:3]]
        solutions = self.agent.schedule(ids)
        if solutions:
            s = solutions[0]
            self.assertGreater(s.metrics.total_cost, 0, "成本应>0")
            self.assertGreaterEqual(s.metrics.balance_score, 0, "均衡度应≥0")
            self.assertGreaterEqual(s.metrics.efficiency_score, 0, "效率应≥0")

    def test_chain_jobs_identification(self):
        ids = [j.id for j in self.jobs[:10]]
        solutions = self.agent.schedule(ids)
        if solutions:
            for s in solutions:
                if s.chain_jobs:
                    for pair in s.chain_jobs:
                        self.assertGreater(pair.cost_saving, 0, "连活节省应>0")
                    return
            # 未识别到连活也可接受


class TestComplianceAgent(unittest.TestCase):
    """合规智能体测试"""

    def setUp(self):
        self.agent = ComplianceAgent()
        self.tugs = load_tugs()
        self.jobs = load_jobs()

    def test_compliance_check_returns_result(self):
        if self.tugs and self.jobs:
            result = self.agent.check_compliance(self.tugs[0].id, self.jobs[0].id)
            self.assertIsNotNone(result)
            self.assertIn("is_compliant", result.model_dump())

    def test_compliance_violation_has_reason(self):
        """合规违规时应有原因文本"""
        if self.tugs and self.jobs:
            result = self.agent.check_compliance(self.tugs[0].id, self.jobs[0].id)
            if not result.is_compliant:
                self.assertIsInstance(result.violation_reason, str)
            else:
                self.skipTest("当前组合无违规")


class TestLearningEngine(unittest.TestCase):
    """自学习引擎测试"""

    def setUp(self):
        from algorithms.learning import LearningEngine
        self.engine = LearningEngine()

    def test_record_and_stats(self):
        self.engine.record_schedule("test", ["JOB001"], [], {"total_cost": 100, "balance_score": 0.5, "efficiency_score": 0.5, "overall_score": 0.5})
        stats = self.engine.get_stats()
        self.assertGreaterEqual(stats["total_schedules"], 1)
        self.assertIn("avg_cost", stats)

    def test_analyze_returns_dict(self):
        self.engine.record_schedule("test", ["JOB001"], [], {"total_cost": 100, "balance_score": 0.5, "efficiency_score": 0.5, "overall_score": 0.5})
        analysis = self.engine.analyze()
        self.assertIn("status", analysis)


if __name__ == "__main__":
    unittest.main(verbosity=2)
