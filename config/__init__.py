# config/__init__.py
"""
CMATSS 系统配置文件
通过环境变量或直接修改切换模式
"""

import os
from pathlib import Path

# ========== 路径配置 ==========
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
INTERFACES_DIR = BASE_DIR / "interfaces"
AGENTS_DIR = BASE_DIR / "agents"

# ========== 模式配置 ==========
# demo: 使用本地JSON数据和同进程调用
# production: 使用数据库和微服务调用
MODE = os.getenv("CMATSS_MODE", "demo")

# ========== 服务端口 ==========
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ========== Agent 微服务地址 (生产模式使用) ==========
AGENT_URLS = {
    "agent1": os.getenv("AGENT1_URL", "http://localhost:8001"),
    "agent2": os.getenv("AGENT2_URL", "http://localhost:8002"),
    "agent3": os.getenv("AGENT3_URL", "http://localhost:8003"),
    "agent4": os.getenv("AGENT4_URL", "http://localhost:8004"),
    "agent5": os.getenv("AGENT5_URL", "http://localhost:8005"),
}

# ========== LLM 配置 (Agent5使用) ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")  # deepseek / openai
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

# ========== 业务规则阈值 ==========
# 连活判定
CHAIN_JOB_TIME_THRESHOLD_HOURS = 2.0   # 间隔小于2小时算连活
CHAIN_JOB_DISTANCE_THRESHOLD_NM = 5.0  # 距离小于5海里算连活

# 疲劳阈值
FATIGUE_WARNING_THRESHOLD = 7.0   # 黄色警告
FATIGUE_LOCK_THRESHOLD = 10.0     # 红色锁定

# 夜间时段
NIGHT_START_HOUR = 22
NIGHT_END_HOUR = 6

# 疲劳累加系数
FATIGUE_DAY_MULTIPLIER = 1.0    # 白天工作每小时增加的疲劳
FATIGUE_NIGHT_MULTIPLIER = 1.5  # 夜间工作每小时增加的疲劳

# ========== 演示模式配置 ==========
DEMO_SCENARIO = os.getenv("DEMO_SCENARIO", "default")
USE_FIXED_RESPONSE = os.getenv("USE_FIXED_RESPONSE", "false").lower() == "true"

# ========== 日志配置 ==========
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
