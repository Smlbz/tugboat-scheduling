# interfaces/schemas.py
"""
CMATSS 核心数据模型定义
版本: 1.0.0
修改此文件需要技术负责人确认！

使用规范:
- 时间: ISO 8601 格式，带时区
- 坐标: GeoJSON顺序 {lng, lat}
- ID: 前缀+数字 (TUG001, JOB001, B001)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


# ============ 枚举类型 ============

class TugStatus(str, Enum):
    """拖轮状态"""
    AVAILABLE = "AVAILABLE"           # 空闲可用
    BUSY = "BUSY"                     # 作业中
    LOCKED_BY_FRMS = "LOCKED_BY_FRMS" # 疲劳锁定
    MAINTENANCE = "MAINTENANCE"       # 维护保养


class BerthPosition(str, Enum):
    """泊位档位"""
    OUTER = "OUTER"  # 外档(可直接出动)
    INNER = "INNER"  # 内档(需先移泊)


class JobType(str, Enum):
    """任务类型"""
    BERTHING = "BERTHING"       # 靠泊
    UNBERTHING = "UNBERTHING"   # 离泊
    SHIFTING = "SHIFTING"       # 移泊
    ESCORT = "ESCORT"           # 护航


class FatigueLevel(str, Enum):
    """疲劳等级"""
    GREEN = "GREEN"    # 正常 (0-7)
    YELLOW = "YELLOW"  # 警告 (7-10)
    RED = "RED"        # 锁定 (>10)


class RuleType(str, Enum):
    """规则类型"""
    USAGE_SPEC = "USAGE_SPEC"           # 参数型: 条件→需求值(CSV来源)
    DISPATCH_FACTOR = "DISPATCH_FACTOR" # 因素型: 定性调度原则(XLSX来源)
    COMPLIANCE = "COMPLIANCE"           # 合规型: 条件→违规判定(JSON来源)


class RuleCategory(str, Enum):
    """规则分类"""
    SAFETY = "SAFETY"       # 安全类
    EFFICIENCY = "EFFICIENCY"  # 效率类
    COMPLIANCE = "COMPLIANCE"  # 合规类


class RuleSeverity(str, Enum):
    """规则严重程度"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ============ 基础模型 ============

class Position(BaseModel):
    """地理位置 (GeoJSON顺序)"""
    lng: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")


# ============ 核心实体 ============

class Tug(BaseModel):
    """拖轮实体"""
    id: str = Field(..., description="唯一标识, 如 TUG001")
    name: str = Field(..., description="拖轮名称, 如 青港拖1")
    horsepower: int = Field(..., description="马力值")
    position: Position = Field(..., description="当前位置")
    berth_id: Optional[str] = Field(None, description="停靠的泊位ID")
    berth_position: Optional[BerthPosition] = Field(None, description="内档/外档")
    status: TugStatus = Field(default=TugStatus.AVAILABLE)
    fatigue_value: float = Field(default=0.0, ge=0, le=15, description="疲劳值 0-15")
    fatigue_level: FatigueLevel = Field(default=FatigueLevel.GREEN)
    today_work_hours: float = Field(default=0.0, ge=0, description="今日已工作时长")
    ship_age: int = Field(default=0, ge=0, description="船龄(年)")
    crew_id: Optional[str] = Field(None, description="船员组ID")

    class Config:
        use_enum_values = True


class Berth(BaseModel):
    """泊位实体"""
    id: str = Field(..., description="泊位ID, 如 B001")
    name: str = Field(..., description="泊位名称")
    position: Position
    tugs_stack: List[str] = Field(default=[], description="停靠的拖轮ID栈, 最后一个是外档")
    max_capacity: int = Field(default=3, description="最大停靠数")
    berth_type: str = Field(default="NORMAL", description="泊位类型")


class Job(BaseModel):
    """调度任务"""
    id: str = Field(..., description="任务ID")
    job_type: JobType
    ship_name: str = Field(..., description="服务船舶名称")
    ship_type: Optional[str] = Field(None, description="船舶类型(油船/杂货船/集装箱船/散货船)")
    ship_length: Optional[float] = Field(None, description="船长(米)")
    ship_tonnage: Optional[int] = Field(None, description="吨位")
    draft_depth: Optional[float] = Field(None, description="吃水深度(米)")
    target_berth_id: str = Field(..., description="目标泊位")
    start_time: datetime
    end_time: datetime
    required_horsepower: int = Field(..., description="需求马力")
    required_tug_count: int = Field(default=1, ge=1, description="需要拖轮数量")
    priority: int = Field(default=5, ge=1, le=10, description="优先级 1-10, 10最高")
    is_high_risk: bool = Field(default=False, description="是否高危作业")
    special_requirements: List[str] = Field(default=[], description="特殊要求")

    class Config:
        use_enum_values = True


class Rule(BaseModel):
    """业务规则"""
    id: str = Field(..., description="规则ID, 如 R001")
    name: str = Field(..., description="规则名称")
    rule_type: RuleType = Field(default=RuleType.COMPLIANCE, description="规则类型")
    category: RuleCategory
    severity: RuleSeverity
    description: str = Field(..., description="规则描述")
    check_logic: Optional[str] = Field(None, description="检查逻辑表达式")
    keywords: List[str] = Field(default=[], description="关键词, 用于向量检索")
    conditions: Optional[Dict[str, Any]] = Field(None, description="条件字段(USAGE_SPEC用): ship_type/length/draft/operation")
    result: Optional[Dict[str, Any]] = Field(None, description="结果字段(USAGE_SPEC用): horsepower/tug_count")
    source: str = Field(default="manual", description="来源标记: csv/xlsx/manual")
    enabled: bool = Field(default=True)

    class Config:
        use_enum_values = True


# ============ Agent 通信模型 ============

class ComplianceCheckRequest(BaseModel):
    """Agent2 合规检查请求"""
    tug_id: str
    job_id: str


class ComplianceCheckResponse(BaseModel):
    """Agent2 合规检查响应"""
    is_compliant: bool
    violation_rules: List[str] = Field(default=[])
    violation_reason: Optional[str] = None


class FatigueCheckResponse(BaseModel):
    """Agent3 疲劳检查响应"""
    tug_id: str
    fatigue_value: float
    fatigue_level: FatigueLevel
    is_available: bool
    lock_reason: Optional[str] = None

    class Config:
        use_enum_values = True


class ChainJobPair(BaseModel):
    """连活任务对"""
    job1_id: str
    job2_id: str
    interval_hours: float = Field(..., description="时间间隔(小时)")
    distance_nm: float = Field(..., description="距离(海里)")
    cost_saving: float = Field(..., description="节省成本(元)")


class Assignment(BaseModel):
    """单个调度分配"""
    tug_id: str
    tug_name: str
    job_id: str
    job_type: JobType
    score: float = Field(..., ge=0, le=1, description="评分 0-1")

    class Config:
        use_enum_values = True


class SolutionMetrics(BaseModel):
    """方案评价指标"""
    total_cost: float = Field(..., description="总燃油成本(元)")
    balance_score: float = Field(..., ge=0, le=1, description="作业均衡度 0-1")
    efficiency_score: float = Field(..., ge=0, le=1, description="效率评分 0-1")
    overall_score: float = Field(..., ge=0, le=1, description="综合评分 0-1")


class ScheduleSolution(BaseModel):
    """调度方案"""
    solution_id: str
    name: str = Field(..., description="方案名称, 如'省油方案'")
    assignments: List[Assignment]
    metrics: SolutionMetrics
    chain_jobs: List[ChainJobPair] = Field(default=[], description="识别出的连活对")
    hidden_tasks: List[str] = Field(default=[], description="生成的隐性任务ID")


class ExplanationResponse(BaseModel):
    """Agent5 解释响应"""
    explanation: str = Field(..., description="自然语言解释")
    counterfactual: Optional[str] = Field(None, description="反事实推演结果")


# ============ API 请求响应 ============

class ScheduleRequest(BaseModel):
    """调度请求"""
    job_ids: List[str] = Field(..., min_length=1, description="待排任务ID列表")


class ScheduleResponse(BaseModel):
    """调度响应"""
    success: bool
    solutions: List[ScheduleSolution] = Field(default=[])
    error_message: Optional[str] = None


class ListResponse(BaseModel):
    """通用列表响应"""
    data: List[Any]
    total: int


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error_code: str
    error_message: str
