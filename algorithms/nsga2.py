# algorithms/nsga2.py
"""
NSGA-II 多目标优化算法实现

用于拖轮调度的多目标优化问题
"""

import random
import logging
import numpy as np
from deap import base, creator, tools, algorithms
from typing import List, Dict, Tuple
from interfaces.schemas import Tug, Job, Assignment, SolutionMetrics, FatigueLevel

logger = logging.getLogger("NSGA2")


class NSGA2Optimizer:
    """
    NSGA-II 优化器类
    """

    def __init__(self, jobs: List[Job], tugs: List[Tug], chain_pairs: List = None):
        from config.algorithm_config import AlgorithmConfig
        from agents.perception_agent import PerceptionAgent

        self.jobs = jobs
        self.tugs = tugs
        self.chain_pairs = chain_pairs or []

        self.tugs_dict = {t.id: t for t in tugs}
        self.jobs_dict = {j.id: j for j in jobs}

        # 基因到任务的映射：支持 required_tug_count > 1
        # 每个 Job 占用 required_tug_count 个基因位
        self.gene_to_job = []
        for i, job in enumerate(self.jobs):
            count = max(job.required_tug_count, 1)
            self.gene_to_job.extend([i] * count)
        self.total_genes = len(self.gene_to_job)
        self.perception_agent = PerceptionAgent()

        config = AlgorithmConfig.get_config("nsga2")
        self.population_size = config["population_size"]
        self.generations = config["generations"]
        self.crossover_prob = config["crossover_prob"]
        self.mutation_prob = config["mutation_prob"]

        self._setup_deap()

    def _setup_deap(self):
        for attr_name in ["FitnessMulti", "Individual"]:
            if hasattr(creator, attr_name):
                delattr(creator, attr_name)

        # 多目标权重:
        #   (-1.0, 1.0, 1.0) → (成本 最小化, 均衡度 最大化, 效率 最大化)
        #   _evaluate_fitness 返回 (total_cost, balance_score, efficiency_score)
        weights = (-1.0, 1.0, 1.0)
        creator.create("FitnessMulti", base.Fitness, weights=weights)
        creator.create("Individual", list, fitness=creator.FitnessMulti)

        self.toolbox = base.Toolbox()

        def generate_gene():
            if not self.tugs or not self.jobs:
                return [0] * self.total_genes
            return [random.randint(0, len(self.tugs) - 1) for _ in range(self.total_genes)]

        self.toolbox.register("individual", tools.initIterate, creator.Individual, generate_gene)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", tools.mutUniformInt, low=0, up=len(self.tugs) - 1, indpb=0.1)
        self.toolbox.register("select", tools.selNSGA2)
        self.toolbox.register("evaluate", self._evaluate_fitness)

    def _evaluate_fitness(self, individual: List[int]) -> Tuple[float, float, float]:
        from utils.metrics_calculator import MetricsCalculator

        # 1. 先按任务收集分配的拖轮（支持 required_tug_count > 1）
        job_to_tugs = {job.id: [] for job in self.jobs}
        tug_workload = {tug.id: 0 for tug in self.tugs}

        for gene_pos, tug_idx in enumerate(individual):
            if 0 <= tug_idx < len(self.tugs):
                job = self.jobs[self.gene_to_job[gene_pos]]
                tug = self.tugs[tug_idx]
                job_to_tugs[job.id].append(tug)
                tug_workload[tug.id] += 1

        # 去重：同一任务不能重复分配同一拖轮
        for job_id in job_to_tugs:
            seen = set()
            unique = []
            for tug in job_to_tugs[job_id]:
                if tug.id not in seen:
                    seen.add(tug.id)
                    unique.append(tug)
            job_to_tugs[job_id] = unique

        # 根据去重结果重算工作量
        tug_workload = {tug.id: 0 for tug in self.tugs}
        for job_id, tugs in job_to_tugs.items():
            for tug in tugs:
                tug_workload[tug.id] += 1

        # 2. 生成逐个拖轮-任务的分配列表
        assignments = []
        for job in self.jobs:
            for tug in job_to_tugs.get(job.id, []):
                score = self._calc_assignment_score(tug, job)
                assignments.append(Assignment(
                    tug_id=tug.id, tug_name=tug.name,
                    job_id=job.id, job_type=job.job_type, score=score
                ))

        # 3. 使用统一的 MetricsCalculator 计算指标
        total_cost = MetricsCalculator.calc_cost(
            assignments, self.tugs_dict, self.jobs_dict, self.perception_agent
        )

        # 4. 约束惩罚：不满 required_tug_count 或马力不足的施加巨大惩罚
        PENALTY_PER_MISSING_TUG = 50000.0
        total_penalty = 0.0
        for job in self.jobs:
            unique_count = len(job_to_tugs.get(job.id, []))
            needed = max(job.required_tug_count, 1)
            if unique_count < needed:
                missing = needed - unique_count
                total_penalty += missing * PENALTY_PER_MISSING_TUG
        total_cost += total_penalty
        balance_score = MetricsCalculator.calc_balance(workload_dict=tug_workload)
        efficiency_score = MetricsCalculator.calc_efficiency(assignments, self.jobs_dict)

        # 5. 连活奖励：链式任务对共享拖轮则减少成本
        for chain in self.chain_pairs:
            tugs_job1 = {a.tug_id for a in assignments if a.job_id == chain.job1_id}
            tugs_job2 = {a.tug_id for a in assignments if a.job_id == chain.job2_id}
            if tugs_job1 & tugs_job2:  # 至少共享一艘拖轮
                total_cost -= chain.cost_saving

        # 运行时验证
        if total_cost < 0:
            total_cost = 0.0
        if not (0.0 <= balance_score <= 1.0):
            raise ValueError(f"均衡度越界: {balance_score}, 应在[0,1]")
        if not (0.0 <= efficiency_score <= 1.0):
            raise ValueError(f"效率评分越界: {efficiency_score}, 应在[0,1]")

        return total_cost, balance_score, efficiency_score

    @staticmethod
    def _calc_assignment_score(tug: Tug, job: Job) -> float:
        """基于拖轮与任务的匹配度动态计算评分 (0-1)"""
        # 1. 马力匹配度 (权重 0.5) — 使用单船所需最低马力
        per_tug_hp = job.required_horsepower / max(job.required_tug_count, 1)
        if per_tug_hp > 0:
            horsepower_ratio = tug.horsepower / per_tug_hp
            if horsepower_ratio >= 1.0:
                horsepower_score = 1.0
            else:
                horsepower_score = max(0.0, horsepower_ratio)
        else:
            horsepower_score = 1.0

        # 2. 疲劳等级惩罚 (权重 0.3)
        fatigue_map = {
            FatigueLevel.GREEN: 1.0,
            FatigueLevel.YELLOW: 0.7,
            FatigueLevel.RED: 0.3
        }
        fatigue_score = fatigue_map.get(tug.fatigue_level, 1.0)

        # 3. 工作时长惩罚 (权重 0.2)
        work_hours = getattr(tug, 'today_work_hours', 0.0)
        work_hours_score = max(0.0, 1.0 - work_hours / 12.0)

        # 综合评分
        score = (horsepower_score * 0.5 + fatigue_score * 0.3 + work_hours_score * 0.2)
        return round(max(0.0, min(1.0, score)), 4)

    def _calc_cost(self, assignments: List[Assignment]) -> float:
        from utils.metrics_calculator import MetricsCalculator
        return MetricsCalculator.calc_cost(assignments, self.tugs_dict, self.jobs_dict, self.perception_agent)

    def _estimate_default_distance(self, tug_position, target_berth_id: str) -> float:
        return self.perception_agent.estimate_distance_from_position(tug_position, target_berth_id)

    def _calc_balance(self, tug_workload: Dict[str, int]) -> float:
        from utils.metrics_calculator import MetricsCalculator
        return MetricsCalculator.calc_balance(workload_dict=tug_workload)

    def _calc_efficiency(self, assignments: List[Assignment]) -> float:
        from utils.metrics_calculator import MetricsCalculator
        return MetricsCalculator.calc_efficiency(assignments, self.jobs_dict)

    def optimize(self) -> list:
        population = self.toolbox.population(n=self.population_size)

        invalid_ind = [ind for ind in population if not ind.fitness.valid]
        fits = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
        for fit, ind in zip(fits, invalid_ind):
            ind.fitness.values = fit

        # 初始化拥挤度距离，供 selTournamentDCD 使用
        for ind in population:
            ind.fitness.crowding_dist = 0.0

        for gen in range(self.generations):
            # 1. 父代选择（基于拥挤度距离的锦标赛选择）
            offspring = tools.selTournamentDCD(population, len(population))
            offspring = [self.toolbox.clone(ind) for ind in offspring]

            # 2. 交叉和变异生成子代
            offspring = algorithms.varAnd(offspring, self.toolbox, cxpb=self.crossover_prob, mutpb=self.mutation_prob)

            # 3. 评估子代适应度
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fits = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
            for fit, ind in zip(fits, invalid_ind):
                ind.fitness.values = fit

            # 4. 合并父代和子代，通过NSGA-II选择新一代
            population = self.toolbox.select(population + offspring, k=self.population_size)

        pareto_front = tools.sortNondominated(population, len(population), first_front_only=True)[0]

        return pareto_front

    def get_best_solutions(self, num_solutions: int = 3) -> List[Dict]:
        pareto_front = self.optimize()

        solutions = []
        for individual in pareto_front[:num_solutions]:
            assignments = []
            for gene_pos, tug_idx in enumerate(individual):
                if 0 <= tug_idx < len(self.tugs):
                    job = self.jobs[self.gene_to_job[gene_pos]]
                    tug = self.tugs[tug_idx]
                    assignments.append(Assignment(
                        tug_id=tug.id, tug_name=tug.name,
                        job_id=job.id, job_type=job.job_type,
                        score=self._calc_assignment_score(tug, job)
                    ))
            cost, balance, efficiency = individual.fitness.values
            solutions.append({
                "assignments": assignments,
                "fitness": {"cost": cost, "balance_score": balance, "efficiency_score": efficiency}
            })
        return solutions
