"""
ExplainerAgent (Agent5) — 调度解释与反事实推演智能体
"""

from typing import Dict, List, Optional
from agents.base_agent import BaseAgent
from utils.llm_client import LLMClient
from interfaces.schemas import ExplanationResponse


class ExplainerAgent(BaseAgent):
    """分析与解释智能体: 方案解释、反事实推演"""

    agent_name = "ExplainerAgent"
    agent_type = "slave"

    def __init__(self):
        super().__init__()
        self.llm = LLMClient()
        self.solution_cache: Dict[str, dict] = {}
        self._max_cache = 10

    def process(self, request: Dict) -> Dict:
        action = request.get("action", "")
        if action == "explain":
            sol_id = request.get("solution_id", "")
            resp = self.explain_solution(sol_id)
            return {"explanation": resp.explanation}
        elif action == "counterfactual":
            sol_id = request.get("solution_id", "")
            change = request.get("change")
            resp = self.counterfactual_reasoning(sol_id, change)
            return {"explanation": resp.explanation, "counterfactual": resp.counterfactual}
        elif action == "health":
            return self.health_check()
        return {"error": f"Unknown action: {action}"}

    def cache_solution(self, solution_id: str, solution_data: dict):
        """缓存方案供后续解释"""
        self.solution_cache[solution_id] = solution_data
        # FIFO 淘汰
        if len(self.solution_cache) > self._max_cache:
            oldest = next(iter(self.solution_cache))
            del self.solution_cache[oldest]
        self.logger.info(f"缓存方案 {solution_id}, 当前缓存 {len(self.solution_cache)} 个")

    def explain_solution(self, solution_id: str) -> ExplanationResponse:
        """生成自然语言方案解释"""
        sol = self.solution_cache.get(solution_id)
        if not sol:
            return ExplanationResponse(
                explanation=f"未找到方案 {solution_id} 的缓存数据",
            )

        prompt = self._build_explain_prompt(sol)
        llm_result = self.llm.chat([{"role": "user", "content": prompt}])

        if llm_result:
            text = llm_result
        else:
            self.logger.warning(f"LLM 解释调用失败，使用模板降级 (solution_id={solution_id})")
            llm_status = "可用" if self.llm.client is not None else "未初始化"
            self.logger.info(f"LLM 客户端状态: {llm_status}, API_KEY: {'已设置' if self.llm._api_key else '未设置'}")
            text = self._template_explain(sol)

        return ExplanationResponse(explanation=text)

    def counterfactual_reasoning(self, solution_id: str,
                                 change: Optional[dict] = None) -> ExplanationResponse:
        """反事实推演: 如果替换拖轮会怎样"""
        sol = self.solution_cache.get(solution_id)
        if not sol:
            return ExplanationResponse(
                explanation=f"未找到方案 {solution_id} 的缓存数据",
            )

        prompt = self._build_counterfactual_prompt(sol, change)
        llm_result = self.llm.chat([{"role": "user", "content": prompt}])

        if llm_result:
            text = llm_result
        else:
            self.logger.warning(f"LLM 反事实推演调用失败，使用模板降级 (solution_id={solution_id})")
            text = self._template_counterfactual(sol, change)

        return ExplanationResponse(
            explanation=f"基于方案 {sol.get('name', solution_id)} 的反事实推演",
            counterfactual=text,
        )

    def _build_explain_prompt(self, sol: dict) -> str:
        """构建解释 prompt"""
        metrics = sol.get("metrics", {})
        assigns = sol.get("assignments", [])
        chain = sol.get("chain_jobs", [])

        assign_text = "; ".join(
            [f"{a.get('tug_id','?')}→{a.get('job_id','?')}" for a in assigns[:5]]
        )
        chain_text = f"识别到 {len(chain)} 对连活任务" if chain else "无连活任务"

        return (
            f"请用中文简要解释以下港口拖轮调度方案（150字以内）:\n"
            f"方案名称: {sol.get('name', '未知')}\n"
            f"总成本: {metrics.get('total_cost', '?')} 元\n"
            f"均衡度: {metrics.get('balance_score', '?'):.2f}\n"
            f"效率: {metrics.get('efficiency_score', '?'):.2f}\n"
            f"综合评分: {metrics.get('overall_score', '?'):.2f}\n"
            f"分配: {assign_text}\n"
            f"连活: {chain_text}\n"
            f"请说明该方案的优缺点。"
        )

    def _build_counterfactual_prompt(self, sol: dict, change: Optional[dict]) -> str:
        """构建反事实推演 prompt"""
        metrics = sol.get("metrics", {})
        return (
            f"假设将调度方案 '{sol.get('name', '未知')}' 中的拖轮分配进行调整"
            f"{'(替换: ' + str(change) + ')' if change else '(默认替换)'}, "
            f"当前方案总成本 {metrics.get('total_cost', '?')} 元, "
            f"请分析调整后可能的影响（100字以内）。"
        )

    def _template_explain(self, sol: dict) -> str:
        """LLM 不可用时的模板降级"""
        metrics = sol.get("metrics", {})
        assigns = sol.get("assignments", [])
        name = sol.get("name", "未知方案")

        tug_names = []
        for a in assigns[:3]:
            tid = a.get("tug_id", "")
            tug_names.append(tid)

        return (
            f"方案「{name}」: 调度 {len(assigns)} 艘拖轮, "
            f"总成本 {metrics.get('total_cost', 0):.0f} 元, "
            f"均衡度 {metrics.get('balance_score', 0):.2f}, "
            f"效率 {metrics.get('efficiency_score', 0):.2f}。"
            f"该方案优先考虑了成本优化, "
            f"指派 {', '.join(tug_names)} 等拖轮执行任务。"
        )

    def _template_counterfactual(self, sol: dict, change: Optional[dict]) -> str:
        """反事实模板降级"""
        metrics = sol.get("metrics", {})
        current_cost = metrics.get("total_cost", 0)
        estimated = current_cost * 1.1
        return (
            f"若调整拖轮分配, 预计总成本变化至约 {estimated:.0f} 元"
            f"（变动 ±10%）, 均衡度可能下降。"
            f"建议在成本与均衡之间权衡取舍。"
        )

    def get_cached_solutions(self) -> List[dict]:
        """获取所有缓存方案摘要"""
        return [
            {"solution_id": sid, "name": data.get("name", "")}
            for sid, data in self.solution_cache.items()
        ]
