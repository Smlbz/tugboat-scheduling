"""Ablation variants of CMATSS — each disables one component.

Uses reduced NSGA-II (pop=20, gen=10) for practical run times.
"""

from typing import List
from agents.master_agent import MasterAgent
from interfaces.schemas import Tug, Job, ScheduleSolution, TugStatus
from data.loader import load_jobs


def _patch_algorithm_config(pop_size=20, generations=10):
    from config.algorithm_config import AlgorithmConfig
    orig = {
        "population_size": AlgorithmConfig.NSGA2_CONFIG["population_size"],
        "generations": AlgorithmConfig.NSGA2_CONFIG["generations"],
    }
    AlgorithmConfig.update_config("nsga2", population_size=pop_size,
                                  generations=generations)
    return orig


def _restore_algorithm_config(original: dict):
    from config.algorithm_config import AlgorithmConfig
    AlgorithmConfig.update_config("nsga2", **original)


class CMATSS_Variant(MasterAgent):
    """MasterAgent with selective module disabling for ablation study.

    Flags:
        disable_fatigue:    Skip fatigue state injection (all GREEN)
        disable_compliance: Skip compliance checks in optimizer
        disable_chain:      Skip chain-job identification
        disable_nsga2:      Force greedy fallback (skip NSGA-II)
        disable_perception: Skip berth constraints / hidden tasks
    """

    def __init__(self, disable_fatigue=False, disable_compliance=False,
                 disable_chain=False, disable_nsga2=False,
                 disable_perception=False,
                 _fast_ablate=True):  # True=pop20 gen10, False=pop60 gen30
        self._disable_fatigue = disable_fatigue
        self._disable_compliance = disable_compliance
        self._disable_chain = disable_chain
        self._disable_nsga2 = disable_nsga2
        self._disable_perception = disable_perception
        self._fast_ablate = _fast_ablate
        super().__init__()

    def get_all_tugs(self) -> List[Tug]:
        if self._disable_fatigue:
            from data.loader import load_tugs
            tugs = load_tugs()
            for tug in tugs:
                tug.fatigue_value = 0.0
                tug.fatigue_level = "GREEN"
                tug.status = TugStatus.AVAILABLE
            return tugs
        return super().get_all_tugs()

    def identify_chain_jobs(self, jobs: List[Job]) -> list:
        if self._disable_chain:
            return []
        return super().identify_chain_jobs(jobs)

    def schedule(self, job_ids: List[str]) -> List[ScheduleSolution]:
        """Override schedule with selective disabling."""
        saved_config = None
        if self._fast_ablate:
            saved_config = _patch_algorithm_config(pop_size=20, generations=10)
        try:
            return self._schedule_impl(job_ids)
        finally:
            if saved_config:
                _restore_algorithm_config(saved_config)

    def _schedule_impl(self, job_ids: List[str]) -> List[ScheduleSolution]:
        job_count = len(job_ids) if job_ids else 0
        self.logger.info(f"[Ablation] fatigue={not self._disable_fatigue}, "
                         f"chain={not self._disable_chain}, "
                         f"nsga2={not self._disable_nsga2}, "
                         f"perception={not self._disable_perception}")

        all_jobs = load_jobs()
        jobs = [j for j in all_jobs if j.id in job_ids] if job_ids else all_jobs
        jobs = self.rule_engine.enrich_jobs(jobs)
        tugs = self.get_all_tugs()

        chain_pairs = self.identify_chain_jobs(jobs)

        if self._disable_perception:
            hidden_tasks = []
        else:
            hidden_tasks = self.perception_agent.get_hidden_tasks()

        available_tugs = []
        for tug in tugs:
            if tug.status in [TugStatus.LOCKED_BY_FRMS, TugStatus.MAINTENANCE, TugStatus.BUSY]:
                continue
            if tug.berth_position == "INNER":
                continue
            available_tugs.append(tug)

        if self._disable_nsga2:
            solutions = self.optimizer_agent._fallback_solutions(
                jobs, available_tugs, chain_pairs, hidden_tasks
            )
        else:
            # Disable compliance in optimizer based on variant config
            original_solve = self.optimizer_agent._nsga2_solve
            def patched_solve(jobs, tugs, chain_pairs):
                from algorithms.nsga2 import NSGA2Optimizer
                optimizer = NSGA2Optimizer(jobs, tugs, chain_pairs,
                                            disable_compliance=self._disable_compliance)
                try:
                    pareto_front = optimizer.optimize()
                except Exception as e:
                    self.logger.error(f"NSGA-II failed: {e}")
                    pareto_front = []
                return optimizer, pareto_front
            self.optimizer_agent._nsga2_solve = patched_solve
            solutions = self.optimizer_agent.generate_solutions(
                jobs=jobs, available_tugs=available_tugs,
                chain_pairs=chain_pairs, hidden_tasks=hidden_tasks
            )

        for sol in solutions:
            self.explainer_agent.cache_solution(sol.solution_id, sol.model_dump())

        return solutions[:3]
