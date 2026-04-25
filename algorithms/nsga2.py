# algorithms/nsga2.py
"""
NSGA-II 多目标优化算法实现

用于拖轮调度的多目标优化问题
"""

import random
import numpy as np
from deap import base, creator, tools, algorithms
from typing import List, Dict, Tuple
from interfaces.schemas import Tug, Job, Assignment, SolutionMetrics, FatigueLevel


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

        self.toolbox = base.Toolbox()

        def generate_gene():
            if not self.tugs or not self.jobs:
                return [0] * len(self.jobs)
            return [random.randint(0, len(self.tugs) - 1) for _ in self.jobs]

        self.toolbox.register("individual", tools.initIterate, creator.Individual, generate_gene)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", tools.mutUniformInt, low=0, up=len(self.tugs) - 1, indpb=0.1)
        self.toolbox.register("select", tools.selNSGA2)
        self.toolbox.register("evaluate", self._evaluate_fitness)

    def _evaluate_fitness(self, individual: List[int]) -> Tuple[float, float, float]:
        assignments = []
        tug_workload = {tug.id: 0 for tug in self.tugs}

        for i, job in enumerate(self.jobs):
            tug_idx = individual[i]
            if 0 <= tug_idx < len(self.tugs):
                tug = self.tugs[tug_idx]
                score = self._calc_assignment_score(tug, job)
                assignments.append(Assignment(
                    tug_id=tug.id,
                    tug_name=tug.name,
                    job_id=job.id,
                    job_type=job.job_type,
                    score=score
                ))
                tug_workload[tug.id] += 1

        total_cost = self._calc_cost(assignments)
        balance_score = self._calc_balance(tug_workload)
        efficiency_score = self._calc_efficiency(assignments)

        # 运行时验证: 确保目标值范围与权重方向一致
        if total_cost < 0:
            raise ValueError(f"成本值异常: {total_cost}, 成本应≥0 (最小化目标)")
        if not (0.0 <= balance_score <= 1.0):
            raise ValueError(f"均衡度越界: {balance_score}, 应在[0,1] (最大化目标)")
        if not (0.0 <= efficiency_score <= 1.0):
            raise ValueError(f"效率评分越界: {efficiency_score}, 应在[0,1] (最大化目标)")

        return total_cost, balance_score, efficiency_score

    @staticmethod
    def _calc_assignment_score(tug: Tug, job: Job) -> float:
        """基于拖轮与任务的匹配度动态计算评分 (0-1)"""
        # 1. 马力匹配度 (权重 0.5)
        if job.required_horsepower > 0:
            horsepower_ratio = tug.horsepower / job.required_horsepower
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
        total_cost = 0.0
        OIL_PRICE_PER_NM = 50.0

        for assignment in assignments:
            tug = self.tugs_dict.get(assignment.tug_id)
            job = self.jobs_dict.get(assignment.job_id)

            if not tug or not job:
                continue

            if tug.berth_id:
                distance = self.perception_agent.get_berth_distance(tug.berth_id, job.target_berth_id)
            else:
                distance = self._estimate_default_distance(tug.position, job.target_berth_id)

            total_cost += distance * OIL_PRICE_PER_NM

        return total_cost

    def _estimate_default_distance(self, tug_position, target_berth_id: str) -> float:
        return self.perception_agent.estimate_distance_from_position(tug_position, target_berth_id)

    def _calc_balance(self, tug_workload: Dict[str, int]) -> float:
        import statistics

        if not tug_workload:
            return 1.0

        job_counts = list(tug_workload.values())
        mean_jobs = statistics.mean(job_counts)

        if mean_jobs == 0:
            return 1.0

        if len(job_counts) > 1:
            variance = statistics.variance(job_counts)
        else:
            variance = 0.0

        balance_score = 1 - (variance / mean_jobs)
        balance_score = max(0.0, min(1.0, balance_score))

        return balance_score

    def _calc_efficiency(self, assignments: List[Assignment]) -> float:
        total_wait_time = 0.0
        max_wait_time = 2.0

        for assignment in assignments:
            job = self.jobs_dict.get(assignment.job_id)
            if not job:
                continue

            if job.job_type == "BERTHING":
                estimated_wait_time = 0.6
            elif job.job_type == "UNBERTHING":
                estimated_wait_time = 0.4
            else:
                estimated_wait_time = 0.5

            total_wait_time += estimated_wait_time

        if not assignments:
            return 1.0

        avg_wait_time = total_wait_time / len(assignments)
        efficiency_score = 1.0 - (avg_wait_time / max_wait_time)
        efficiency_score = max(0.0, min(1.0, efficiency_score))

        return efficiency_score

    def optimize(self) -> list:
        population = self.toolbox.population(n=self.population_size)

        invalid_ind = [ind for ind in population if not ind.fitness.valid]
        fits = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
        for fit, ind in zip(fits, invalid_ind):
            ind.fitness.values = fit

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
            for job_idx, tug_idx in enumerate(individual):
                if 0 <= tug_idx < len(self.tugs):
                    job = self.jobs[job_idx]
                    tug = self.tugs[tug_idx]
                    assignments.append(Assignment(
                        tug_id=tug.id,
                        tug_name=tug.name,
                        job_id=job.id,
                        job_type=job.job_type,
                        score=self._calc_assignment_score(tug, job)
                    ))
            cost, balance, efficiency = individual.fitness.values
            solutions.append({
                "assignments": assignments,
                "fitness": {
                    "cost": cost,
                    "balance_score": balance,
                    "efficiency_score": efficiency
                }
            })

        return solutions
