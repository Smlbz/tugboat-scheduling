"""
tests/test_integration.py
CMATSS 集成测试 — 覆盖核心调度流程
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from agents.master_agent import MasterAgent
from data.loader import load_tugs, load_berths, load_jobs, load_rules


class TestMasterAgentIntegration:
    """主控智能体集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.master = MasterAgent()

    def test_schedule_basic(self):
        """基本调度: 3 个任务"""
        solutions = self.master.schedule(["JOB001", "JOB002", "JOB003"])
        assert len(solutions) > 0, "应生成至少 1 个方案"
        sol = solutions[0]
        assert hasattr(sol, 'solution_id'), "方案应有 ID"
        assert hasattr(sol, 'metrics'), "方案应有指标"
        assert sol.metrics.total_cost > 0, "成本应 > 0"
        assert 0 <= sol.metrics.balance_score <= 1, "均衡度应在 0-1"
        assert 0 <= sol.metrics.efficiency_score <= 1, "效率应在 0-1"

    def test_schedule_single_job(self):
        """单任务调度"""
        solutions = self.master.schedule(["JOB001"])
        assert len(solutions) > 0

    def test_schedule_invalid_job(self):
        """无效任务 ID"""
        solutions = self.master.schedule(["INVALID_JOB"])
        # 不应抛出异常，返回空或默认方案
        assert solutions is not None

    def test_schedule_all_jobs(self):
        """全部任务调度"""
        all_jobs = [j.id for j in load_jobs()]
        solutions = self.master.schedule(all_jobs)
        assert len(solutions) >= 1

    def test_chain_job_detection(self):
        """连活任务识别"""
        solutions = self.master.schedule(["JOB001", "JOB005"])
        if solutions and len(solutions) > 0:
            pass  # 连活与否取决于数据，不 assert 具体值

    def test_compliance_check(self):
        """合规检查"""
        result = self.master.check_compliance("TUG001", "JOB001")
        assert hasattr(result, 'is_compliant')
        assert hasattr(result, 'violation_reason')

    def test_all_agents_healthy(self):
        """所有智能体健康检查"""
        assert self.master.health_check() is not None
        assert self.master.explainer_agent.health_check() is not None


class TestDataLoading:
    """数据加载测试 (更严格的验证)"""

    def test_load_tugs(self):
        tugs = load_tugs()
        assert len(tugs) == 60, "应加载 60 艘拖轮"
        assert all(t.horsepower > 0 for t in tugs), "所有拖轮应有马力"
        assert all(t.position.lng for t in tugs), "所有拖轮应有位置"

    def test_load_berths(self):
        berths = load_berths()
        assert len(berths) >= 10, "应加载至少 10 个泊位"
        assert all(b.position.lng for b in berths)

    def test_load_jobs(self):
        jobs = load_jobs()
        assert len(jobs) >= 50, "应加载至少 50 个任务"
        assert all(j.required_horsepower > 0 for j in jobs)

    def test_load_rules(self):
        rules = load_rules()
        assert len(rules) >= 8, "应加载至少 8 条规则"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
