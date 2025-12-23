# agents/optimizer_agent.py
"""
SlaveAgent4 - 运筹规划智能体
负责人: 成员A

职责:
- 多目标评分函数
- 方案生成与排序
- 连活优化处理
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from interfaces.schemas import (
    Tug, Job, ScheduleSolution, SolutionMetrics,
    Assignment, ChainJobPair, JobType
)
import uuid


class OptimizerAgent(BaseAgent):
    """运筹规划智能体"""
    
    agent_name = "SlaveAgent4"
    
    def __init__(self):
        super().__init__()
        self.logger.info("OptimizerAgent 初始化完成")
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        # 需要从请求中解析数据
        return {"error": "Use generate_solutions directly"}
    
    def generate_solutions(
        self,
        jobs: List[Job],
        available_tugs: List[Tug],
        chain_pairs: List[ChainJobPair] = None,
        hidden_tasks: List[str] = None
    ) -> List[ScheduleSolution]:
        """
        生成 Top-3 调度方案
        
        TODO [成员A]:
        1. 实现多目标优化算法
        2. 考虑连活优先
        3. 生成不同侧重的方案
        """
        chain_pairs = chain_pairs or []
        hidden_tasks = hidden_tasks or []
        
        solutions = []
        
        # 方案1: 省油方案 (距离最短)
        sol1 = self._generate_cost_optimized(jobs, available_tugs, chain_pairs)
        sol1.name = "省油方案"
        solutions.append(sol1)
        
        # 方案2: 均衡方案 (工作量均衡)
        sol2 = self._generate_balanced(jobs, available_tugs, chain_pairs)
        sol2.name = "均衡方案"
        solutions.append(sol2)
        
        # 方案3: 综合最优
        sol3 = self._generate_overall_best(jobs, available_tugs, chain_pairs)
        sol3.name = "综合最优"
        solutions.append(sol3)
        
        return solutions
    
    def _generate_cost_optimized(
        self, jobs: List[Job], tugs: List[Tug], chain_pairs: List[ChainJobPair]
    ) -> ScheduleSolution:
        """
        生成省油方案
        
        TODO [成员A]: 实现基于距离的优化
        """
        assignments = self._simple_assign(jobs, tugs, weight_cost=0.8)
        metrics = self._calc_metrics(assignments, weight_cost=0.8)
        
        return ScheduleSolution(
            solution_id=f"SOL-{uuid.uuid4().hex[:8]}",
            name="省油方案",
            assignments=assignments,
            metrics=metrics,
            chain_jobs=chain_pairs
        )
    
    def _generate_balanced(
        self, jobs: List[Job], tugs: List[Tug], chain_pairs: List[ChainJobPair]
    ) -> ScheduleSolution:
        """
        生成均衡方案
        
        TODO [成员A]: 实现基于工作量均衡的优化
        """
        assignments = self._simple_assign(jobs, tugs, weight_balance=0.8)
        metrics = self._calc_metrics(assignments, weight_balance=0.8)
        
        return ScheduleSolution(
            solution_id=f"SOL-{uuid.uuid4().hex[:8]}",
            name="均衡方案",
            assignments=assignments,
            metrics=metrics,
            chain_jobs=chain_pairs
        )
    
    def _generate_overall_best(
        self, jobs: List[Job], tugs: List[Tug], chain_pairs: List[ChainJobPair]
    ) -> ScheduleSolution:
        """
        生成综合最优方案
        
        TODO [成员A]: 实现综合评分优化
        """
        assignments = self._simple_assign(jobs, tugs)
        metrics = self._calc_metrics(assignments)
        
        return ScheduleSolution(
            solution_id=f"SOL-{uuid.uuid4().hex[:8]}",
            name="综合最优",
            assignments=assignments,
            metrics=metrics,
            chain_jobs=chain_pairs
        )
    
    def _simple_assign(
        self, jobs: List[Job], tugs: List[Tug],
        weight_cost: float = 0.33, weight_balance: float = 0.33
    ) -> List[Assignment]:
        """
        简单分配算法（Demo版）
        
        TODO [成员A]: 实现更复杂的分配算法
        """
        assignments = []
        available = list(tugs)
        
        for job in jobs:
            if not available:
                break
            
            # 简单策略: 选择马力最匹配的
            best_tug = min(
                available,
                key=lambda t: abs(t.horsepower - job.required_horsepower / job.required_tug_count)
            )
            
            assignments.append(Assignment(
                tug_id=best_tug.id,
                tug_name=best_tug.name,
                job_id=job.id,
                job_type=job.job_type,
                score=0.85  # TODO: 计算真实评分
            ))
            
            available.remove(best_tug)
        
        return assignments
    
    def _calc_metrics(
        self, assignments: List[Assignment],
        weight_cost: float = 0.33,
        weight_balance: float = 0.33,
        weight_efficiency: float = 0.34
    ) -> SolutionMetrics:
        """
        计算方案评价指标
        
        TODO [成员A]:
        - calc_cost(): 计算燃油成本
        - calc_balance(): 计算作业均衡度方差
        - calc_efficiency(): 计算等待时间
        """
        # Demo版: 使用模拟值
        return SolutionMetrics(
            total_cost=12500.0 * (1 - weight_cost * 0.2),
            balance_score=0.7 + weight_balance * 0.2,
            efficiency_score=0.8,
            overall_score=0.75 + weight_cost * 0.1 + weight_balance * 0.1
        )
    
    def calc_cost(self, assignments: List[Assignment]) -> float:
        """
        计算燃油成本
        
        TODO [成员A]: 公式 = 距离 × 油价
        """
        return 0.0
    
    def calc_balance(self, assignments: List[Assignment]) -> float:
        """
        计算作业均衡度
        
        TODO [成员A]: 使用方差评估
        """
        return 0.0
    
    def calc_efficiency(self, assignments: List[Assignment]) -> float:
        """
        计算效率评分
        
        TODO [成员A]: 基于等待时间
        """
        return 0.0
