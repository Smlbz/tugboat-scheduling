"""
算法自学习轻量版
记录调度方案-执行反馈，支持参数微调
"""

import json
import logging
import os
import threading
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional

logger = logging.getLogger("Learning")

BASE_DIR = Path(__file__).parent.parent
HISTORY_FILE = BASE_DIR / "data" / "history.json"


class LearningEngine:
    """自学习引擎 — 记录调度决策+反馈，优化算法参数"""

    _lock = threading.Lock()

    def __init__(self):
        self.logger = logger
        self.history = self._load_history()

    def _load_history(self) -> dict:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "version": "1.0",
            "schedules": [],
            "insights": {},
            "param_adjustments": [],
        }

    def _save(self):
        """线程安全原子写：写临时文件后重命名"""
        with self._lock:
            tmp = HISTORY_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            tmp.replace(HISTORY_FILE)

    def record_schedule(
        self,
        solution_name: str,
        job_ids: List[str],
        assignments: List[Dict],
        metrics: Dict,
        chain_jobs_count: int = 0,
    ):
        """记录一次调度方案"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "solution_name": solution_name,
            "job_count": len(job_ids) if job_ids else 0,
            "job_ids": job_ids,
            "assignment_count": len(assignments),
            "metrics": metrics,
            "chain_jobs_count": chain_jobs_count,
            "adopted": False,
            "feedback": None,
        }
        self.history["schedules"].append(record)
        if len(self.history["schedules"]) > 1000:
            self.history["schedules"] = self.history["schedules"][-1000:]
        self._save()

    def record_feedback(
        self, schedule_idx: int, adopted: bool, actual_cost: float = None, note: str = ""
    ):
        """记录方案是否被采纳及实际执行结果"""
        if schedule_idx < len(self.history["schedules"]):
            self.history["schedules"][schedule_idx]["adopted"] = adopted
            self.history["schedules"][schedule_idx]["feedback"] = {
                "actual_cost": actual_cost,
                "note": note,
                "feedback_time": datetime.now().isoformat(),
            }
            self._save()

    def analyze(self) -> Dict:
        """分析历史数据，返回洞察"""
        schedules = self.history["schedules"]
        if not schedules:
            return {"status": "no_data", "total_schedules": 0}

        total = len(schedules)
        adopted = sum(1 for s in schedules if s.get("adopted"))
        adoption_rate = adopted / total if total > 0 else 0

        # 平均指标
        costs = [s["metrics"]["total_cost"] for s in schedules if s.get("metrics")]
        balances = [s["metrics"]["balance_score"] for s in schedules if s.get("metrics")]
        efficiencies = [s["metrics"]["efficiency_score"] for s in schedules if s.get("metrics")]

        avg_cost = sum(costs) / len(costs) if costs else 0
        avg_balance = sum(balances) / len(balances) if balances else 0
        avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

        # 趋势分析（最近10条 vs 总体）
        recent = schedules[-10:] if total >= 10 else schedules
        recent_balances = [s["metrics"]["balance_score"] for s in recent if s.get("metrics")]

        improvement = None
        if recent_balances and len(balances) > 10:
            recent_avg = sum(recent_balances) / len(recent_balances)
            overall_avg = sum(balances) / len(balances)
            improvement = recent_avg - overall_avg

        result = {
            "status": "ready",
            "total_schedules": total,
            "adoption_rate": round(adoption_rate, 2),
            "avg_cost": round(avg_cost, 0),
            "avg_balance": round(avg_balance, 2),
            "avg_efficiency": round(avg_efficiency, 2),
            "trend_improvement": round(improvement, 2) if improvement is not None else None,
        }
        self.history["insights"] = result
        self._save()
        return result

    def get_param_adjustments(self) -> Dict:
        """根据历史数据推荐参数调整"""
        analysis = self.analyze()
        adjustments = {}

        if analysis["status"] == "no_data":
            return {"recommendation": "collect_more_data"}

        # 若采纳率低，建议调整权重
        if analysis.get("adoption_rate", 1) < 0.5:
            adjustments["weight_tuning"] = "reduce cost weight, increase balance weight"

        # 若均衡度低，建议增加pop size
        if analysis.get("avg_balance", 1) < 0.4:
            adjustments["population_size"] = 80

        if adjustments:
            self.history["param_adjustments"].append({
                "timestamp": datetime.now().isoformat(),
                "adjustments": adjustments,
                "based_on_analysis": analysis,
            })
            self._save()

        return adjustments or {"recommendation": "current_params_adequate"}

    def apply_adjustments(self) -> Dict:
        """将参数调整建议写入选代配置, 供优化器读取"""
        analysis = self.analyze()
        adjustments = {}

        if analysis["status"] == "no_data":
            return {"status": "skipped", "reason": "no_data"}

        avg_cost = analysis.get("avg_cost", 20000)
        avg_balance = analysis.get("avg_balance", 0.5)
        avg_efficiency = analysis.get("avg_efficiency", 0.5)

        # 采纳率 < 50%, 动态调权重: 某项指标长期偏低则加大权重
        if analysis.get("adoption_rate", 1) < 0.5:
            # 归一化各指标的"不足程度"
            cost_deficit = min(avg_cost / 20000, 1.0) if avg_cost > 0 else 0.5
            balance_deficit = 1.0 - avg_balance
            efficiency_deficit = 1.0 - avg_efficiency
            total_deficit = cost_deficit + balance_deficit + efficiency_deficit
            if total_deficit > 0:
                adjustments["weight_cost"] = round(cost_deficit / total_deficit * 0.33 + 0.25, 2)
                adjustments["weight_balance"] = round(balance_deficit / total_deficit * 0.33 + 0.25, 2)
                adjustments["weight_efficiency"] = round(efficiency_deficit / total_deficit * 0.33 + 0.25, 2)

        # 均衡度 < 0.4, 建议增 pop_size
        if analysis.get("avg_balance", 1) < 0.4:
            adjustments["population_size"] = 80

        # 效率 < 0.5, 建议增 generations
        if analysis.get("avg_efficiency", 1) < 0.5:
            adjustments["generations"] = 50

        if not adjustments:
            return {"status": "adequate", "adjustments": {}}

        # 写入选代配置文件
        adj_path = BASE_DIR / "data" / "learning_adjustments.json"
        with open(adj_path, "w", encoding="utf-8") as f:
            json.dump(adjustments, f, ensure_ascii=False, indent=2)

        self.logger.info(f"自学习参数调整已应用: {adjustments}")
        return {"status": "applied", "adjustments": adjustments}

    def get_stats(self) -> Dict:
        """获取简化的统计摘要"""
        return self.analyze()
