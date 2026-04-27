# CMATSS — 认知多智能体拖轮调度系统

Cognitive Multi-Agent Tugboat Scheduling System

基于多智能体架构的港口拖轮智能调度系统。集成NSGA-II多目标优化、BFM疲劳管理、规则引擎合规检查、LLM解释与反事实推演、GIS可视化看板。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.x, FastAPI, Uvicorn |
| 优化算法 | DEAP (NSGA-II), 贪心回退 |
| 疲劳模型 | BFM (Bio-mathematical Fatigue Model) |
| 向量检索 | ChromaDB (可选, 有关键词降级) |
| LLM | OpenAI-compatible SDK (DeepSeek) |
| 前端 | Vanilla JS, Leaflet.js GIS, Web Speech API |
| 数据 | JSON, CSV/XLSX 规则导入 |

## 系统架构

```
Frontend (Leaflet GIS)
     │ HTTP API
MasterAgent — 调度主控 (连活识别、任务分解、结果融合)
  ├── PerceptionAgent — 感知 (泊位Stack推演、距离计算、隐性任务)
  ├── ComplianceAgent — 合规 (8条核心规则、ChromaDB向量检索)
  ├── FatigueAgent — 疲劳 (BFM模型、三级预警、锁定机制)
  ├── OptimizerAgent — 优化 (NSGA-II多目标、Pareto前沿、Top-3方案)
  └── ExplainerAgent — 解释 (LLM解释生成、反事实推演、模板降级)
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端首页 |
| GET | `/api/tugs` | 所有拖轮 (含状态/疲劳/位置) |
| GET | `/api/berths` | 所有泊位 |
| GET | `/api/jobs` | 所有调度任务 |
| GET | `/api/rules` | 所有规则 (三类合并) |
| GET | `/api/health` | 系统健康检查 |
| GET | `/api/dashboard` | 拖轮状态看板统计 |
| GET | `/api/tide?date=` | 指定日期潮汐预测 |
| GET | `/api/learning/stats` | 自学习统计 |
| GET | `/api/learning/analysis` | 自学习分析与参数建议 |
| GET | `/api/explain/history` | 已缓存可解释方案 |
| POST | `/api/schedule` | 执行调度 → Top-3方案 |
| POST | `/api/compliance/check` | 拖轮-任务合规检查 |
| POST | `/api/departure-time` | 备车出发时间估算 |
| POST | `/api/explain` | 方案解释生成 |
| POST | `/api/counterfactual` | 反事实推演 |
| POST | `/api/tide/cable-risk` | 缆绳风险评估 |
| POST | `/api/learning/feedback` | 提交方案采纳反馈 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置LLM (可选, 不影响核心调度)
cp .env.example .env  # 编辑填入 DeepSeek/OpenAI key

# 启动服务
python main.py

# 浏览器访问
open http://localhost:8000
```

## 项目结构

```
tugboat-scheduling/
├── main.py              # FastAPI 主入口
├── config/              # 系统配置 + 算法参数
├── agents/              # 6个智能体 (Master + 5 Slaves)
├── algorithms/          # NSGA-II + 自学习引擎
├── engine/              # 规则引擎 (合规检查器 + 条件匹配)
├── interfaces/          # Pydantic 数据模型
├── utils/               # LLM客户端、潮汐预测、距离估算、指标计算
├── data/                # JSON数据 + ChromaDB向量库
├── frontend/            # Leaflet GIS 前端
└── tests/               # 单元测试 + 性能基准 + 论文图表生成
```

## 测试

```bash
python -m pytest tests/test_agents.py -v    # 单元测试
python tests/benchmark.py                    # 性能基准
python tests/plot_thesis_report.py           # 论文图表+LaTeX表
```
