# main.py
"""
CMATSS 认知多智能体拖轮调度系统 - 主入口
运行方式: python main.py
访问地址: http://localhost:8000
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from agents.master_agent import MasterAgent
from interfaces.schemas import (
    ScheduleRequest, ScheduleResponse, ListResponse,
    ComplianceCheckResponse, DepartureInfo, ExplanationResponse,
)
from pydantic import BaseModel
from typing import Optional, Any, Dict


class ExplainRequest(BaseModel):
    solution_id: str


class CounterfactualRequest(BaseModel):
    solution_id: str
    change: Optional[Dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    solution_id: str
    adopted: bool
    actual_cost: Optional[float] = None
    note: str = ""


# ============ 数据加载 ============
from data.loader import load_tugs, load_berths, load_jobs, load_rules
from utils.departure_estimator import departure_estimator
from utils.tide_predictor import tide_predictor
from config import API_HOST, API_PORT, LOG_LEVEL

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("CMATSS")

# 全局 Agent 实例
master_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global master_agent
    logger.info("🚀 正在初始化 CMATSS 系统...")
    master_agent = MasterAgent()

    # 初始化数据库持久化
    from data.database import ensure_db_sync
    try:
        ensure_db_sync()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning("数据库初始化失败 (不影响核心功能): %s", e)

    logger.info("✅ 系统初始化完成!")
    yield
    logger.info("👋 系统关闭")


app = FastAPI(
    title="CMATSS 拖轮调度系统",
    description="认知多智能体拖轮调度系统 Demo",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 静态文件 ============

@app.get("/")
async def index():
    """首页"""
    return FileResponse("frontend/index.html")


@app.get("/favicon.ico")
async def favicon():
    """favicon (data URI in HTML, 后端占位避免 404)"""
    from fastapi.responses import Response
    return Response(status_code=204)


# 挂载前端静态文件 (使用绝对路径避免工作目录依赖)
import os as _os
_frontend_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "frontend")
try:
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")
except Exception as _e:
    logger.warning(f"前端目录挂载失败 ({_frontend_dir}): {_e}")


# ============ API 接口 ============

@app.get("/api/tugs")
def get_tugs():
    """获取所有拖轮"""
    tugs = master_agent.get_all_tugs()
    return ListResponse(data=[t.model_dump() for t in tugs], total=len(tugs))


@app.get("/api/berths")
def get_berths():
    """获取所有泊位"""
    berths = load_berths()
    return ListResponse(data=[b.model_dump() for b in berths], total=len(berths))


@app.get("/api/jobs")
def get_jobs():
    """获取所有任务"""
    jobs = load_jobs()
    return ListResponse(data=[j.model_dump() for j in jobs], total=len(jobs))


@app.get("/api/rules")
def get_rules():
    """获取所有规则（三类合并）"""
    all_rules = master_agent.rule_engine.get_all_rules()
    return ListResponse(data=all_rules, total=len(all_rules))


@app.post("/api/schedule", response_model=ScheduleResponse)
def schedule(request: ScheduleRequest = Body()):
    """执行调度"""
    try:
        solutions = master_agent.schedule(request.job_ids)
        return ScheduleResponse(success=True, solutions=solutions)
    except Exception as e:
        logger.error(f"调度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compliance/check", response_model=ComplianceCheckResponse)
def compliance_check(tug_id: str = Body(...), job_id: str = Body(...)):
    """检查拖轮执行任务的合规性"""
    try:
        result = master_agent.check_compliance(tug_id, job_id)
        return result
    except Exception as e:
        logger.error(f"合规检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/departure-time")
def get_departure_time(tug_id: str = Body(...), job_id: str = Body(...), is_low_tide: Optional[bool] = Body(None)):
    """估算备车出发时间 (is_low_tide=None 自动检测)"""
    if not master_agent:
        raise HTTPException(status_code=503, detail="系统未初始化")
    tugs = load_tugs()
    jobs = load_jobs()
    berths = load_berths()

    tug = next((t for t in tugs if t.id == tug_id), None)
    job = next((j for j in jobs if j.id == job_id), None)
    if not tug or not job:
        raise HTTPException(status_code=404, detail="拖轮或任务不存在")

    target_berth = next((b for b in berths if b.id == job.target_berth_id), None)
    if not target_berth:
        raise HTTPException(status_code=404, detail="目标泊位不存在")

    info = departure_estimator.estimate_for_tug_job(
        tug_lng=tug.position.lng, tug_lat=tug.position.lat,
        tug_name=tug.name,
        target_lng=target_berth.position.lng, target_lat=target_berth.position.lat,
        target_name=target_berth.name,
        is_low_tide=is_low_tide,
        job_start_time=job.start_time,
    )

    est_departure = info.estimate_departure(job.start_time)

    return DepartureInfo(
        tug_id=tug.id,
        tug_name=tug.name,
        job_id=job.id,
        target_berth_name=target_berth.name,
        distance_nm=info.distance_nm,
        travel_time_min=info.travel_time_min,
        aux_time_min=info.aux_time_min,
        early_arrival_min=info.early_arrival_min,
        prep_time_min=info.prep_time_min,
        departure_time_desc=info.departure_time,
        estimated_departure_time=est_departure.isoformat(),
        base_name=info.base_name,
        note=info.note,
    )


@app.get("/api/health")
def health_check():
    """健康检查"""
    agents_status = {"master": master_agent.health_check() if master_agent else None}
    if master_agent:
        try:
            agents_status["explainer"] = master_agent.explainer_agent.health_check()
        except Exception:
            agents_status["explainer"] = {"status": "unavailable"}
    return {"status": "healthy", "agents": agents_status}


# ============ Agent5 解释接口 ============


@app.post("/api/explain", response_model=ExplanationResponse)
def explain_solution(req: ExplainRequest = Body()):
    """解释指定调度方案"""
    if not master_agent:
        raise HTTPException(status_code=503, detail="系统未初始化")
    try:
        return master_agent.explainer_agent.explain_solution(req.solution_id)
    except Exception as e:
        logger.error(f"解释生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/counterfactual", response_model=ExplanationResponse)
def counterfactual(req: CounterfactualRequest = Body()):
    """反事实推演"""
    if not master_agent:
        raise HTTPException(status_code=503, detail="系统未初始化")
    try:
        return master_agent.explainer_agent.counterfactual_reasoning(
            req.solution_id, req.change
        )
    except Exception as e:
        logger.error(f"反事实推演失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/explain/history")
def explain_history():
    """获取已缓存可解释的方案列表"""
    if not master_agent:
        return {"error": "系统未初始化"}
    return {"solutions": master_agent.explainer_agent.get_cached_solutions()}


# ============ 潮汐信息接口 ============


@app.get("/api/tide")
def get_tide_info(date: str = None):
    """获取指定日期潮汐信息 (默认当天)"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    schedule = tide_predictor.get_tide_schedule(date)
    return schedule


class CableRiskRequest(BaseModel):
    berth_id: str = ""
    tide_level: Optional[float] = None
    ship_draft: float = 10.0
    berth_depth: float = 15.0


@app.post("/api/tide/cable-risk")
def check_cable_risk(req: CableRiskRequest):
    """检查缆绳风险 (tide_level=None 则实时预测)"""
    tide_level = req.tide_level
    if tide_level is None:
        tide_level = tide_predictor.predict(datetime.now()).level
    result = tide_predictor.get_cable_risk_for_berth(tide_level, req.ship_draft, req.berth_depth)
    return result


@app.get("/api/learning/stats")
def learning_stats():
    """自学习统计"""
    if not master_agent:
        return {"error": "系统未初始化"}
    return master_agent.learning_engine.get_stats()


@app.get("/api/learning/analysis")
def learning_analysis():
    """自学习分析与参数建议"""
    if not master_agent:
        return {"error": "系统未初始化"}
    analysis = master_agent.learning_engine.analyze()
    adjustments = master_agent.learning_engine.get_param_adjustments()
    return {"analysis": analysis, "adjustments": adjustments}


@app.post("/api/learning/feedback")
def learning_feedback(req: FeedbackRequest = Body()):
    """提交方案采纳反馈, 触发自学习调整"""
    if not master_agent:
        raise HTTPException(status_code=503, detail="系统未初始化")

    # 在历史记录中标记
    schedules = master_agent.learning_engine.history.get("schedules", [])
    for i, s in enumerate(schedules):
        if s.get("solution_name", "") == req.solution_id:
            master_agent.learning_engine.record_feedback(
                i, req.adopted, req.actual_cost, req.note
            )
            break

    # 应用调整
    result = master_agent.learning_engine.apply_adjustments()
    return {"status": "ok", "adjustment_result": result}


@app.get("/api/dashboard")
def dashboard():
    """拖轮状态看板数据"""
    if not master_agent:
        return {"error": "系统未初始化"}
    tugs = master_agent.get_all_tugs()
    all_jobs = load_jobs()

    status_dist = {}
    fatigue_dist = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    available = 0
    for tug in tugs:
        s = tug.status.value if hasattr(tug.status, 'value') else str(tug.status)
        status_dist[s] = status_dist.get(s, 0) + 1
        fl = tug.fatigue_level.value if hasattr(tug.fatigue_level, 'value') else str(tug.fatigue_level)
        fatigue_dist[fl] = fatigue_dist.get(fl, 0) + 1
        if s == "AVAILABLE":
            available += 1

    return {
        "total_tugs": len(tugs),
        "available_tugs": available,
        "total_jobs": len(all_jobs),
        "status_distribution": status_dist,
        "fatigue_distribution": fatigue_dist,
        "fatigue_warning_threshold": 7.0,
        "fatigue_lock_threshold": 10.0,
    }


# ============ 启动 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )
