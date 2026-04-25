# agents/explainer_agent.py
"""
SlaveAgent5 - 分析与学习智能体
负责人: 成员B

职责:
- 自然语言解释生成（模板 + LLM）
- 反事实推演（为什么不派某艘拖轮）
- 方案对比分析
"""

from typing import Optional
from agents.base_agent import BaseAgent
from interfaces.schemas import ExplanationResponse
from data.loader import load_tugs, load_jobs, get_tug_by_id, get_job_by_id
from config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL


class ExplainerAgent(BaseAgent):
    """分析与学习智能体"""

    agent_name = "SlaveAgent5"

    def __init__(self):
        super().__init__()
        self.solutions_cache = {}

        # 初始化 LLM 客户端（如已配置）
        self.llm_client = None
        if LLM_API_KEY:
            self._init_llm_client()

    def _init_llm_client(self):
        """
        初始化 LLM 客户端

        支持 DeepSeek / OpenAI 兼容接口
        """
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL
            )
            self.logger.info(f"LLM 客户端初始化成功: {LLM_PROVIDER} ({LLM_MODEL})")
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
        """缓存方案数据用于解释"""
        self.solutions_cache[solution_id] = solution_data

    def explain(self, solution_id: str, question: str = None) -> ExplanationResponse:
        """
        生成自然语言解释

        无 question: 方案解释
        有 question: 反事实推演（如"为什么不派亚洲2号"）
        """
        solution = self.solutions_cache.get(solution_id)

        if question:
            return self._counterfactual_reasoning(solution, question)
        else:
            return self._generate_explanation(solution)

    def _extract_tug_name_from_question(self, question: str) -> Optional[str]:
        """从问题中提取拖轮名称"""
        import re
        # 常见模式: "为什么不派XXX" "为什么不用XXX" "亚洲2号怎么样"
        tugs = load_tugs()
        for tug in tugs:
            if tug.name in question:
                return tug.name
        return None

    def _lookup_tug_state(self, tug_name: str) -> dict:
        """查询拖轮的当前状态（用于反事实推演）"""
        tugs = load_tugs()
        for tug in tugs:
            if tug.name == tug_name:
                return {
                    "name": tug.name,
                    "horsepower": tug.horsepower,
                    "status": tug.status,
                    "fatigue_value": tug.fatigue_value,
                    "fatigue_level": tug.fatigue_level,
                    "today_work_hours": tug.today_work_hours,
                    "ship_age": tug.ship_age,
                    "berth_position": tug.berth_position if tug.berth_position else "未知",
                    "is_inner": tug.berth_position == "INNER" if tug.berth_position else False,
                }
        return None

    def _generate_explanation(self, solution: dict) -> ExplanationResponse:
        """
        生成方案解释

        优先使用 LLM，不可用时生成结构化模板解释
        """
        if self.llm_client and solution:
            prompt = self._build_explanation_prompt(solution)
            explanation = self._call_llm(prompt)
            if explanation:
                return ExplanationResponse(explanation=explanation)

        # 模板降级: 从方案数据生成结构化解释
        return self._template_explanation(solution)

    def _template_explanation(self, solution: dict) -> ExplanationResponse:
        """基于模板生成方案解释"""
        if not solution:
            return ExplanationResponse(explanation="暂无方案数据。")

        name = solution.get("name", "未知方案")
        metrics = solution.get("metrics", {})
        assignments = solution.get("assignments", [])
        chain_jobs = solution.get("chain_jobs", [])

        parts = [f"【{name}】"]

        # 分配详情
        if assignments:
            tug_summary = {}
            for a in assignments:
                tug_id = a.get("tug_id", "")
                tug_name = a.get("tug_name", "")
                job_id = a.get("job_id", "")
                job_type = a.get("job_type", "")
                if job_id not in tug_summary:
                    tug_summary[job_id] = {"type": job_type, "tugs": []}
                tug_summary[job_id]["tugs"].append(tug_name)

            parts.append(f"共 {len(assignments)} 个任务分配：")
            for job_id, info in tug_summary.items():
                parts.append(f"· 任务 {job_id}（{info['type']}）→ {'、'.join(info['tugs'])}")

        # 指标
        if metrics:
            parts.append(
                f"成本 ¥{metrics.get('total_cost', 0):.0f}，"
                f"均衡度 {metrics.get('balance_score', 0)*100:.0f}%，"
                f"效率 {metrics.get('efficiency_score', 0)*100:.0f}%"
            )

        # 连活信息
        if chain_jobs:
            total_saving = sum(c.get("cost_saving", 0) for c in chain_jobs)
            parts.append(f"识别到 {len(chain_jobs)} 对连活任务，共节省 ¥{total_saving:.0f}")

        return ExplanationResponse(explanation="\n".join(parts))

    def _counterfactual_reasoning(self, solution: dict, question: str) -> ExplanationResponse:
        """
        反事实推演

        解析用户问题中的拖轮名称，查询其状态，
        结合方案数据解释为什么未被选中
        """
        tug_name = self._extract_tug_name_from_question(question)

        if self.llm_client:
            # 如找到拖轮，附带状态信息到 LLM prompt
            tug_state = self._lookup_tug_state(tug_name) if tug_name else None
            prompt = self._build_counterfactual_prompt(solution, question, tug_state)
            response = self._call_llm(prompt)
            if response and "LLM 未配置" not in response and "出错" not in response:
                return ExplanationResponse(
                    explanation=response,
                    counterfactual=f"针对问题 '{question}' 的推演结果"
                )

        # 模板降级
        return self._template_counterfactual(solution, question, tug_name)

    def _template_counterfactual(self, solution: dict, question: str, tug_name: str = None) -> ExplanationResponse:
        """基于模板的反事实推演"""
        reasons = []

        if tug_name:
            state = self._lookup_tug_state(tug_name)
            if state:
                reasons.append(f"拖轮 '{tug_name}' 当前状态分析：")

                if state["fatigue_level"] == "RED":
                    reasons.append(f"· 疲劳值 {state['fatigue_value']}（红色锁定），需强制休息")
                elif state["fatigue_level"] == "YELLOW":
                    reasons.append(f"· 疲劳值 {state['fatigue_value']}（黄色警告），存在一定风险")

                if state["status"] == "BUSY":
                    reasons.append("· 当前正在作业，无法参与新任务")
                elif state["status"] == "MAINTENANCE":
                    reasons.append("· 当前处于维护保养状态")
                elif state["status"] == "LOCKED_BY_FRMS":
                    reasons.append("· 被疲劳管理系统锁定")

                if state["is_inner"]:
                    reasons.append("· 位于泊位内档，需要先移泊才能出动")

                if state["today_work_hours"] >= 8:
                    reasons.append(f"· 今日已工作 {state['today_work_hours']} 小时，接近饱和")

                if not reasons[1:]:  # 仅有前缀没有具体原因
                    reasons.append(f"· 虽然状态正常（疲劳 {state['fatigue_value']}，位置 {state['berth_position']}），但其他拖轮在综合评分上更优")
            else:
                reasons.append(f"未找到拖轮 '{tug_name}' 的信息")
        else:
            reasons.append(f"关于您的问题 '{question}'：")

        reasons.append("如果强行派遣，可能触发安全规则限制或导致作业效率下降。")

        return ExplanationResponse(
            explanation="\n".join(reasons),
            counterfactual=f"假如派遣 {tug_name or '该拖轮'}：疲劳值可能继续升高，或引发合规风险。"
        )

    def _build_explanation_prompt(self, solution: dict) -> str:
        """构建解释 Prompt"""
        if not solution:
            return "请解释暂无调度方案。"

        return f"""你是一个港口拖轮调度系统的解释助手。请根据以下调度方案，生成一段简洁的自然语言解释（3-5句话）。

## 调度方案

方案名称: {solution.get('name', '未知')}
方案ID: {solution.get('solution_id', '')}

### 任务分配
{solution.get('assignments', [])}

### 评价指标
{solution.get('metrics', {})}

### 连活任务
{solution.get('chain_jobs', [])}

## 输出要求
1. 用中文回答，简洁明了
2. 解释选船逻辑：为什么选中这些拖轮（考虑马力匹配、疲劳值、位置）
3. 说明方案的优势（成本低/均衡好/效率高）
4. 如有连活安排，特别说明节省的成本"""

    def _build_counterfactual_prompt(self, solution: dict, question: str, tug_state: dict = None) -> str:
        """构建反事实 Prompt"""
        tug_info = ""
        if tug_state:
            tug_info = f"""
## 该拖轮状态
- 拖轮名称: {tug_state['name']}
- 马力: {tug_state['horsepower']}
- 当前状态: {tug_state['status']}
- 疲劳值: {tug_state['fatigue_value']} ({tug_state['fatigue_level']})
- 今日工作量: {tug_state['today_work_hours']}小时
- 船龄: {tug_state['ship_age']}年
- 泊位位置: {tug_state['berth_position']}
"""

        return f"""你是一个港口拖轮调度系统的解释助手。用户对调度结果有疑问。

## 用户问题
{question}
{tug_info}
## 当前方案数据
{solution}

## 输出要求
1. 用中文回答
2. 解释为什么该拖轮没有被选中（或为什么选择了其他拖轮）
3. 从疲劳值、马力匹配、位置（内档/外档）、当前状态、规则合规等角度分析
4. 如强行派遣可能有什么后果
5. 简洁，3-5句话"""

    def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM

        支持 DeepSeek / OpenAI 兼容接口
        """
        if not self.llm_client:
            return "LLM 未配置"

        try:
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的港口调度系统助手，用中文简洁回答调度相关问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"LLM 调用失败: {e}")
            return f"生成解释时出错: {e}"
