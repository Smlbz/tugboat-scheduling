"""
Ablation benchmark — runs 6 CMATSS variants, measures overall_score.
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from data.loader import load_jobs
from utils.cmatss_variants import CMATSS_Variant


def run_ablation(job_ids, repeats=2, output_path="benchmark_ablation_results.json"):
    """Run ablation study: 6 variants x N repeats."""
    variant_configs = [
        ("full", {}),
        ("-fatigue", {"disable_fatigue": True}),
        ("-compliance", {"disable_compliance": True}),
        ("-chain", {"disable_chain": True}),
        ("-NSGA2", {"disable_nsga2": True}),
        ("-perception", {"disable_perception": True}),
    ]

    total = len(variant_configs) * repeats
    count = 0
    results = []

    for name, flags in variant_configs:
        variant_overall = []
        variant_metrics = []

        for rep in range(repeats):
            count += 1
            print(f"[{count}/{total}] variant={name}, repeat={rep}")

            agent = CMATSS_Variant(**flags)
            t0 = time.time()
            solutions = agent.schedule(job_ids)
            elapsed = time.time() - t0

            metrics = solutions[0].metrics if solutions else None
            score = metrics.overall_score if metrics else 0
            variant_overall.append(score)
            variant_metrics.append({
                "elapsed": round(elapsed, 4),
                "total_cost": metrics.total_cost if metrics else None,
                "balance_score": metrics.balance_score if metrics else None,
                "efficiency_score": metrics.efficiency_score if metrics else None,
                "overall_score": score,
            })

        results.append({
            "variant": name,
            "mean_overall": round(float(np.mean(variant_overall)), 4),
            "std_overall": round(float(np.std(variant_overall)), 4),
            "details": variant_metrics,
        })

    output = {
        "config": {"job_size": len(job_ids), "repeats": repeats},
        "results": results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n--- Ablation Results ---")
    for r in results:
        print(f"  {r['variant']:15s} overall={r['mean_overall']:.4f} ±{r['std_overall']:.4f}")
    print(f"\nSaved to {output_path}")
    return results


if __name__ == "__main__":
    print("=" * 50)
    print("Ablation Study Benchmark")
    print("=" * 50)
    jobs = load_jobs()
    ids = [j.id for j in jobs[:15]]
    print(f"Jobs: {len(ids)} (IDs: {ids[:3]}...{ids[-3:]})")
    run_ablation(ids, repeats=2)
