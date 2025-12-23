# agents/explainer_agent.py
"""
SlaveAgent5 - 分析与学习智能体
负责人: 成员B

职责:
- 自然语言解释生成
- 反事实推演
- LLM 接口调用
"""

from typing import Optional
from agents.base_agent import BaseAgent
from interfaces.schemas import ExplanationResponse
from config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL


class ExplainerAgent(BaseAgent):
    """分析与学习智能体"""
    
    agent_name = "SlaveAgent5"
    
    def __init__(self):
        super().__init__()
        self.solutions_cache = {}  # 缓存方案数据用于解释
        
        # TODO [成员B]: 初始化 LLM 客户端
        self.llm_client = None
        if LLM_API_KEY:
            self._init_llm_client()
    
    def _init_llm_client(self):
        """
        初始化 LLM 客户端
        
        TODO [成员B]: 根据配置初始化 DeepSeek 或 OpenAI
        """
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL
            )
            self.logger.info(f"LLM 客户端初始化成功: {LLM_PROVIDER}")
        except Exception as e:
            self.logger.warning(f"LLM 客户端初始化失败: {e}")
    
    def process(self, request: dict) -> dict:
        """通用处理接口"""
        result = self.explain(
            request.get("solution_id"),
            request.get("question")
        )
        return result.model_dump()
    
    def cache_solution(self, solution_id: str, solution_data: dict):
        """缓存方案数据"""
        self.solutions_cache[solution_id] = solution_data
    
    def explain(self, solution_id: str, question: str = None) -> ExplanationResponse:
        """
        生成自然语言解释
        
        TODO [成员B]:
        1. 设计好的 Prompt 模板
        2. 调用 LLM 生成解释
        3. 处理反事实问题
        """
        solution = self.solutions_cache.get(solution_id)
        
        if question:
            # 反事实推演
            return self._counterfactual_reasoning(solution, question)
        else:
            # 普通解释
            return self._generate_explanation(solution)
    
    def _generate_explanation(self, solution: dict) -> ExplanationResponse:
        """
        生成方案解释
        
        TODO [成员B]: 使用 LLM 生成自然语言解释
        """
        if self.llm_client and solution:
            # 调用 LLM
            prompt = self._build_explanation_prompt(solution)
            explanation = self._call_llm(prompt)
            return ExplanationResponse(explanation=explanation)
        
        # Demo 降级: 使用模板
        return ExplanationResponse(
            explanation="本次调度方案综合考虑了成本、均衡性和效率，"
                       "优先选择了距离较近且疲劳值较低的拖轮。"
        )
    
    def _counterfactual_reasoning(self, solution: dict, question: str) -> ExplanationResponse:
        """
        反事实推演
        
        TODO [成员B]: 
        1. 解析用户问题（如"为什么不派亚洲2号"）
        2. 查询该船的状态和违规情况
        3. 生成解释
        """
        if self.llm_client:
            prompt = self._build_counterfactual_prompt(solution, question)
            response = self._call_llm(prompt)
            return ExplanationResponse(
                explanation=response,
                counterfactual=f"针对问题'{question}'的推演结果"
            )
        
        # Demo 降级: 使用预设回答
        return ExplanationResponse(
            explanation=f"关于您的问题'{question}'：经过系统推演分析，"
                       "该拖轮未被选中可能是因为疲劳值较高或存在规则冲突。",
            counterfactual="如果强行派遣，可能触发安全规则限制。"
        )
    
    def _build_explanation_prompt(self, solution: dict) -> str:
        """
        构建解释 Prompt
        
        TODO [成员B]: 设计更好的 Prompt
        """
        return f"""
你是一个港口拖轮调度系统的解释助手。请根据以下调度方案，生成一段简洁的自然语言解释。

方案数据:
{solution}

要求:
1. 用中文回答
2. 解释为什么选择这些拖轮
3. 提及成本和效率因素
4. 如果有连活安排，特别说明节省的成本
"""
    
    def _build_counterfactual_prompt(self, solution: dict, question: str) -> str:
        """构建反事实 Prompt"""
        return f"""
你是一个港口拖轮调度系统的解释助手。用户对调度结果有疑问。

用户问题: {question}

当前方案数据:
{solution}

请解释为什么该拖轮没有被选中，可能的原因包括:
- 疲劳值过高
- 违反业务规则
- 马力不匹配
- 位置不佳（内档）
"""
    
    def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM
        
        TODO [成员B]: 实现真实的 LLM 调用
        """
        if not self.llm_client:
            return "LLM 未配置"
        
        try:
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"LLM 调用失败: {e}")
            return f"生成解释时出错: {e}"
