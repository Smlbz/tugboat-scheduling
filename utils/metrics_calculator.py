import math
import statistics
import logging

logger = logging.getLogger("MetricsCalculator")

class MetricsCalculator:
    OIL_PRICE_PER_NM = 50.0
    MAX_WAIT_TIME = 2.0
    JOB_WAIT_TIME_COEFFICIENTS = {"BERTHING": 0.6, "UNBERTHING": 0.4, "SHIFTING": 0.5, "ESCORT": 0.5}

    @staticmethod
    def calc_cost(assignments, tugs_dict, jobs_dict, perception_agent):
        total_cost = 0.0
        for assignment in assignments:
            tug = tugs_dict.get(assignment.tug_id)
            job = jobs_dict.get(assignment.job_id)
            if not tug or not job:
                logger.warning("成本计算跳过分配: tug=%s job=%s (数据缺失)", assignment.tug_id, assignment.job_id)
                continue
            if tug.berth_id:
                distance = perception_agent.get_berth_distance(tug.berth_id, job.target_berth_id)
            else:
                distance = perception_agent.estimate_distance_from_position(tug.position, job.target_berth_id)
            cost = distance * MetricsCalculator.OIL_PRICE_PER_NM
            total_cost += cost
        return round(total_cost, 2)

    @staticmethod
    def calc_balance(assignments=None, workload_dict=None):
        if workload_dict is not None:
            tug_jobs = workload_dict
        else:
            tug_jobs = {}
            for assignment in assignments or []:
                if assignment.tug_id not in tug_jobs:
                    tug_jobs[assignment.tug_id] = 0
                tug_jobs[assignment.tug_id] += 1
        if not tug_jobs:
            return 1.0
        job_counts = list(tug_jobs.values())
        mean_jobs = statistics.mean(job_counts)
        if mean_jobs == 0:
            return 1.0
        if len(job_counts) > 1:
            variance = statistics.variance(job_counts)
        else:
            variance = 0.0
        # 使用变异系数 (CV) 替代原始公式, 小样本下分辨率更佳
        cv = math.sqrt(variance) / mean_jobs if mean_jobs > 0 else 0
        balance_score = 1.0 - min(cv, 1.0)
        return round(max(0.0, min(1.0, balance_score)), 4)
    
    @staticmethod
    def calc_efficiency(assignments, jobs_dict):
        total_wait_time = 0.0
        for assignment in assignments:
            job = jobs_dict.get(assignment.job_id)
            if not job:
                logger.warning("效率计算跳过分配: job=%s (数据缺失)", assignment.job_id)
                continue
            job_type = job.job_type.value if hasattr(job.job_type, 'value') else job.job_type
            wait_time = MetricsCalculator.JOB_WAIT_TIME_COEFFICIENTS.get(job_type, 0.5)
            total_wait_time += wait_time
        if not assignments:
            return 1.0
        avg_wait_time = total_wait_time / len(assignments)
        efficiency_score = 1.0 - (avg_wait_time / MetricsCalculator.MAX_WAIT_TIME)
        efficiency_score = max(0.0, min(1.0, efficiency_score))
        return round(efficiency_score, 2)