# agents/optimizer_agent.py
"""
SlaveAgent4 - 运筹规划智能体
负责人: 成员A

职责:
- 多目标评分函数
- 方案生成与排序
- 连活优化处理
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from interfaces.schemas import (
    Tug, Job, ScheduleSolution, SolutionMetrics,
    Assignment, ChainJobPair, JobType
)
import uuid


class OptimizerAgent(BaseAgent):
    """运筹规划智能体"""
    
    agent_name = "SlaveAgent4"
    
    def __init__(self):
        super().__init__()
        self.logger.info("OptimizerAgent 初始化完成")
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        return {"error": "Use generate_solutions directly"}
    
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
        """
        chain_pairs = chain_pairs or []
        hidden_tasks = hidden_tasks or []
        
        if not available_tugs or not jobs:
            self.logger.warning("无可用拖轮或任务，返回空方案")
            return []
        
        try:
            optimizer, pareto_front = self._nsga2_solve(jobs, available_tugs, chain_pairs)
            solutions = self._select_named_solutions(
                pareto_front, optimizer, jobs, available_tugs, chain_pairs, hidden_tasks
            )
        except Exception as e:
            self.logger.error(f"NSGA-II算法执行失败: {str(e)}")
            self.logger.warning("使用降级方案")
            solutions = self._fallback_solutions(jobs, available_tugs, chain_pairs, hidden_tasks)
        
        for i, solution in enumerate(solutions, 1):
            self.logger.info(f"\n=== 方案 {i}: {solution.name} ===")
            self.logger.info(f"方案ID: {solution.solution_id}")
            self.logger.info(f"总燃油成本: ¥{solution.metrics.total_cost}")
            self.logger.info(f"均衡度评分: {solution.metrics.balance_score}")
            self.logger.info(f"效率评分: {solution.metrics.efficiency_score}")
            self.logger.info(f"综合评分: {solution.metrics.overall_score}")
            
            self.logger.info("\n分配详情:")
            for assignment in solution.assignments:
                self.logger.info(f"  - 拖轮: {assignment.tug_name} ({assignment.tug_id}) → 任务: {assignment.job_id} ({assignment.job_type})")
            
            if solution.chain_jobs:
                self.logger.info("\n连活信息:")
                for chain in solution.chain_jobs:
                    self.logger.info(f"  - 任务对: {chain.job1_id} → {chain.job2_id}")
                    self.logger.info(f"    时间间隔: {chain.interval_hours}小时, 距离: {chain.distance_nm}海里, 节省成本: ¥{chain.cost_saving}")
            
            self.logger.info("=" * 50)
        
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
        assignments = []
        for gene_pos, tug_idx in enumerate(individual):
            if 0 <= tug_idx < len(optimizer.tugs):
                job = optimizer.jobs[optimizer.gene_to_job[gene_pos]]
                tug = optimizer.tugs[tug_idx]
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
        """从帕累托前沿中选出 3 个命名方案"""
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
        
        candidates = [
            ("省油方案", by_cost[0]),
            ("均衡方案", by_balance[0]),
            ("综合最优", by_overall[0]),
        ]
        
        solutions = []
        for name, individual in candidates:
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
        """帕累托前沿为空时的降级方案（贪心）"""
        assignments = self._simple_assign(jobs, available_tugs, chain_pairs=chain_pairs)
        metrics = self._calc_metrics(assignments)
        return [ScheduleSolution(
            solution_id=f"SOL-{uuid.uuid4().hex[:8]}",
            name="降级方案",
            assignments=assignments,
            metrics=metrics,
            chain_jobs=chain_pairs,
            hidden_tasks=hidden_tasks
        )]
    
    def _simple_assign(
        self, jobs: List[Job], tugs: List[Tug],
        weight_cost: float = 0.33, weight_balance: float = 0.33,
        chain_pairs: List = None
    ) -> List[Assignment]:
        """
        贪心分配算法（降级用）

        考虑连活优先级
        根据权重参数调整分配策略
        """
        from agents.perception_agent import PerceptionAgent
        
        chain_pairs = chain_pairs or []
        assignments = []
        available = list(tugs)
        assigned_jobs = set()
        perception_agent = PerceptionAgent()
        from algorithms.nsga2 import NSGA2Optimizer

        tug_workload = {tug.id: 0 for tug in tugs}

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
            sorted_tugs = sorted(available, key=lambda t: abs(t.horsepower - per_tug_hp))
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
            sorted_tugs = sorted(available, key=lambda t: abs(t.horsepower - per_tug_hp))
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
        weight_cost: float = 0.33,
        weight_balance: float = 0.33,
        weight_efficiency: float = 0.34
    ) -> SolutionMetrics:
        """计算方案评价指标"""
        total_cost = self.calc_cost(assignments)
        balance_score = self.calc_balance(assignments)
        efficiency_score = self.calc_efficiency(assignments)
        
        overall_score = (
            total_cost * (-weight_cost) / 10000 +
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
