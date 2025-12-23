# 🚢 CMATSS - 认知多智能体拖轮调度系统

Cognitive Multi-Agent Tugboat Scheduling System

## 项目简介

基于多智能体架构的港口拖轮智能调度系统，支持连活识别、疲劳管理、合规检查等核心功能。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Web UI)                     │
│                   成员D 负责开发                          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP API
┌────────────────────────┴────────────────────────────────┐
│                    MasterAgent                           │
│                   成员A 负责开发                          │
└───────┬─────────┬─────────┬─────────┬─────────┬─────────┘
        │         │         │         │         │
   ┌────┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐
   │Agent1  │ │Agent2 │ │Agent3 │ │Agent4 │ │Agent5 │
   │感知    │ │合规   │ │疲劳   │ │优化   │ │解释   │
   │成员C   │ │成员B  │ │成员C  │ │成员A  │ │成员B  │
   └────────┘ └───────┘ └───────┘ └───────┘ └───────┘
```

## 快速开始

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd cmatss

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python main.py

# 4. 访问系统
# 浏览器打开 http://localhost:8000
```

## 项目结构

```
cmatss/
├── main.py                 # 主入口
├── config.py               # 配置文件
├── requirements.txt        # 依赖
├── agents/                 # 智能体模块
│   ├── base_agent.py       # 基类
│   ├── master_agent.py     # 主控 (成员A)
│   ├── perception_agent.py # 感知 (成员C)
│   ├── compliance_agent.py # 合规 (成员B)
│   ├── fatigue_agent.py    # 疲劳 (成员C)
│   ├── optimizer_agent.py  # 优化 (成员A)
│   └── explainer_agent.py  # 解释 (成员B)
├── interfaces/             # 数据模型
│   └── schemas.py          # Pydantic 模型
├── data/                   # 数据文件
│   ├── tugs.json
│   ├── berths.json
│   ├── jobs.json
│   └── rules.json
└── frontend/               # 前端 (成员D)
    ├── index.html
    ├── style.css
    └── main.js
```

## 成员分工

| 成员 | 负责模块 | 文件 |
|------|----------|------|
| A | MasterAgent + Agent4 | `master_agent.py`, `optimizer_agent.py` |
| B | Agent2 + Agent5 | `compliance_agent.py`, `explainer_agent.py` |
| C | Agent1 + Agent3 | `perception_agent.py`, `fatigue_agent.py` |
| D | 前端 | `frontend/` |

## 开发指南

详见 [DEVELOPMENT.md](./DEVELOPMENT.md)

## API 文档

启动服务后访问: http://localhost:8000/docs
