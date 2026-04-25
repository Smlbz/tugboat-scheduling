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

from agents.master_agent import MasterAgent
from interfaces.schemas import ScheduleRequest, ScheduleResponse, ListResponse, ComplianceCheckResponse
from data.loader import load_tugs, load_berths, load_jobs, load_rules
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


# 挂载前端静态文件
try:
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
except:
    logger.warning("前端目录不存在，跳过静态文件挂载")


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
def schedule(request: ScheduleRequest):
    """执行调度"""
    try:
        solutions = master_agent.schedule(request.job_ids)
        return ScheduleResponse(success=True, solutions=solutions)
    except Exception as e:
        logger.error(f"调度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/explain")
def explain(solution_id: str, question: str = None):
    """生成解释"""
    try:
        explanation = master_agent.get_explanation(solution_id, question)
        return {"explanation": explanation}
    except Exception as e:
        logger.error(f"解释生成失败: {e}")
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


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "agents": {
            "master": master_agent.health_check() if master_agent else None
        }
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
