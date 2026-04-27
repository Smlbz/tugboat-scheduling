"""MetricsCalculator 单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import unittest
from utils.metrics_calculator import MetricsCalculator
from interfaces.schemas import Assignment, Job, JobType, Position, Tug
from datetime import datetime


def _make_job(job_id="J001", job_type=JobType.BERTHING, hp=4000):
    return Job(
        id=job_id, job_type=job_type,
        ship_name="船", target_berth_id="B001",
        start_time=datetime(2026, 1, 1, 8, 0),
        end_time=datetime(2026, 1, 1, 12, 0),
        required_horsepower=hp, required_tug_count=1,
    )


def _make_assign(tug_id="T001", job_id="J001", job_type=JobType.BERTHING):
    return Assignment(tug_id=tug_id, tug_name="拖轮", job_id=job_id, job_type=job_type, score=0.8)


class TestMetricsCalcBalance(unittest.TestCase):
    def test_balance_empty(self):
        self.assertEqual(MetricsCalculator.calc_balance(assignments=[]), 1.0)

    def test_balance_single_tug(self):
        # 单拖轮方差=0，变异系数=0，平衡度=1.0（完美），退化情况数学正确
        self.assertEqual(MetricsCalculator.calc_balance(workload_dict={"T1": 3}), 1.0)

    def test_balance_perfect(self):
        self.assertEqual(MetricsCalculator.calc_balance(workload_dict={"T1": 2, "T2": 2}), 1.0)

    def test_balance_uneven(self):
        score = MetricsCalculator.calc_balance(workload_dict={"T1": 5, "T2": 1})
        self.assertLess(score, 1.0)
        self.assertGreaterEqual(score, 0.0)

    def test_balance_extreme(self):
        score = MetricsCalculator.calc_balance(workload_dict={"T1": 100, "T2": 0})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_balance_zero_mean(self):
        score = MetricsCalculator.calc_balance(workload_dict={"T1": 0, "T2": 0})
        self.assertEqual(score, 1.0)


class TestMetricsCalcEfficiency(unittest.TestCase):
    def test_efficiency_empty(self):
        self.assertEqual(MetricsCalculator.calc_efficiency([], {}), 1.0)

    def test_efficiency_with_assignments(self):
        jobs = {"J001": _make_job()}
        assigns = [_make_assign()]
        score = MetricsCalculator.calc_efficiency(assigns, jobs)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_efficiency_missing_job_data(self):
        assigns = [_make_assign()]
        score = MetricsCalculator.calc_efficiency(assigns, {})
        self.assertGreaterEqual(score, 0.0)


class TestMetricsCalcCost(unittest.TestCase):
    def test_cost_zero_on_empty(self):
        result = MetricsCalculator.calc_cost([], {}, {}, None)
        self.assertEqual(result, 0.0)

    def test_cost_with_missing_data(self):
        assigns = [_make_assign()]
        result = MetricsCalculator.calc_cost(assigns, {}, {}, None)
        self.assertGreaterEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
