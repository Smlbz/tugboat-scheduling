"""
Benchmark: CMATSS vs Bare NSGA-II vs Greedy.

Measures response time + solution quality across job sizes [5,10,20,30,50].
Outputs structured JSON.
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from agents.master_agent import MasterAgent
from agents.optimizer_agent import OptimizerAgent
from utils.bare_nsga2 import BareNSGA2Solver
from data.loader import load_jobs
from tests.metrics_quality import compute_quality_metrics


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def run_cmatss(job_ids):
    """Run full CMATSS pipeline, capture Pareto front + gen_history."""
    master = MasterAgent()
    capture = {}

    original_solve = master.optimizer_agent._nsga2_solve
    def capturing_solve(jobs, tugs, chain_pairs):
        from algorithms.nsga2 import NSGA2Optimizer
        optimizer = NSGA2Optimizer(jobs, tugs, chain_pairs, disable_compliance=True)
        try:
            pareto_front = optimizer.optimize()
        except Exception as e:
            master.logger.error(f"CMATSS NSGA-II failed: {e}")
            pareto_front = []
        capture["optimizer"] = optimizer
        capture["pareto_front"] = pareto_front
        return optimizer, pareto_front
    master.optimizer_agent._nsga2_solve = capturing_solve

    t0 = time.time()
    solutions = master.schedule(job_ids)
    elapsed = time.time() - t0
    master.optimizer_agent._nsga2_solve = original_solve

    front = capture.get("pareto_front", [])
    front_data = [[float(ind.fitness.values[0]),
                   float(ind.fitness.values[1]),
                   float(ind.fitness.values[2])] for ind in front]

    opt = capture.get("optimizer")
    gen_history = opt.gen_history if opt and hasattr(opt, "gen_history") else []

    metrics = solutions[0].metrics if solutions else None
    return {
        "algorithm": "cmatss",
        "num_jobs": len(job_ids),
        "elapsed": round(elapsed, 4),
        "num_solutions": len(solutions),
        "overall_score": metrics.overall_score if metrics else None,
        "total_cost": metrics.total_cost if metrics else None,
        "balance_score": metrics.balance_score if metrics else None,
        "efficiency_score": metrics.efficiency_score if metrics else None,
        "pareto_front": front_data,
        "pareto_front_size": len(front_data),
        "gen_history": gen_history,
        "compliance_disabled": True,  # ChromaDB too slow for GA loop
    }


def run_bare_nsga2(job_ids):
    """Run Bare NSGA-II via direct optimizer call."""
    solver = BareNSGA2Solver()
    result = solver.solve(job_ids)

    best = result["solutions"][0]["fitness"] if result["solutions"] else {}
    total_cost = best.get("total_cost", 0)
    balance_score = best.get("balance_score", 0)
    efficiency_score = best.get("efficiency_score", 0)
    # Use same overall_score formula as CMATSS _calc_metrics
    num_jobs = len(job_ids) or 1
    cost_per_job_baseline = 2000
    cost_score = 1.0 - min(total_cost / (num_jobs * cost_per_job_baseline), 1.0)
    overall_score = cost_score * 0.33 + balance_score * 0.33 + efficiency_score * 0.34
    overall_score = max(0.0, min(1.0, overall_score))

    return {
        "algorithm": "bare_nsga2",
        "num_jobs": result["num_jobs"],
        "elapsed": result["elapsed"],
        "num_solutions": len(result["solutions"]),
        "overall_score": round(overall_score, 4),
        "total_cost": total_cost,
        "balance_score": balance_score,
        "efficiency_score": efficiency_score,
        "pareto_front": result["pareto_front"],
        "pareto_front_size": result["pareto_front_size"],
        "gen_history": result["gen_history"],
    }


def run_greedy(job_ids):
    """Run greedy assignment via OptimizerAgent._simple_assign."""
    from data.loader import load_jobs, load_tugs

    all_jobs = load_jobs()
    all_tugs = load_tugs()
    jobs = [j for j in all_jobs if j.id in job_ids]

    agent = OptimizerAgent()
    t0 = time.time()
    assignments = agent._simple_assign(jobs, all_tugs, strategy="overall")
    elapsed = time.time() - t0
    metrics = agent._calc_metrics(assignments)

    return {
        "algorithm": "greedy",
        "num_jobs": len(jobs),
        "elapsed": round(elapsed, 4),
        "num_solutions": 1,
        "overall_score": metrics.overall_score,
        "total_cost": metrics.total_cost,
        "balance_score": metrics.balance_score,
        "efficiency_score": metrics.efficiency_score,
        # Greedy has no Pareto front — treat single solution as front
        "pareto_front": [[metrics.total_cost, metrics.balance_score, metrics.efficiency_score]],
        "pareto_front_size": 1,
        "gen_history": [],
    }


def run_all(job_sizes=(5, 10, 20, 30, 50), repeats=1, output_path="benchmark_comparison_results.json"):
    """Run all 3 algorithms on all job sizes."""
    jobs = load_jobs()
    job_ids = [j.id for j in jobs]
    total = len(job_sizes) * repeats
    count = 0

    all_results = []
    for size in job_sizes:
        if size > len(job_ids):
            print(f"  Skip size {size}: only {len(job_ids)} jobs available")
            continue
        ids = job_ids[:size]

        for rep in range(repeats):
            count += 1
            print(f"\n[{count}/{total}] size={size}, repeat={rep}")

            print("  CMATSS...")
            c = run_cmatss(ids)

            print("  Bare NSGA-II...")
            b = run_bare_nsga2(ids)

            print("  Greedy...")
            g = run_greedy(ids)

            # Quality metrics
            fronts = {}
            for name, result in [("cmatss", c), ("bare_nsga2", b), ("greedy", g)]:
                pts = np.array(result["pareto_front"])
                if len(pts) > 0:
                    fronts[name] = pts

            quality = compute_quality_metrics(fronts) if len(fronts) >= 2 else {}

            all_results.append({
                "size": size,
                "repeat": rep,
                "cmatss": c,
                "bare_nsga2": b,
                "greedy": g,
                "quality_metrics": quality,
            })

            # Partial save for crash recovery
            partial = {"config": {"job_sizes": list(job_sizes), "repeats": repeats},
                       "results": all_results}
            with open(output_path, "w") as f:
                json.dump(partial, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    print(f"\nDone! {len(all_results)} benchmark runs saved to {output_path}")
    return all_results


if __name__ == "__main__":
    print("=" * 50)
    print("3-Algorithm Comparison Benchmark")
    print("=" * 50)
    run_all(job_sizes=(5, 10, 20, 30, 50), repeats=1)
