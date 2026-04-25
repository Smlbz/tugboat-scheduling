"""
SlaveAgent2 - 规则与知识守护智能体
职责:
- 向量数据库搭建（规则检索）
- 合规检查器（委托RuleEngine）
- 名称混淆检测
- 违规原因生成
"""

from typing import List, Dict
from agents.base_agent import BaseAgent
from interfaces.schemas import ComplianceCheckResponse, Rule
from data.loader import load_rules, get_tug_by_id, get_job_by_id
from engine.rule_engine import RuleEngine
from datetime import datetime


class ComplianceAgent(BaseAgent):
    """规则与知识守护智能体"""

    agent_name = "SlaveAgent2"

    def __init__(self):
        super().__init__()
        self.rule_engine = RuleEngine()
        self.rules = load_rules()
        self.rules_dict = {r.id: r for r in self.rules}
        self.logger.info(f"加载了 {len(self.rules)} 条业务规则")

        # 尝试初始化向量数据库（可选，失败不阻塞）
        self.vector_db = None
        self._init_vector_db()

    def _init_vector_db(self):
        """初始化向量数据库（ChromaDB）"""
        try:
            import chromadb
            self.vector_db = chromadb.Client()
            self.collection = self.vector_db.create_collection(
                name="rules", metadata={"hnsw:space": "cosine"}
            )
            all_rules = self.rule_engine.get_all_rules()
            for rule in all_rules:
                if not rule.get('id') or not rule.get('name'):
                    continue
                self.collection.add(
                    documents=[f"{rule['name']}: {rule.get('description', '')}"],
                    metadatas=[{"id": rule['id'], "category": rule.get('category', ''),
                                "severity": rule.get('severity', '')}],
                    ids=[rule['id']]
                )
            self.logger.info(f"向量数据库初始化成功，导入 {len(all_rules)} 条规则")
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

    def check_compliance(self, tug_id: str, job_id: str, assigned_tug_ids: List[str] = None) -> ComplianceCheckResponse:
        """
        检查拖轮执行任务是否合规
        委托RuleEngine执行，保留原接口签名
        """
        tug = get_tug_by_id(tug_id)
        job = get_job_by_id(job_id)

        if not tug or not job:
            return ComplianceCheckResponse(
                is_compliant=False,
                violation_rules=["SYSTEM"],
                violation_reason="拖轮或任务不存在"
            )

        # 构建assigned_tugs对象列表
        assigned_tugs = []
        if assigned_tug_ids:
            for tid in assigned_tug_ids:
                t = get_tug_by_id(tid)
                if t:
                    assigned_tugs.append(t)

        # 用RuleEngine检查
        helpers = {
            "check_night_qualification": self._has_night_qualification,
            "check_hazmat_qualification": self._has_hazmat_qualification,
        }
        violations = self.rule_engine.check_compliance(tug, job, assigned_tugs, helpers)

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
        if tug.today_work_hours >= 8:
            return False
        return True

    def _has_hazmat_qualification(self, tug) -> bool:
        """检查拖轮是否有危化品作业资质"""
        return tug.horsepower >= 5000

    def _generate_violation_reason(self, violations: List[str], tug, job) -> str:
        """
        生成人类可读的违规原因
        使用规则描述
        """
        reasons = []
        # 合并所有规则来源的描述
        all_rules = {}
        for r in self.rule_engine.get_all_rules():
            all_rules[r["id"]] = r

        for v in violations:
            rule = all_rules.get(v)
            desc = rule.get("description", v) if rule else v
            if v == "R001":
                reasons.append(f"拖轮 '{tug.name}' 与同作业其他拖轮名称相似，存在调度混淆风险（{desc}）")
            elif v == "R002":
                reasons.append(f"拖轮 '{tug.name}' 船龄 {tug.ship_age} 年，超过20年限制，不得执行高危作业（{desc}）")
            elif v == "R003":
                need_hp = job.required_horsepower / max(job.required_tug_count, 1)
                reasons.append(f"拖轮 '{tug.name}' 马力 {tug.horsepower}，不满足任务所需单船最低马力 {need_hp:.0f}（{desc}）")
            elif v == "R004":
                reasons.append(f"拖轮 '{tug.name}' 疲劳值 {tug.fatigue_value}，超过红色阈值禁止派遣（{desc}）")
            elif v == "R005":
                reasons.append(f"拖轮 '{tug.name}' 不具备夜间作业资质，无法执行 {job.start_time.hour}:00 的夜间任务（{desc}）")
            elif v == "R007":
                reasons.append(f"拖轮 '{tug.name}' 今日已工作 {tug.today_work_hours:.0f} 小时，超过连续作业限制（{desc}）")
            elif v == "R008":
                reasons.append(f"拖轮 '{tug.name}' 不具备危化品作业资质，无法执行危化品任务（{desc}）")
            else:
                reasons.append(f"拖轮 '{tug.name}' 违反规则 {v}（{desc}）")

        return "；".join(reasons)

    def search_rules(self, query: str):
        """
        检索相关规则
        优先使用向量数据库，降级关键词匹配
        """
        from interfaces.schemas import Rule as RuleSchema

        if self.vector_db and hasattr(self, 'collection'):
            try:
                results = self.collection.query(query_texts=[query], n_results=5)
                rule_ids = [m["id"] for m in results["metadatas"][0]]
                all_rules = self.rule_engine.get_all_rules()
                id_map = {r["id"]: r for r in all_rules}
                found = [id_map[rid] for rid in rule_ids if rid in id_map]
                if found:
                    return [RuleSchema(**r) for r in found]
            except Exception:
                pass

        # 降级: 关键词匹配
        scored = []
        query_lower = query.lower()
        for r in self.rule_engine.get_all_rules():
            score = 0
            for kw in r.get("keywords", []):
                if kw.lower() in query_lower:
                    score += 1
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [RuleSchema(**r) for _, r in scored]
