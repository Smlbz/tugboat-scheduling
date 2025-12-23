# agents/compliance_agent.py
"""
SlaveAgent2 - 规则与知识守护智能体
负责人: 成员B

职责:
- 向量数据库搭建（规则检索）
- 合规检查器
- 违规原因生成
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from interfaces.schemas import ComplianceCheckResponse, Rule
from data.loader import load_rules, get_tug_by_id, get_job_by_id


class ComplianceAgent(BaseAgent):
    """规则与知识守护智能体"""
    
    agent_name = "SlaveAgent2"
    
    def __init__(self):
        super().__init__()
        self.rules = load_rules()
        self.logger.info(f"加载了 {len(self.rules)} 条业务规则")
        
        # TODO [成员B]: 初始化向量数据库
        # self.vector_db = ChromaDB(...)
    
    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        result = self.check_compliance(
            request.get("tug_id"),
            request.get("job_id")
        )
        return result.model_dump()
    
    def check_compliance(self, tug_id: str, job_id: str) -> ComplianceCheckResponse:
        """
        检查拖轮执行任务是否合规
        
        TODO [成员B]: 实现完整的规则检查逻辑
        1. 从向量数据库检索相关规则
        2. 逐条检查是否违反
        3. 生成违规原因
        """
        violations = []
        tug = get_tug_by_id(tug_id)
        job = get_job_by_id(job_id)
        
        if not tug or not job:
            return ComplianceCheckResponse(
                is_compliant=False,
                violation_rules=["SYSTEM"],
                violation_reason="拖轮或任务不存在"
            )
        
        # 规则检查示例 (TODO: 成员B扩展)
        
        # R002: 老旧拖轮高危限制
        if tug.ship_age > 20 and job.is_high_risk:
            violations.append("R002")
        
        # R003: 马力匹配
        if tug.horsepower < job.required_horsepower / job.required_tug_count:
            violations.append("R003")
        
        # R001: 名称混淆检查
        # TODO [成员B]: 实现名称相似度检查
        
        if violations:
            reason = self._generate_violation_reason(violations, tug, job)
            return ComplianceCheckResponse(
                is_compliant=False,
                violation_rules=violations,
                violation_reason=reason
            )
        
        return ComplianceCheckResponse(is_compliant=True)
    
    def _generate_violation_reason(self, violations: List[str], tug, job) -> str:
        """
        生成人类可读的违规原因
        
        TODO [成员B]: 使用规则描述生成更详细的原因
        """
        reasons = []
        for v in violations:
            if v == "R002":
                reasons.append(f"拖轮{tug.name}船龄{tug.ship_age}年，不得执行高危作业")
            elif v == "R003":
                reasons.append(f"拖轮马力{tug.horsepower}不满足任务需求")
            else:
                reasons.append(f"违反规则{v}")
        return "；".join(reasons)
    
    def search_rules(self, query: str) -> List[Rule]:
        """
        从向量数据库检索相关规则
        
        TODO [成员B]: 实现向量检索
        """
        # Demo版: 简单关键词匹配
        results = []
        for rule in self.rules:
            if any(kw in query for kw in rule.keywords):
                results.append(rule)
        return results
