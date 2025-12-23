# interfaces/__init__.py
"""
接口模块
包含所有数据模型定义
"""

from interfaces.schemas import (
    # 枚举
    TugStatus,
    BerthPosition,
    JobType,
    FatigueLevel,
    RuleCategory,
    RuleSeverity,
    # 基础类型
    Position,
    # 实体
    Tug,
    Berth,
    Job,
    Rule,
    # Agent通信
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    FatigueCheckResponse,
    ChainJobPair,
    Assignment,
    SolutionMetrics,
    ScheduleSolution,
    ExplanationResponse,
    # API
    ScheduleRequest,
    ScheduleResponse,
    ListResponse,
    ErrorResponse,
)

__all__ = [
    "TugStatus",
    "BerthPosition", 
    "JobType",
    "FatigueLevel",
    "RuleCategory",
    "RuleSeverity",
    "Position",
    "Tug",
    "Berth",
    "Job",
    "Rule",
    "ComplianceCheckRequest",
    "ComplianceCheckResponse",
    "FatigueCheckResponse",
    "ChainJobPair",
    "Assignment",
    "SolutionMetrics",
    "ScheduleSolution",
    "ExplanationResponse",
    "ScheduleRequest",
    "ScheduleResponse",
    "ListResponse",
    "ErrorResponse",
]
