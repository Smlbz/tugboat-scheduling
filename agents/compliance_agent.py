# agents/compliance_agent.py
"""
SlaveAgent2 - 规则与知识守护智能体
负责人: 成员B

职责:
- 向量数据库搭建（规则检索）
- 合规检查器（全部10条规则）
- 名称混淆检测（R001）
- 违规原因生成
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from interfaces.schemas import ComplianceCheckResponse, Rule
from data.loader import load_rules, get_tug_by_id, get_job_by_id
from datetime import datetime


class ComplianceAgent(BaseAgent):
    """规则与知识守护智能体"""

    agent_name = "SlaveAgent2"

    def __init__(self):
        super().__init__()
        self.rules = load_rules()
        self.rules_dict = {r.id: r for r in self.rules}
        self.logger.info(f"加载了 {len(self.rules)} 条业务规则")

        # 尝试初始化向量数据库（可选，失败不阻塞）
        self.vector_db = None
        self._init_vector_db()

    def _init_vector_db(self):
        """
        初始化向量数据库（ChromaDB）

        如未安装 chromadb 或配置，跳过不影响功能
        """
        try:
            import chromadb
            self.vector_db = chromadb.Client()
            self.collection = self.vector_db.create_collection(
                name="rules", metadata={"hnsw:space": "cosine"}
            )
            # 导入规则到向量库
            for rule in self.rules:
                self.collection.add(
                    documents=[f"{rule.name}: {rule.description}"],
                    metadatas=[{"id": rule.id, "category": rule.category, "severity": rule.severity}],
                    ids=[rule.id]
                )
            self.logger.info(f"向量数据库初始化成功，导入 {len(self.rules)} 条规则")
        except ImportError:
            self.logger.info("ChromaDB 未安装，跳过向量数据库")
        except Exception as e:
            self.logger.warning(f"向量数据库初始化失败: {e}")

    def process(self, request: Dict) -> Dict:
        """通用处理接口"""
        result = self.check_compliance(
            request.get("tug_id"),
            request.get("job_id")
        )
        return result.model_dump()

    def _check_name_similarity(self, tug_name: str, assigned_tugs: List[str]) -> bool:
        """
        检查名称混淆（R001）

        规则: 名称相似的拖轮不能同时分配给同一作业
        检测方法:
        - 移除数字后缀后比较基础名称
        - 检查是否为同系列船（亚洲X号、青港拖X等）
        """
        import re

        def normalize(name: str) -> str:
            """提取名称的基础部分（去掉数字后缀）"""
            return re.sub(r'[\d]+号?$', '', name).strip()

        base = normalize(tug_name)

        for other_name in assigned_tugs:
            other_base = normalize(other_name)
            # 基础名称相同 → 同系列 → 混淆风险
            if base and base == other_base:
                return True
            # 包含关系: "亚洲" 包含在 "亚洲1号" / "亚洲2号" 中
            if len(base) >= 2 and len(other_base) >= 2 and (base in other_base or other_base in base):
                return True

        return False

    def check_compliance(self, tug_id: str, job_id: str, assigned_tug_ids: List[str] = None) -> ComplianceCheckResponse:
        """
        检查拖轮执行任务是否合规

        按 R001-R010 逐条检查，返回所有违规项
        assigned_tug_ids: 同一作业已分配的其他拖轮（用于R001名称混淆检查）
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

        # R001: 名称混淆禁止
        if assigned_tug_ids:
            assigned_names = []
            for tid in assigned_tug_ids:
                t = get_tug_by_id(tid)
                if t:
                    assigned_names.append(t.name)
            if self._check_name_similarity(tug.name, assigned_names):
                violations.append("R001")

        # R002: 老旧拖轮高危限制
        if tug.ship_age > 20 and job.is_high_risk:
            violations.append("R002")

        # R003: 马力匹配
        if tug.horsepower < job.required_horsepower / max(job.required_tug_count, 1):
            violations.append("R003")

        # R004: 疲劳船员禁派（由 FatigueAgent 负责，这里做二次检查）
        if tug.fatigue_level == "RED":
            violations.append("R004")

        # R005: 夜间作业资质
        if job.start_time:
            hour = job.start_time.hour
            if hour >= 22 or hour < 6:
                if not self._has_night_qualification(tug):
                    violations.append("R005")

        # R006: 内档船移泊优先（警告级别，不阻止）
        if tug.berth_position and tug.berth_position == "INNER":
            # 内档船可以使用，但效率较低，记录但不算违规
            pass

        # R007: 连续作业限制
        if tug.today_work_hours > 4:
            violations.append("R007")

        # R008: 危化品专用泊位（由调度逻辑处理，这里检查）
        if job.is_high_risk and "危化品" in job.special_requirements:
            if not self._has_hazmat_qualification(tug):
                violations.append("R008")

        # R009: 作业均衡分配（由 optimizer 评分函数处理）
        # R010: 连活优先识别（由 master_agent 的 identify_chain_jobs 处理）

        if violations:
            reason = self._generate_violation_reason(violations, tug, job)
            return ComplianceCheckResponse(
                is_compliant=False,
                violation_rules=violations,
                violation_reason=reason
            )

        return ComplianceCheckResponse(is_compliant=True)

    def _has_night_qualification(self, tug) -> bool:
        """检查拖轮是否有夜间作业资质"""
        # Demo 版: 已工作超过8小时的视为不具备
        if tug.today_work_hours >= 8:
            return False
        # 大多数拖轮具备夜间资质
        return True

    def _has_hazmat_qualification(self, tug) -> bool:
        """检查拖轮是否有危化品作业资质"""
        # Demo版: 马力 >= 5000 的视为有危化品资质
        return tug.horsepower >= 5000

    def _generate_violation_reason(self, violations: List[str], tug, job) -> str:
        """
        生成人类可读的违规原因

        使用规则描述生成详细原因，支持多规则组合
        """
        reasons = []
        for v in violations:
            rule = self.rules_dict.get(v)
            if v == "R001":
                reasons.append(f"拖轮 '{tug.name}' 与同作业其他拖轮名称相似，存在调度混淆风险（{rule.description if rule else 'R001'}）")
            elif v == "R002":
                reasons.append(f"拖轮 '{tug.name}' 船龄 {tug.ship_age} 年，超过20年限制，不得执行高危作业（{rule.description if rule else 'R002'}）")
            elif v == "R003":
                need_hp = job.required_horsepower / max(job.required_tug_count, 1)
                reasons.append(f"拖轮 '{tug.name}' 马力 {tug.horsepower}，不满足任务所需单船最低马力 {need_hp:.0f}（{rule.description if rule else 'R003'}）")
            elif v == "R004":
                reasons.append(f"拖轮 '{tug.name}' 疲劳值 {tug.fatigue_value}，超过红色阈值禁止派遣（{rule.description if rule else 'R004'}）")
            elif v == "R005":
                reasons.append(f"拖轮 '{tug.name}' 不具备夜间作业资质，无法执行 {job.start_time.hour}:00 的夜间任务（{rule.description if rule else 'R005'}）")
            elif v == "R007":
                reasons.append(f"拖轮 '{tug.name}' 今日已工作 {tug.today_work_hours:.0f} 小时，超过连续作业限制（{rule.description if rule else 'R007'}）")
            elif v == "R008":
                reasons.append(f"拖轮 '{tug.name}' 不具备危化品作业资质，无法执行危化品任务（{rule.description if rule else 'R008'}）")
            else:
                desc = f"（{rule.description}）" if rule else ""
                reasons.append(f"拖轮 '{tug.name}' 违反规则 {v}{desc}")

        return "；".join(reasons)

    def search_rules(self, query: str) -> List[Rule]:
        """
        检索相关规则

        优先使用向量数据库，不可用时降级为关键词匹配
        """
        # 尝试向量检索
        if self.vector_db and hasattr(self, 'collection'):
            try:
                results = self.collection.query(query_texts=[query], n_results=5)
                rule_ids = [m["id"] for m in results["metadatas"][0]]
                return [self.rules_dict[rid] for rid in rule_ids if rid in self.rules_dict]
            except Exception:
                pass

        # 降级: 关键词匹配（优化版：按匹配数量排序）
        scored = []
        query_lower = query.lower()
        for rule in self.rules:
            score = 0
            for kw in rule.keywords:
                if kw.lower() in query_lower:
                    score += 1
            if score > 0:
                scored.append((score, rule))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored]
