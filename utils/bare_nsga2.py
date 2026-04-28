"""Bare NSGA-II solver — direct optimizer call, skip multi-agent preprocessing."""

import time
import numpy as np
from algorithms.nsga2 import NSGA2Optimizer
from data.loader import load_jobs, load_tugs


class BareNSGA2Solver:
    """Direct NSGA2Optimizer without MasterAgent preprocessing.

    Skips: fatigue injection, rule enrichment, chain-job identification,
    hidden tasks, berth constraints.
    Retains: ComplianceAgent inside optimizer fitness (can't disable
    without subclassing optimizer).
    """

    def solve(self, job_ids: list[str], num_solutions: int = 3) -> dict:
        all_jobs = load_jobs()
        jobs = [j for j in all_jobs if j.id in job_ids]
        all_tugs = load_tugs()

        optimizer = NSGA2Optimizer(jobs, all_tugs, chain_pairs=[],
                                    disable_compliance=True)

        t0 = time.time()
        pareto_front = optimizer.optimize()
        elapsed = time.time() - t0

        costs = [ind.fitness.values[0] for ind in pareto_front]
        balances = [ind.fitness.values[1] for ind in pareto_front]
        effs = [ind.fitness.values[2] for ind in pareto_front]

        solutions = []
        for ind in pareto_front[:num_solutions]:
            cost, balance, efficiency = ind.fitness.values
            solutions.append({
                "fitness": {
                    "total_cost": cost,
                    "balance_score": balance,
                    "efficiency_score": efficiency,
                },
            })

        return {
            "algorithm": "bare_nsga2",
            "num_jobs": len(jobs),
            "elapsed": round(elapsed, 4),
            "pareto_front": [[float(c), float(b), float(e)]
                             for c, b, e in zip(costs, balances, effs)],
            "pareto_front_size": len(pareto_front),
            "solutions": solutions,
            "gen_history": optimizer.gen_history,
        }
