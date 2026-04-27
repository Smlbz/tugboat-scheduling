# CMATSS 开发指南

## 环境准备

```bash
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## 核心模块

### MasterAgent + OptimizerAgent (`agents/master_agent.py`, `agents/optimizer_agent.py`)

**MasterAgent** 是调度中枢：
- `schedule(job_ids)` → 3个方案 (省油/均衡/综合最优)
- `identify_chain_jobs(jobs)` → 连活任务对 (时间间隔<2h, 距离<5nm)
- 内部调用5个SlaveAgent协作

**OptimizerAgent** 运行NSGA-II：
- 3目标: 成本最小化 / 均衡度最大化 / 效率最大化
- 参数: 种群60, 代数30, 交叉0.8, 变异0.2
- Pareto前沿 → Top-3方案
- 贪心回退保障: 3策略 (cost/balance/overall)

### PerceptionAgent + FatigueAgent (`agents/perception_agent.py`, `agents/fatigue_agent.py`)

**PerceptionAgent**:
- `get_berth_distance(id1, id2)` → Haversine距离
- Stack推演: 外档(Front) / 内档(Back), LIFO约束
- `get_hidden_tasks(berths)` → 隐性任务 (移泊/辅助带缆/航道清理)

**FatigueAgent** (BFM模型):
- 公式: 新疲劳 = 当前 + 白天工时×1.0 + 夜间工时×1.5
- 连续工作惩罚: 连续>4h额外+1
- 休息恢复: 基础0.5/h, 深度休息(>2h)加成
- 三级: GREEN(<7), YELLOW(7-10), RED(≥10锁定)
- 锁定拖轮不可派工

### ComplianceAgent + ExplainerAgent (`agents/compliance_agent.py`, `agents/explainer_agent.py`)

**ComplianceAgent** 规则引擎:
- 8条核心规则: 名称相似/老旧船/马力匹配/疲劳锁/夜间资质/内档限制/连续工时/危化品
- CSV导入USAGE_SPEC (马力配比)
- XLSX导入DISPATCH_FACTOR (定性因子)
- ChromaDB向量检索, 关键词匹配降级

**ExplainerAgent**:
- LLM生成自然语言解释
- 反事实推演 (换拖轮会怎样)
- LLM不可用时自动模板降级

### 前端 (`frontend/`)

纯JS单页应用:
- Leaflet GIS青岛港地图 (暗色主题)
- 拖轮标记: 绿=可用, 黄=疲劳警告, 红=锁定, 蓝=工作中
- 左侧任务面板, 右侧方案卡片
- 采纳动画 + 连活金线 + 违规弹窗
- TTS语音播报

## 配置

```
.env  → LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
config/__init__.py → 系统参数 (阈值/端口/模式)
config/algorithm_config.py → NSGA-II/DRL参数
```

## 数据

所有模拟数据在 `data/`:
- `tugs.json` — 60拖轮 (马力/位置/状态/疲劳)
- `berths.json` — 10泊位 (坐标/堆栈)
- `jobs.json` — 50任务 (类型/时间/泊位)
- `rules.json` — 10条合规规则
- `rules_usage.json` — CSV导入的马力配比
- `rules_factors.json` — XLSX导入的调配因子

## 测试

```bash
# 单元测试
python -m pytest tests/test_agents.py -v

# 性能基准 (5/10/20/30/50 任务)
python tests/benchmark.py

# 论文图表
python tests/plot_thesis_report.py

# 集成测试 (项目根目录)
python ../test_cmatss.py
```

## 常见问题

| 问题 | 解决 |
|------|------|
| LLM没配置 | 自动降级模板回复, 不影响调度 |
| ChromaDB不可用 | 自动降级关键词匹配 |
| 端口冲突 | `config/__init__.py` 改 `API_PORT` |
| 数据修改后不生效 | 重启服务 (热重载已开启) |
