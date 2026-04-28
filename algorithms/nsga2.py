# algorithms/nsga2.py
"""
NSGA-II 多目标优化算法实现

用于拖轮调度的多目标优化问题
"""

import random
import logging
import time
import signal
import numpy as np
from deap import base, creator, tools, algorithms
from typing import List, Dict, Tuple
from interfaces.schemas import Tug, Job, Assignment, SolutionMetrics, FatigueLevel

logger = logging.getLogger("NSGA2")


class NSGA2Optimizer:
    """
    NSGA-II 优化器类
    """

    def __init__(self, jobs: List[Job], tugs: List[Tug], chain_pairs: List = None,
                 disable_compliance: bool = False):
        from config.algorithm_config import AlgorithmConfig
        from agents.perception_agent import PerceptionAgent

        self.jobs = jobs
        self.tugs = tugs
        self.chain_pairs = chain_pairs or []
        self.disable_compliance = disable_compliance

        self.tugs_dict = {t.id: t for t in tugs}
        self.jobs_dict = {j.id: j for j in jobs}

        # 基因到任务的映射：支持 required_tug_count > 1
        self.gene_to_job = []
        for i, job in enumerate(self.jobs):
            count = max(job.required_tug_count, 1)
            self.gene_to_job.extend([i] * count)
        self.total_genes = len(self.gene_to_job)
        self.perception_agent = PerceptionAgent()

        # 自适应种群: 任务少则缩小搜索空间
        job_count = len(self.jobs)
        if job_count <= 5:
            base_pop, base_gen = 20, 15
        elif job_count <= 10:
            base_pop, base_gen = 40, 20
        else:
            base_pop, base_gen = 60, 30

        config = AlgorithmConfig.get_config("nsga2")
        self.population_size = base_pop
        self.generations = base_gen
        self.crossover_prob = config["crossover_prob"]
        self.mutation_prob = config["mutation_prob"]

        log_msg = f"任务数={job_count}, 种群={self.population_size}, 代数={self.generations}, 总评估≈{self.population_size + self.population_size * self.generations}"
        logger.info(log_msg)

        # 合规预缓存: 一次跑完所有 (tug, job) 组合, 避免 GA 循环中重复调用
        self._compliance_cache = self._build_compliance_cache()
        # Ctrl+C 中断标记
        self._interrupted = False

        self._setup_deap()

    def _build_compliance_cache(self) -> Dict[Tuple[str, str], bool]:
        """预计算所有 (tug, job) 合规结果, 跳过 ChromaDB/违规原因生成"""
        if self.disable_compliance or not self.tugs or not self.jobs:
            return {}
        try:
            from engine.rule_engine import RuleEngine
            re = RuleEngine()
            cache = {}
            total = len(self.tugs) * len(self.jobs)
            for job in self.jobs:
                for tug in self.tugs:
                    violations = re.check_compliance(tug, job, [], {})
                    cache[(tug.id, job.id)] = len(violations) == 0
            logger.info(f"合规缓存就绪: {total} 项 (RuleEngine 直查, 无向量库)")
            return cache
        except Exception as e:
            logger.error(f"合规缓存构建失败, 跳过: {e}", exc_info=True)
            return {}

    def _setup_deap(self):
        for attr_name in ["FitnessMulti", "Individual"]:
            if hasattr(creator, attr_name):
                delattr(creator, attr_name)

        weights = (-1.0, 1.0, 1.0)
        creator.create("FitnessMulti", base.Fitness, weights=weights)
        creator.create("Individual", list, fitness=creator.FitnessMulti)

        self.toolbox = base.Toolbox()

        tug_count = len(self.tugs) if self.tugs else 1
        def generate_gene():
            if not self.tugs or not self.jobs:
                return [0] * self.total_genes
            return [random.randint(0, tug_count - 1) for _ in range(self.total_genes)]

        self.toolbox.register("individual", tools.initIterate, creator.Individual, generate_gene)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", tools.mutUniformInt, low=0, up=max(0, tug_count - 1), indpb=0.1)
        self.toolbox.register("select", tools.selNSGA2)
        self.toolbox.register("evaluate", self._evaluate_fitness)

    def _evaluate_fitness(self, individual: List[int]) -> Tuple[float, float, float]:
        from utils.metrics_calculator import MetricsCalculator

        # 1. 按任务收集分配的拖轮
        job_to_tugs = {job.id: [] for job in self.jobs}
        tug_workload = {tug.id: 0 for tug in self.tugs}

        for gene_pos, tug_idx in enumerate(individual):
            if 0 <= tug_idx < len(self.tugs):
                job = self.jobs[self.gene_to_job[gene_pos]]
                tug = self.tugs[tug_idx]
                job_to_tugs[job.id].append(tug)
                tug_workload[tug.id] += 1

        # 去重
        for job_id in list(job_to_tugs.keys()):
            seen = set()
            unique = []
            for tug in job_to_tugs[job_id]:
                if tug.id not in seen:
                    seen.add(tug.id)
                    unique.append(tug)
            job_to_tugs[job_id] = unique

        # 重算工作量
        tug_workload = {tug.id: 0 for tug in self.tugs}
        for job_id, tugs_list in job_to_tugs.items():
            for tug in tugs_list:
                tug_workload[tug.id] += 1

        # 2. 生成分配列表
        assignments = []
        for job in self.jobs:
            for tug in job_to_tugs.get(job.id, []):
                score = self._calc_assignment_score(tug, job)
                assignments.append(Assignment(
                    tug_id=tug.id, tug_name=tug.name,
                    job_id=job.id, job_type=job.job_type, score=score
                ))

        # 3. 计算成本
        total_cost = MetricsCalculator.calc_cost(
            assignments, self.tugs_dict, self.jobs_dict, self.perception_agent
        )

        # 4. 约束惩罚
        PENALTY_PER_MISSING_TUG = 50000.0
        total_penalty = 0.0
        for job in self.jobs:
            unique_count = len(job_to_tugs.get(job.id, []))
            needed = max(job.required_tug_count, 1)
            if unique_count < needed:
                total_penalty += (needed - unique_count) * PENALTY_PER_MISSING_TUG
        total_cost += total_penalty

        # 5. 合规惩罚 (用预缓存, 避免重复调用 ComplianceAgent)
        VIOLATION_PENALTY = 100000.0
        compliance_violations = 0
        if self._compliance_cache:
            for job in self.jobs:
                for tug in job_to_tugs.get(job.id, []):
                    if not self._compliance_cache.get((tug.id, job.id), True):
                        compliance_violations += 1
        elif not self.disable_compliance:
            from agents.compliance_agent import ComplianceAgent
            ca = getattr(self, '_compliance_agent', None)
            if ca is None:
                ca = ComplianceAgent()
                self._compliance_agent = ca
            for job in self.jobs:
                for tug in job_to_tugs.get(job.id, []):
                    result = ca.check_compliance(tug.id, job.id)
                    if not result.is_compliant:
                        compliance_violations += 1
        total_cost += compliance_violations * VIOLATION_PENALTY

        balance_score = MetricsCalculator.calc_balance(workload_dict=tug_workload)
        efficiency_score = MetricsCalculator.calc_efficiency(assignments, self.jobs_dict)

        # 6. 连活奖励
        for chain in self.chain_pairs:
            tugs_job1 = {a.tug_id for a in assignments if a.job_id == chain.job1_id}
            tugs_job2 = {a.tug_id for a in assignments if a.job_id == chain.job2_id}
            if tugs_job1 & tugs_job2:
                total_cost -= chain.cost_saving

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

    def _signal_handler(self, signum, frame):
        """Ctrl+SIGINT 处理: 标记中断, 当前代完成后退出"""
        self._interrupted = True
        logger.warning("收到中断信号, 当前代完成后停止...")

    def optimize(self) -> list:
        t_start = time.time()
        self.gen_history = []
        self._interrupted = False

        # 注册 Ctrl+C 处理器 (主线程有效)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
        except (ValueError, AttributeError):
            pass  # 非主线程忽略

        population = self.toolbox.population(n=self.population_size)

        invalid_ind = [ind for ind in population if not ind.fitness.valid]
        fits = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
        for fit, ind in zip(fits, invalid_ind):
            ind.fitness.values = fit

        for ind in population:
            ind.fitness.crowding_dist = 0.0

        t_eval = time.time()
        for gen in range(self.generations):
            if self._interrupted:
                logger.info(f"中断标记, 提前退出于第 {gen} 代")
                break

            costs = [ind.fitness.values[0] for ind in population]
            self.gen_history.append({
                "gen": gen,
                "avg_cost": float(np.mean(costs)),
                "min_cost": float(np.min(costs)),
                "avg_balance": float(np.mean([ind.fitness.values[1] for ind in population])),
                "max_balance": float(np.max([ind.fitness.values[1] for ind in population])),
                "avg_efficiency": float(np.mean([ind.fitness.values[2] for ind in population])),
                "max_efficiency": float(np.max([ind.fitness.values[2] for ind in population])),
            })

            offspring = tools.selTournamentDCD(population, len(population))
            offspring = [self.toolbox.clone(ind) for ind in offspring]
            offspring = algorithms.varAnd(offspring, self.toolbox, cxpb=self.crossover_prob, mutpb=self.mutation_prob)

            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fits = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
            for fit, ind in zip(fits, invalid_ind):
                ind.fitness.values = fit

            population = self.toolbox.select(population + offspring, k=self.population_size)

        pareto_front = tools.sortNondominated(population, len(population), first_front_only=True)[0]

        t_end = time.time()
        eval_time = t_end - t_eval
        total_time = t_end - t_start
        logger.info(f"优化完成: {total_time:.1f}s (评估 {eval_time:.1f}s), 帕累托前沿 {len(pareto_front)} 个体")

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
