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
        '''
        from config import MODE
        '''
        
        chain_pairs = chain_pairs or []
        hidden_tasks = hidden_tasks or []
        '''
        # Demo模式: 使用固定最优解
        if MODE == "demo":
            fixed_solution = self._get_fixed_best_plan()
            return [fixed_solution]
        '''
        
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
        
        # 打印方案详细信息
        for i, solution in enumerate(solutions, 1):
            self.logger.info(f"\n=== 方案 {i}: {solution.name} ===")
            self.logger.info(f"方案ID: {solution.solution_id}")
            self.logger.info(f"总燃油成本: ¥{solution.metrics.total_cost}")
            self.logger.info(f"均衡度评分: {solution.metrics.balance_score}")
            self.logger.info(f"效率评分: {solution.metrics.efficiency_score}")
            self.logger.info(f"综合评分: {solution.metrics.overall_score}")
            
            self.logger.info("\n分配详情:")
            for assignment in solution.assignments:
                self.logger.info(f"  - 拖轮: {assignment.tug_name} ({assignment.tug_id}) → 任务: {assignment.job_id} ({assignment.job_type})")
            
            if solution.chain_jobs:
                self.logger.info("\n连活信息:")
                for chain in solution.chain_jobs:
                    self.logger.info(f"  - 任务对: {chain.job1_id} → {chain.job2_id}")
                    self.logger.info(f"    时间间隔: {chain.interval_hours}小时, 距离: {chain.distance_nm}海里, 节省成本: ¥{chain.cost_saving}")
            
            self.logger.info("=" * 50)
        
        return solutions
    
    def _generate_cost_optimized(
        self, jobs: List[Job], tugs: List[Tug], chain_pairs: List[ChainJobPair]
    ) -> ScheduleSolution:
        """
        生成省油方案
        
        基于距离的优化
        """
        assignments = self._simple_assign(jobs, tugs, weight_cost=0.8, chain_pairs=chain_pairs)
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
        
        基于工作量均衡的优化
        """
        assignments = self._simple_assign(jobs, tugs, weight_balance=0.8, chain_pairs=chain_pairs)
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
        
        综合评分优化
        """
        assignments = self._simple_assign(jobs, tugs, chain_pairs=chain_pairs)
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
        weight_cost: float = 0.33, weight_balance: float = 0.33,
        chain_pairs: List = None
    ) -> List[Assignment]:
        """
        优化的分配算法
        
        考虑连活优先级
        根据权重参数调整分配策略
        """
        from data.loader import load_jobs
        from agents.perception_agent import PerceptionAgent
        
        chain_pairs = chain_pairs or []
        assignments = []
        available = list(tugs)
        assigned_jobs = set()
        perception_agent = PerceptionAgent()
        
        # 初始化拖轮工作量统计
        tug_workload = {tug.id: 0 for tug in tugs}
        
        # 1. 优先处理连活任务
        for chain_pair in chain_pairs:
            job1_id = chain_pair.job1_id
            job2_id = chain_pair.job2_id
            
            # 检查两个任务是否都在待分配列表中
            job1 = next((j for j in jobs if j.id == job1_id), None)
            job2 = next((j for j in jobs if j.id == job2_id), None)
            
            if not job1 or not job2:
                continue
            
            if job1_id in assigned_jobs or job2_id in assigned_jobs:
                continue
            
            # 为第一个任务分配拖轮
            if available:
                # 根据权重选择拖轮
                if weight_cost > 0.5:  # 省油方案，优先考虑距离
                    def cost_key(tug):
                        if tug.berth_id:
                            distance = perception_agent.get_berth_distance(tug.berth_id, job1.target_berth_id)
                        else:
                            distance = 2.0  # 默认距离
                        horsepower_diff = abs(tug.horsepower - job1.required_horsepower / job1.required_tug_count)
                        # 距离权重更高
                        return distance * 0.8 + horsepower_diff * 0.2
                    
                    best_tug = min(available, key=cost_key)
                
                elif weight_balance > 0.5:  # 均衡方案，优先考虑工作量
                    def balance_key(tug):
                        horsepower_diff = abs(tug.horsepower - job1.required_horsepower / job1.required_tug_count)
                        # 工作量权重更高
                        return horsepower_diff * 0.3 + tug_workload[tug.id] * 0.7
                    
                    best_tug = min(available, key=balance_key)
                
                else:  # 综合方案，默认考虑马力匹配
                    def overall_key(tug):
                        if tug.berth_id:
                            distance = perception_agent.get_berth_distance(tug.berth_id, job1.target_berth_id)
                        else:
                            distance = 2.0  # 默认距离
                        horsepower_diff = abs(tug.horsepower - job1.required_horsepower / job1.required_tug_count)
                        workload = tug_workload[tug.id]
                        # 平衡考虑所有因素
                        return distance * 0.3 + horsepower_diff * 0.5 + workload * 0.2
                    
                    best_tug = min(available, key=overall_key)
                
                assignments.append(Assignment(
                    tug_id=best_tug.id,
                    tug_name=best_tug.name,
                    job_id=job1.id,
                    job_type=job1.job_type,
                    score=0.95  # 连活任务评分更高
                ))
                
                assigned_jobs.add(job1.id)
                tug_workload[best_tug.id] += 1
                
                # 为第二个任务分配同一个拖轮（连活）
                assignments.append(Assignment(
                    tug_id=best_tug.id,
                    tug_name=best_tug.name,
                    job_id=job2.id,
                    job_type=job2.job_type,
                    score=0.92  # 连活任务评分较高
                ))
                
                assigned_jobs.add(job2.id)
                tug_workload[best_tug.id] += 1
                available.remove(best_tug)
        
        # 2. 处理剩余任务
        for job in jobs:
            if job.id in assigned_jobs:
                continue
            
            if not available:
                break
            
            # 根据权重选择拖轮
            if weight_cost > 0.5:  # 省油方案，优先考虑距离
                # 计算每个拖轮到任务目标泊位的距离
                tug_distances = []
                for tug in available:
                    if tug.berth_id:
                        distance = perception_agent.get_berth_distance(tug.berth_id, job.target_berth_id)
                    else:
                        distance = 2.0  # 默认距离
                    tug_distances.append((distance, tug))
                
                # 按距离排序，选择最近的拖轮
                tug_distances.sort(key=lambda x: x[0])
                best_tug = tug_distances[0][1]
            
            elif weight_balance > 0.5:  # 均衡方案，优先考虑工作量
                # 按工作量排序，选择工作量最少的拖轮
                sorted_tugs = sorted(available, key=lambda t: tug_workload[t.id])
                best_tug = sorted_tugs[0]
            
            else:  # 综合方案，优先考虑马力匹配
                # 计算每个拖轮的马力匹配度
                best_tug = min(
                    available,
                    key=lambda t: abs(t.horsepower - job.required_horsepower / job.required_tug_count)
                )
            
            assignments.append(Assignment(
                tug_id=best_tug.id,
                tug_name=best_tug.name,
                job_id=job.id,
                job_type=job.job_type,
                score=0.85  # 普通任务评分
            ))
            
            assigned_jobs.add(job.id)
            tug_workload[best_tug.id] += 1
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
        
        使用真实计算值
        """
        # 计算各项指标
        total_cost = self.calc_cost(assignments)
        balance_score = self.calc_balance(assignments)
        efficiency_score = self.calc_efficiency(assignments)
        
        # 计算综合评分
        overall_score = (
            total_cost * (-weight_cost) / 10000 +  # 成本越低评分越高
            balance_score * weight_balance +
            efficiency_score * weight_efficiency
        )
        
        # 确保综合评分在 0-1 之间
        overall_score = max(0.0, min(1.0, overall_score))
        
        return SolutionMetrics(
            total_cost=total_cost,
            balance_score=balance_score,
            efficiency_score=efficiency_score,
            overall_score=round(overall_score, 2)
        )
    
    def calc_cost(self, assignments: List[Assignment]) -> float:
        """
        计算燃油成本
        
        公式: 燃油成本 = 距离 × 油价
        """
        from data.loader import load_tugs, load_jobs
        from agents.perception_agent import PerceptionAgent
        
        tugs = {t.id: t for t in load_tugs()}
        jobs = {j.id: j for j in load_jobs()}
        perception_agent = PerceptionAgent()
        
        total_cost = 0.0
        OIL_PRICE_PER_NM = 50.0  # 油价：50元/海里
        
        for assignment in assignments:
            tug = tugs.get(assignment.tug_id)
            job = jobs.get(assignment.job_id)
            
            if not tug or not job:
                continue
            
            # 计算拖轮到任务目标泊位的距离
            if tug.berth_id:
                distance = perception_agent.get_berth_distance(tug.berth_id, job.target_berth_id)
            else:
                # 如果拖轮不在泊位，使用估计距离
                distance = 2.0  # 默认2海里
            
            # 计算燃油成本
            cost = distance * OIL_PRICE_PER_NM
            total_cost += cost
        
        return round(total_cost, 2)
    
    def calc_balance(self, assignments: List[Assignment]) -> float:
        """
        计算作业均衡度
        
        公式: 均衡度 = 1 - 方差/均值
        """
        import statistics
        
        # 统计每个拖轮的作业数量
        tug_jobs = {}
        for assignment in assignments:
            if assignment.tug_id not in tug_jobs:
                tug_jobs[assignment.tug_id] = 0
            tug_jobs[assignment.tug_id] += 1
        
        if not tug_jobs:
            return 1.0  # 没有作业时均衡度为1
        
        # 计算作业数量列表
        job_counts = list(tug_jobs.values())
        
        # 计算均值
        mean_jobs = statistics.mean(job_counts)
        
        if mean_jobs == 0:
            return 1.0
        
        # 计算方差
        if len(job_counts) > 1:
            variance = statistics.variance(job_counts)
        else:
            variance = 0.0
        
        # 计算均衡度
        balance_score = 1 - (variance / mean_jobs)
        
        # 确保结果在 0-1 之间
        balance_score = max(0.0, min(1.0, balance_score))
        
        return round(balance_score, 2)
    
    def calc_efficiency(self, assignments: List[Assignment]) -> float:
        """
        计算效率评分
        
        基于等待时间计算效率
        """
        from data.loader import load_jobs
        
        jobs = {j.id: j for j in load_jobs()}
        
        total_wait_time = 0.0
        max_wait_time = 2.0  # 最大等待时间（小时），超过这个时间效率会降低
        
        for assignment in assignments:
            job = jobs.get(assignment.job_id)
            if not job:
                continue
            
            # 计算等待时间（假设拖轮需要提前到达）
            # 这里使用简化的计算，实际应该考虑拖轮的位置和速度
            estimated_wait_time = 0.5  # 默认等待时间30分钟
            
            # 可以根据任务类型调整等待时间
            if job.job_type == "BERTHING":
                estimated_wait_time = 0.6  # 靠泊任务等待时间稍长
            elif job.job_type == "UNBERTHING":
                estimated_wait_time = 0.4  # 离泊任务等待时间稍短
            
            total_wait_time += estimated_wait_time
        
        if not assignments:
            return 1.0  # 没有作业时效率为1
        
        # 计算平均等待时间
        avg_wait_time = total_wait_time / len(assignments)
        
        # 计算效率评分（等待时间越短，效率越高）
        efficiency_score = 1.0 - (avg_wait_time / max_wait_time)
        
        # 确保结果在 0-1 之间
        efficiency_score = max(0.0, min(1.0, efficiency_score))
        
        return round(efficiency_score, 2)
    
    def _get_fixed_best_plan(self) -> ScheduleSolution:
        """
        为演示准备固定最优解
        
        Demo模式下使用的固定方案
        """
        from interfaces.schemas import Assignment, SolutionMetrics, ChainJobPair
        import uuid
        
        # 固定的分配方案
        fixed_assignments = [
            Assignment(
                tug_id="TUG001",
                tug_name="青港拖1",
                job_id="JOB001",
                job_type="BERTHING",
                score=0.95
            ),
            Assignment(
                tug_id="TUG002",
                tug_name="青港拖2",
                job_id="JOB002",
                job_type="UNBERTHING",
                score=0.92
            ),
            Assignment(
                tug_id="TUG003",
                tug_name="青港拖3",
                job_id="JOB003",
                job_type="SHIFTING",
                score=0.88
            )
        ]
        
        # 固定的连活对
        fixed_chain_pairs = [
            ChainJobPair(
                job1_id="JOB001",
                job2_id="JOB002",
                interval_hours=1.5,
                distance_nm=3.2,
                cost_saving=32.0
            )
        ]
        
        # 固定的评价指标
        fixed_metrics = SolutionMetrics(
            total_cost=8500.0,
            balance_score=0.9,
            efficiency_score=0.85,
            overall_score=0.88
        )
        
        # 创建固定方案
        fixed_solution = ScheduleSolution(
            solution_id=f"SOL-DEMO-{uuid.uuid4().hex[:4]}",
            name="演示最优方案",
            assignments=fixed_assignments,
            metrics=fixed_metrics,
            chain_jobs=fixed_chain_pairs,
            hidden_tasks=[]
        )
        
        return fixed_solution
