# agents/optimizer_agent.py
"""
SlaveAgent4 - 运筹规划智能体
负责人: 成员A

职责:
- 多目标评分函数
- 方案生成与排序（NSGA-II + 贪心降级）
- 连活优化处理
"""

from typing import List, Dict, Optional
from agents.base_agent import BaseAgent
from interfaces.schemas import (
    Tug, Job, ScheduleSolution, SolutionMetrics,
    Assignment, ChainJobPair, JobType
)
import uuid
import json
from pathlib import Path


class OptimizerAgent(BaseAgent):
    """运筹规划智能体"""

    agent_name = "SlaveAgent4"

    def __init__(self):
        super().__init__()
        self._perception_agent = None
        self.logger.info("OptimizerAgent 初始化完成")

    @property
    def _get_perception(self):
        """延迟单例 PerceptionAgent"""
        if self._perception_agent is None:
            from agents.perception_agent import PerceptionAgent
            self._perception_agent = PerceptionAgent()
        return self._perception_agent

    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        return {"error": "Use generate_solutions directly"}

    def _load_learning_adjustments(self) -> dict:
        """加载自学习参数调整"""
        adj_path = Path(__file__).parent.parent / "data" / "learning_adjustments.json"
        if adj_path.exists():
            try:
                with open(adj_path, "r") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                self.logger.error("加载学习参数失败: %s", e)
        return {}

    def generate_solutions(
        self,
        jobs: List[Job],
        available_tugs: List[Tug],
        chain_pairs: List[ChainJobPair] = None,
        hidden_tasks: List[str] = None
    ) -> List[ScheduleSolution]:
        """
        生成 Top-3 调度方案

        使用 NSGA-II 多目标优化算法
        演示模式下可使用固定解
        """
        chain_pairs = chain_pairs or []
        hidden_tasks = hidden_tasks or []

        if not available_tugs or not jobs:
            self.logger.warning("无可用拖轮或任务，返回空方案")
            return []

        # 加载自学习调整
        self.learning_adjustments = self._load_learning_adjustments()
        if self.learning_adjustments:
            self.logger.info(f"使用自学习调参: {self.learning_adjustments}")
        else:
            self.learning_adjustments = {}

        # 正常模式: NSGA-II 优化
        try:
            optimizer, pareto_front = self._nsga2_solve(jobs, available_tugs, chain_pairs)
            solutions = self._select_named_solutions(
                pareto_front, optimizer, jobs, available_tugs, chain_pairs, hidden_tasks
            )
        except Exception as e:
            self.logger.error(f"NSGA-II算法执行失败: {str(e)}")
            self.logger.warning("使用降级方案")
            solutions = self._fallback_solutions(jobs, available_tugs, chain_pairs, hidden_tasks)

        return solutions

    def _nsga2_solve(self, jobs: List[Job], available_tugs: List[Tug], chain_pairs: List[ChainJobPair]):
        """调用 NSGA-II 求解"""
        from algorithms.nsga2 import NSGA2Optimizer

        optimizer = NSGA2Optimizer(jobs, available_tugs, chain_pairs)
        try:
            pareto_front = optimizer.optimize()
            self.logger.info(f"NSGA-II 完成, 帕累托前沿大小: {len(pareto_front)}")
        except Exception as e:
            self.logger.error(f"NSGA-II优化失败: {e}")
            pareto_front = []
        return optimizer, pareto_front

    def _individual_to_assignments(self, individual, optimizer) -> List[Assignment]:
        """将 NSGA-II 个体转换为 Assignment 列表（支持多拖轮分配）"""
        # 先按任务收集拖轮
        job_to_tugs = {}
        for gene_pos, tug_idx in enumerate(individual):
            if 0 <= tug_idx < len(optimizer.tugs):
                job = optimizer.jobs[optimizer.gene_to_job[gene_pos]]
                tug = optimizer.tugs[tug_idx]
                job_to_tugs.setdefault(job.id, []).append((job, tug))

        # 去重：同一任务不能重复分配同一拖轮
        assignments = []
        seen_per_job = {}
        for job_id, pairs in job_to_tugs.items():
            seen = set()
            for job, tug in pairs:
                if tug.id not in seen:
                    seen.add(tug.id)
                    assignments.append(Assignment(
                        tug_id=tug.id, tug_name=tug.name,
                        job_id=job.id, job_type=job.job_type,
                        score=optimizer._calc_assignment_score(tug, job)
                    ))
        return assignments

    def _select_named_solutions(
        self,
        pareto_front: list,
        optimizer,
        jobs: List[Job],
        available_tugs: List[Tug],
        chain_pairs: List[ChainJobPair],
        hidden_tasks: List[str]
    ) -> List[ScheduleSolution]:
        """从帕累托前沿中选出 3 个互不相同的命名方案"""
        if not pareto_front:
            self.logger.warning("帕累托前沿为空，使用降级方案")
            return self._fallback_solutions(jobs, available_tugs, chain_pairs, hidden_tasks)

        by_cost = sorted(pareto_front, key=lambda ind: ind.fitness.values[0])
        by_balance = sorted(pareto_front, key=lambda ind: -ind.fitness.values[1])
        by_overall = sorted(pareto_front, key=lambda ind: -(
            ind.fitness.values[1] * 0.33 +
            ind.fitness.values[2] * 0.34 -
            ind.fitness.values[0] / 10000 * 0.33
        ))

        # 挑选 3 个互不相同的个体（按适应度值判重）
        candidates = [
            ("省油方案", by_cost),
            ("均衡方案", by_balance),
            ("综合最优", by_overall),
        ]
        picked = []
        picked_keys = set()
        for name, sorted_list in candidates:
            for ind in sorted_list:
                key = tuple(round(v, 2) for v in ind.fitness.values)
                if key not in picked_keys:
                    picked.append((name, ind))
                    picked_keys.add(key)
                    break

        # 如果不足 3 个，从全局补充
        if len(picked) < 3:
            for ind in by_cost:
                key = tuple(round(v, 2) for v in ind.fitness.values)
                if key not in picked_keys:
                    picked.append((f"备选方案{len(picked)+1}", ind))
                    picked_keys.add(key)
                    if len(picked) >= 3:
                        break

        solutions = []
        for name, individual in picked:
            assignments = self._individual_to_assignments(individual, optimizer)
            metrics = self._calc_metrics(assignments)
            solutions.append(ScheduleSolution(
                solution_id=f"SOL-{uuid.uuid4().hex[:8]}",
                name=name,
                assignments=assignments,
                metrics=metrics,
                chain_jobs=chain_pairs,
                hidden_tasks=hidden_tasks
            ))

        return solutions

    def _fallback_solutions(
        self,
        jobs: List[Job],
        available_tugs: List[Tug],
        chain_pairs: List[ChainJobPair],
        hidden_tasks: List[str]
    ) -> List[ScheduleSolution]:
        """NSGA-II 失败时的降级方案 — 生成三个不同策略的贪心解"""
        solutions = []
        for name_suffix, strategy in [
            ("省油方案", "cost"),
            ("均衡方案", "balance"),
            ("综合最优", "overall"),
        ]:
            assignments = self._simple_assign(jobs, available_tugs, chain_pairs=chain_pairs, strategy=strategy)
            metrics = self._calc_metrics(assignments)
            solutions.append(ScheduleSolution(
                solution_id=f"SOL-FB-{uuid.uuid4().hex[:8]}",
                name=name_suffix,
                assignments=assignments,
                metrics=metrics,
                chain_jobs=chain_pairs,
                hidden_tasks=hidden_tasks
            ))
        return solutions

    def _simple_assign(
        self, jobs: List[Job], tugs: List[Tug],
        weight_cost: float = 0.33, weight_balance: float = 0.33,
        chain_pairs: List = None, strategy: str = "cost"
    ) -> List[Assignment]:
        """
        贪心分配算法（降级用）

        考虑连活优先级
        strategy: "cost" 马力最匹配, "balance" 工作量最少优先, "overall" 综合
        """
        chain_pairs = chain_pairs or []
        assignments = []
        available = list(tugs)
        assigned_jobs = set()
        perception_agent = self._get_perception
        from algorithms.nsga2 import NSGA2Optimizer

        tug_workload = {tug.id: 0 for tug in tugs}

        def sort_key(t, per_tug_hp):
            if strategy == "cost":
                return abs(t.horsepower - per_tug_hp)
            elif strategy == "balance":
                return (t.today_work_hours, tug_workload.get(t.id, 0), abs(t.horsepower - per_tug_hp))
            else:
                return (
                    abs(t.horsepower - per_tug_hp) * 0.5 +
                    t.fatigue_value * 0.3 +
                    tug_workload.get(t.id, 0) * 0.2
                )

        for chain_pair in chain_pairs:
            job1 = next((j for j in jobs if j.id == chain_pair.job1_id), None)
            job2 = next((j for j in jobs if j.id == chain_pair.job2_id), None)

            if not job1 or not job2:
                continue
            if job1.id in assigned_jobs or job2.id in assigned_jobs:
                continue

            needed = max(job1.required_tug_count, job2.required_tug_count, 1)
            if len(available) < needed:
                continue

            per_tug_hp = job1.required_horsepower / needed
            sorted_tugs = sorted(available, key=lambda t: sort_key(t, per_tug_hp))
            chain_tugs = sorted_tugs[:needed]

            for tug in chain_tugs:
                assignments.append(Assignment(
                    tug_id=tug.id, tug_name=tug.name,
                    job_id=job1.id, job_type=job1.job_type,
                    score=NSGA2Optimizer._calc_assignment_score(tug, job1)
                ))
                assignments.append(Assignment(
                    tug_id=tug.id, tug_name=tug.name,
                    job_id=job2.id, job_type=job2.job_type,
                    score=NSGA2Optimizer._calc_assignment_score(tug, job2)
                ))
                tug_workload[tug.id] += 2
                available.remove(tug)

            assigned_jobs.add(job1.id)
            assigned_jobs.add(job2.id)

        for job in jobs:
            if job.id in assigned_jobs:
                continue

            needed = max(job.required_tug_count, 1)
            if len(available) < needed:
                break

            per_tug_hp = job.required_horsepower / needed
            sorted_tugs = sorted(available, key=lambda t: sort_key(t, per_tug_hp))
            job_tugs = sorted_tugs[:needed]

            for tug in job_tugs:
                assignments.append(Assignment(
                    tug_id=tug.id, tug_name=tug.name,
                    job_id=job.id, job_type=job.job_type,
                    score=NSGA2Optimizer._calc_assignment_score(tug, job)
                ))
                tug_workload[tug.id] += 1
                available.remove(tug)

            assigned_jobs.add(job.id)

        return assignments

    def _calc_metrics(
        self, assignments: List[Assignment],
        weight_cost: float = None,
        weight_balance: float = None,
        weight_efficiency: float = None
    ) -> SolutionMetrics:
        """计算方案评价指标 (权重可从自学习调整加载)"""
        adj = getattr(self, 'learning_adjustments', {})
        weight_cost = weight_cost or adj.get('weight_cost', 0.33)
        weight_balance = weight_balance or adj.get('weight_balance', 0.33)
        weight_efficiency = weight_efficiency or adj.get('weight_efficiency', 0.34)

        total_cost = self.calc_cost(assignments)
        balance_score = self.calc_balance(assignments)
        efficiency_score = self.calc_efficiency(assignments)

        num_jobs = len(set(a.job_id for a in assignments)) if assignments else 1
        cost_per_job_baseline = 2000  # 单任务参考成本
        cost_score = 1.0 - min(total_cost / (num_jobs * cost_per_job_baseline), 1.0)

        overall_score = (
            cost_score * weight_cost +
            balance_score * weight_balance +
            efficiency_score * weight_efficiency
        )

        overall_score = max(0.0, min(1.0, overall_score))

        return SolutionMetrics(
            total_cost=total_cost,
            balance_score=balance_score,
            efficiency_score=efficiency_score,
            overall_score=round(overall_score, 2)
        )

    def calc_cost(self, assignments: List[Assignment]) -> float:
        """计算燃油成本（委托到 MetricsCalculator）"""
        from data.loader import load_tugs, load_jobs
        from agents.perception_agent import PerceptionAgent
        from utils.metrics_calculator import MetricsCalculator

        tugs_dict = {t.id: t for t in load_tugs()}
        jobs_dict = {j.id: j for j in load_jobs()}
        return MetricsCalculator.calc_cost(assignments, tugs_dict, jobs_dict, PerceptionAgent())

    def calc_balance(self, assignments: List[Assignment]) -> float:
        """计算作业均衡度（委托到 MetricsCalculator）"""
        from utils.metrics_calculator import MetricsCalculator
        return MetricsCalculator.calc_balance(assignments=assignments)

    def calc_efficiency(self, assignments: List[Assignment]) -> float:
        """计算效率评分（委托到 MetricsCalculator）"""
        from data.loader import load_jobs
        from utils.metrics_calculator import MetricsCalculator

        jobs_dict = {j.id: j for j in load_jobs()}
        return MetricsCalculator.calc_efficiency(assignments, jobs_dict)
