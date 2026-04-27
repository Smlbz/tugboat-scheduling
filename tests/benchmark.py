"""
CMATSS 性能基准测试
测量调度响应时间、优化指标、NSGA-II收敛速度
"""

import sys
import time
import json
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents import MasterAgent
from data.loader import load_jobs


def benchmark_schedule(master, job_ids, label):
    """测量单次调度响应时间和指标"""
    start = time.time()
    solutions = master.schedule(job_ids)
    elapsed = time.time() - start

    if not solutions:
        print(f"  [{label}] 无解")
        return elapsed, None

    sol = solutions[0]
    print(f"  [{label}] 响应={elapsed:.3f}s 方案数={len(solutions)} "
          f"成本={sol.metrics.total_cost:.0f} "
          f"均衡={sol.metrics.balance_score:.2%} "
          f"效率={sol.metrics.efficiency_score:.2%} "
          f"综合={sol.metrics.overall_score:.2%}")
    return elapsed, sol.metrics


def main():
    print("=" * 60)
    print("CMATSS 性能基准测试")
    print("=" * 60)

    master = MasterAgent()
    all_jobs = load_jobs()
    job_ids = [j.id for j in all_jobs]

    print(f"\n任务总数: {len(job_ids)}")
    results = []

    # 不同规模测试
    sizes = [5, 10, 20, 30, 50]
    for size in sizes:
        if size > len(job_ids):
            break
        ids = job_ids[:size]
        elapsed, metrics = benchmark_schedule(master, ids, f"{size}任务")
        results.append({
            "size": size,
            "elapsed": elapsed,
            "cost": metrics.total_cost if metrics else None,
            "balance": metrics.balance_score if metrics else None,
            "efficiency": metrics.efficiency_score if metrics else None,
            "overall": metrics.overall_score if metrics else None,
        })

    # NSGA-II速度测试（重复5次取平均）
    print(f"\n--- NSGA-II 稳定性测试（5次x10任务） ---")
    times = []
    for i in range(5):
        t, _ = benchmark_schedule(master, job_ids[:10], f"第{i+1}次")
        times.append(t)
    avg = sum(times) / len(times)
    print(f"  平均响应: {avg:.3f}s  (min={min(times):.3f}s max={max(times):.3f}s)")

    # 输出汇总
    print(f"\n--- 汇总 ---")
    print(f"{'任务数':<8} {'响应(s)':<10} {'成本':<10} {'均衡':<10} {'效率':<10} {'综合':<10}")
    print("-" * 58)
    for r in results:
        print(f"{r['size']:<8} {r['elapsed']:<10.3f} "
              f"{r['cost']:<10.0f} {r['balance']:<10.2%} "
              f"{r['efficiency']:<10.2%} {r['overall']:<10.2%}")

    # 保存结果
    out = {"results": results, "avg_time_10jobs": avg}
    with open("benchmark_results.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 benchmark_results.json")


if __name__ == "__main__":
    main()
