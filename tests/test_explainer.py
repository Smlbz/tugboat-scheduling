"""ExplainerAgent 单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import unittest
from agents.explainer_agent import ExplainerAgent


class TestExplainerAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ExplainerAgent()

    def test_cache_and_explain(self):
        sol = {
            "name": "test",
            "metrics": {"total_cost": 1000, "balance_score": 0.5, "efficiency_score": 0.5, "overall_score": 0.5},
            "assignments": [],
            "chain_jobs": []
        }
        self.agent.cache_solution("SOL-001", sol)
        resp = self.agent.explain_solution("SOL-001")
        # 模板降级应返回方案名（LLM 不可用时）
        self.assertTrue(len(resp.explanation) > 0)

    def test_explain_nonexistent(self):
        resp = self.agent.explain_solution("NONEXIST")
        self.assertIn("未找到", resp.explanation)

    def test_counterfactual_without_change(self):
        sol = {
            "name": "test",
            "metrics": {"total_cost": 1000, "balance_score": 0.5, "efficiency_score": 0.5, "overall_score": 0.5},
            "assignments": [],
            "chain_jobs": []
        }
        self.agent.cache_solution("SOL-001", sol)
        resp = self.agent.counterfactual_reasoning("SOL-001")
        self.assertIsNotNone(resp.counterfactual)
        self.assertIsNotNone(resp.explanation)

    def test_cache_fifo_eviction(self):
        self.agent._max_cache = 3
        for i in range(5):
            self.agent.cache_solution(f"SOL-{i:03d}", {"name": f"s{i}"})
        self.assertEqual(len(self.agent.solution_cache), 3)

    def test_get_cached_solutions(self):
        self.agent.cache_solution("SOL-001", {"name": "s1"})
        cached = self.agent.get_cached_solutions()
        self.assertGreaterEqual(len(cached), 1)
        self.assertIn("solution_id", cached[0])

    def test_process_explain_action(self):
        sol = {
            "name": "test",
            "metrics": {"total_cost": 1000, "balance_score": 0.5, "efficiency_score": 0.5, "overall_score": 0.5},
            "assignments": [],
            "chain_jobs": []
        }
        self.agent.cache_solution("SOL-001", sol)
        result = self.agent.process({"action": "explain", "solution_id": "SOL-001"})
        self.assertIn("explanation", result)

    def test_process_health_action(self):
        result = self.agent.process({"action": "health"})
        self.assertEqual(result.get("status"), "healthy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
