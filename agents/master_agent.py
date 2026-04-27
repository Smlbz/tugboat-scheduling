# agents/master_agent.py
"""
MasterAgent - 调度决策与优化中枢
负责人: 成员A

职责:
- 接收调度请求
- 协调各 SlaveAgent
- 执行连活算法
- 输出最优方案
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from agents.perception_agent import PerceptionAgent
from agents.compliance_agent import ComplianceAgent
from agents.fatigue_agent import FatigueAgent
from agents.optimizer_agent import OptimizerAgent
from agents.explainer_agent import ExplainerAgent
from engine.rule_engine import RuleEngine
from algorithms.learning import LearningEngine
from interfaces.schemas import (
    Tug, Job, ScheduleSolution, ChainJobPair, TugStatus
)
from data.loader import load_tugs, load_jobs
from config import CHAIN_JOB_TIME_THRESHOLD_HOURS, CHAIN_JOB_DISTANCE_THRESHOLD_NM


class MasterAgent(BaseAgent):
    """主控智能体"""
    
    agent_name = "MasterAgent"
    agent_type = "master"
    
    def __init__(self):
        super().__init__()
        # 初始化规则引擎
        self.rule_engine = RuleEngine()
        # 初始化所有 SlaveAgent
        self.perception_agent = PerceptionAgent()   # Agent1
        self.compliance_agent = ComplianceAgent()   # Agent2
        self.fatigue_agent = FatigueAgent()         # Agent3
        self.optimizer_agent = OptimizerAgent()     # Agent4
        self.explainer_agent = ExplainerAgent()     # Agent5
        self.learning_engine = LearningEngine()      # 自学习引擎

        self.logger.info("MasterAgent 初始化完成 (含 Agent5 ExplainerAgent)")
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        action = request.get("action")
        if action == "schedule":
            solutions = self.schedule(request.get("job_ids", []))
            return {"solutions": [s.model_dump() for s in solutions]}
        elif action == "get_tugs":
            tugs = self.get_all_tugs()
            return {"tugs": [t.model_dump() for t in tugs]}
        return {"error": "Unknown action"}
    
    def get_all_tugs(self) -> List[Tug]:
        """获取所有拖轮及实时状态"""
        tugs = load_tugs()
        for tug in tugs:
            fatigue = self.fatigue_agent.get_fatigue(tug.id)
            tug.fatigue_value = fatigue.fatigue_value
            tug.fatigue_level = fatigue.fatigue_level
            if not fatigue.is_available:
                tug.status = TugStatus.LOCKED_BY_FRMS
        return tugs
    
    def schedule(self, job_ids: List[str]) -> List[ScheduleSolution]:
        """
        核心调度方法
        
        TODO [成员A]: 完善调度流程
        """
        job_count = len(job_ids) if job_ids else 0
        self.logger.info(f"开始调度，任务数: {job_count}")

        # Step 1: 获取数据
        all_jobs = load_jobs()
        jobs = [j for j in all_jobs if j.id in job_ids] if job_ids else all_jobs
        # 用规则引擎填充CSV需求参数
        jobs = self.rule_engine.enrich_jobs(jobs)
        tugs = self.get_all_tugs()
        
        # Step 2: 识别连活
        chain_pairs = self.identify_chain_jobs(jobs)
        self.logger.info(f"识别到 {len(chain_pairs)} 对连活任务")
        
        # Step 3: 获取约束
        berth_constraints = self.perception_agent.get_berth_constraints()
        hidden_tasks = self.perception_agent.get_hidden_tasks()
        
        # Step 4: 过滤不可用拖轮
        available_tugs = []
        for tug in tugs:
            # 检查状态
            if tug.status in [TugStatus.LOCKED_BY_FRMS, TugStatus.MAINTENANCE, TugStatus.BUSY]:
                continue
            
            # 检查是否内档
            if tug.berth_position == "INNER":
                continue
            
            # 检查合规
            is_compliant = False
            for job in jobs:
                result = self.compliance_agent.check_compliance(tug.id, job.id)
                if result.is_compliant:
                    is_compliant = True
                    break
            
            if is_compliant:
                available_tugs.append(tug)
        
        self.logger.info(f"可用拖轮: {len(available_tugs)}/{len(tugs)}")
        
        # 自学习调参（失败不阻塞调度）
        try:
            self.learning_engine.apply_adjustments()
        except Exception as e:
            self.logger.error("自学习调参失败: %s", e)

        # Step 5: 生成方案
        solutions = self.optimizer_agent.generate_solutions(
            jobs=jobs,
            available_tugs=available_tugs,
            chain_pairs=chain_pairs,
            hidden_tasks=hidden_tasks
        )
        
        # 缓存方案供解释使用
        for sol in solutions:
            self.explainer_agent.cache_solution(sol.solution_id, sol.model_dump())

        # 记录调度历史（自学习用，失败不阻塞调度）
        if solutions:
            best = solutions[0]
            try:
                self.learning_engine.record_schedule(
                    solution_name=best.name,
                    job_ids=job_ids,
                    assignments=[{"tug_id": a.tug_id, "job_id": a.job_id} for a in best.assignments],
                    metrics={
                        "total_cost": best.metrics.total_cost,
                        "balance_score": best.metrics.balance_score,
                        "efficiency_score": best.metrics.efficiency_score,
                        "overall_score": best.metrics.overall_score,
                    },
                    chain_jobs_count=len(chain_pairs),
                )
            except Exception as e:
                self.logger.error("记录调度历史失败: %s", e)

        return solutions[:3]
    
    def identify_chain_jobs(self, jobs: List[Job]) -> List[ChainJobPair]:
        """
        连活算法
        
        识别时间间隔短、距离近的任务对，以实现连活调度
        """
        chain_pairs = []
        sorted_jobs = sorted(jobs, key=lambda j: j.start_time)
        
        for i, job1 in enumerate(sorted_jobs):
            for job2 in sorted_jobs[i+1:]:
                # 计算时间间隔（小时）
                interval = (job2.start_time - job1.end_time).total_seconds() / 3600
                
                # 筛选时间间隔
                if interval < 0 or interval > CHAIN_JOB_TIME_THRESHOLD_HOURS:
                    continue
                
                # 计算任务间距离
                distance = self.perception_agent.get_berth_distance(
                    job1.target_berth_id,
                    job2.target_berth_id
                )
                
                # 筛选距离
                if distance <= CHAIN_JOB_DISTANCE_THRESHOLD_NM:
                    # 计算节省成本
                    # 假设油价为50元/海里，连活节省20%成本
                    saving = distance * 50 * 0.2
                    chain_pairs.append(ChainJobPair(
                        job1_id=job1.id,
                        job2_id=job2.id,
                        interval_hours=round(interval, 2),
                        distance_nm=round(distance, 2),
                        cost_saving=round(saving, 2)
                    ))
        
        # 按节省成本排序，优先选择节省最多的连活
        chain_pairs.sort(key=lambda cp: cp.cost_saving, reverse=True)
        
        return chain_pairs

    def check_compliance(self, tug_id: str, job_id: str):
        """检查拖轮执行任务的合规性"""
        return self.compliance_agent.check_compliance(tug_id, job_id)
