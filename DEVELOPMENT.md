# 🛠️ CMATSS 开发指南

本文档帮助团队成员快速上手各自负责的模块开发。

---

## 📥 第一步：环境准备

```bash
# 克隆仓库
git clone <repo-url>
cd cmatss

# 创建虚拟环境 (推荐)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -c "from agents import MasterAgent; print('✅ 环境准备完成')"
```

---

## 🧑‍💻 成员 A：MasterAgent + OptimizerAgent

**负责文件**:
- `agents/master_agent.py`
- `agents/optimizer_agent.py`

### 核心任务

#### 1. 连活算法 (`identify_chain_jobs`)
```python
# 位置: master_agent.py 第 100 行
# 输入: 任务列表
# 输出: 连活任务对列表

def identify_chain_jobs(self, jobs: List[Job]) -> List[ChainJobPair]:
    """
    TODO: 完善连活识别逻辑
    - 筛选时间间隔 < 2小时的任务对
    - 计算任务间距离
    - 计算节省成本
    """
```

#### 2. 多目标评分 (`calc_cost`, `calc_balance`, `calc_efficiency`)
```python
# 位置: optimizer_agent.py 第 140-160 行

def calc_cost(self, assignments) -> float:
    """TODO: 实现燃油成本计算 = 距离 × 油价"""

def calc_balance(self, assignments) -> float:
    """TODO: 实现均衡度计算 = 1 - 方差/均值"""

def calc_efficiency(self, assignments) -> float:
    """TODO: 实现效率评分 = 基于等待时间"""
```

#### 3. Demo 兜底逻辑
```python
# 位置: optimizer_agent.py
# 建议: 为演示准备固定最优解

if scenario == 'demo':
    return self._get_fixed_best_plan()
```

### 测试命令
```bash
python -c "
from agents import MasterAgent
m = MasterAgent()
solutions = m.schedule(['JOB001', 'JOB002'])
print(f'生成了 {len(solutions)} 个方案')
"
```

---

## 🧑‍💻 成员 B：ComplianceAgent + ExplainerAgent

**负责文件**:
- `agents/compliance_agent.py`
- `agents/explainer_agent.py`

### 核心任务

#### 1. 向量数据库搭建
```python
# 位置: compliance_agent.py 第 25 行
# 推荐使用 ChromaDB

# 安装
pip install chromadb

# 初始化
import chromadb
self.vector_db = chromadb.Client()
self.collection = self.vector_db.create_collection("rules")

# 导入规则
for rule in self.rules:
    self.collection.add(
        documents=[rule.description],
        metadatas=[{"id": rule.id, "severity": rule.severity}],
        ids=[rule.id]
    )
```

#### 2. 规则检索 (`check_compliance`)
```python
# 位置: compliance_agent.py 第 40 行

def check_compliance(self, tug_id, job_id):
    """
    TODO: 
    1. 获取拖轮和任务信息
    2. 构建查询文本
    3. 向量检索相关规则
    4. 逐条检查是否违反
    """
    # 示例: 向量检索
    results = self.collection.query(
        query_texts=[f"{tug.name} {job.job_type}"],
        n_results=5
    )
```

#### 3. LLM 接口配置
```python
# 位置: explainer_agent.py

# 在 config.py 或 .env 中配置
LLM_API_KEY=your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com

# Prompt 模板设计
EXPLAIN_PROMPT = """
你是港口调度解释助手。根据以下信息生成简洁解释：
方案: {solution}
要求: 说明选择原因，提及成本和效率因素
"""
```

#### 4. 反事实推演预设
```python
# 位置: explainer_agent.py
# 为常见问题准备固定回答

FIXED_ANSWERS = {
    "亚洲2号": "亚洲2号当前疲劳值较高(9.2)，且与亚洲1号存在名称混淆风险，故未被选中。",
    "老港拖1": "老港拖1船龄超过20年，根据R002规则不得执行高危作业。"
}
```

### 测试命令
```bash
python -c "
from agents import ComplianceAgent
c = ComplianceAgent()
result = c.check_compliance('TUG012', 'JOB003')
print(f'合规检查: {result.is_compliant}, 原因: {result.violation_reason}')
"
```

---

## 🧑‍💻 成员 C：PerceptionAgent + FatigueAgent

**负责文件**:
- `agents/perception_agent.py`
- `agents/fatigue_agent.py`

### 核心任务

#### 1. 泊位堆栈逻辑
```python
# 位置: perception_agent.py

class BerthStack:
    """
    泊位只能后进先出
    TODO: 实现以下方法
    """
    def __init__(self, berth_id: str, tugs: List[str]):
        self.berth_id = berth_id
        self.stack = tugs  # 最后一个是外档
    
    def can_dispatch(self, tug_id: str) -> bool:
        """能否直接出动 tug_id"""
        return self.stack and self.stack[-1] == tug_id
    
    def get_blocking_tugs(self, tug_id: str) -> List[str]:
        """获取阻挡 tug_id 的船只列表"""
        if tug_id not in self.stack:
            return []
        idx = self.stack.index(tug_id)
        return self.stack[idx+1:]  # 它后面的都要先移走
```

#### 2. 隐性任务生成
```python
# 位置: perception_agent.py

def get_hidden_tasks(self) -> List[str]:
    """
    TODO: 生成隐性任务
    - 辅助带缆
    - 航道清理
    - 移泊任务
    """
    hidden = []
    # 示例: 为内档船生成移泊任务
    for berth in self.berths.values():
        if len(berth.tugs_stack) > 1:
            for inner_tug in berth.tugs_stack[:-1]:
                hidden.append(f"SHIFT_{inner_tug}")
    return hidden
```

#### 3. 疲劳模型 BFM
```python
# 位置: fatigue_agent.py 第 70 行

def update_fatigue(self, tug_id, work_hours, is_night=False):
    """
    TODO: 完善疲劳计算模型
    
    建议公式:
    新疲劳 = 当前值 + 白天工时×1.0 + 夜间工时×1.5
    
    高级功能:
    - 连续工作惩罚 (连续>4小时额外+1)
    - 休息恢复 (每小时休息-0.5)
    """
```

### 数据准备

成员 C 需要准备以下数据:

| 数据 | 文件 | 说明 |
|------|------|------|
| 拖轮初始疲劳 | `data/tugs.json` | 调整 `fatigue_value` 字段 |
| 泊位坐标 | `data/berths.json` | 真实的青岛港坐标 |
| 演示场景 | `data/demo_scenario.json` | 构造冲突场景 |

### 测试命令
```bash
python -c "
from agents import FatigueAgent
f = FatigueAgent()
locked = f.get_locked_tugs()
print(f'被锁定的拖轮: {locked}')
"
```

---

## 🧑‍💻 成员 D：前端开发

**负责文件**:
- `frontend/index.html`
- `frontend/style.css`
- `frontend/main.js`

### 核心任务

#### 1. GIS 地图
```javascript
// 位置: main.js

// 当前已实现基础地图
// TODO: 增强功能

// 点击泊位显示堆栈
marker.on('click', () => {
    showBerthStack(berth.id, berth.tugs_stack);
});

// 连活连线动画
function drawChainLine(job1, job2) {
    L.polyline([
        [job1.lat, job1.lng],
        [job2.lat, job2.lng]
    ], {
        color: 'gold',
        dashArray: '10, 10',
        weight: 3
    }).addTo(map);
}
```

#### 2. 方案采纳动画
```javascript
// 位置: main.js

function adoptSolution(solutionId) {
    // TODO: 
    // 1. 高亮被选中的拖轮
    // 2. 画出拖轮到任务的连线
    // 3. 如果有连活，显示金色虚线
    // 4. 显示节省成本浮动标签
}
```

#### 3. 违规弹窗特效
```javascript
// 位置: main.js

function showViolationAlert(tug, reason) {
    // TODO: 红色震动特效
    const popup = L.popup()
        .setLatLng([tug.lat, tug.lng])
        .setContent(`⚠️ ${reason}`)
        .openOn(map);
    
    // 添加震动动画
    popup.getElement().classList.add('shake');
}
```

### 测试方法
```bash
# 启动后端
python main.py

# 浏览器访问
http://localhost:8000
```

---

## 📊 还需要的数据

| 数据 | 负责人 | 说明 |
|------|--------|------|
| 青岛港真实泊位坐标 | 成员C | 当前使用模拟坐标 |
| 更多业务规则 | 成员B | 当前只有10条示例 |
| 拖轮真实参数 | 成员C | 马力、船龄等 |
| 历史调度数据 | 全员 | 用于验证算法效果 |
| LLM API Key | 成员B | DeepSeek 或 OpenAI |
| 演示场景数据 | 成员C | 构造连活、冲突场景 |

---

## 🔄 Git 工作流

```bash
# 每个人在自己的分支开发
git checkout -b feature/agent1  # 成员C
git checkout -b feature/agent2  # 成员B
git checkout -b feature/frontend  # 成员D

# 提交代码
git add .
git commit -m "feat: 实现疲劳计算模型"
git push origin feature/agent1

# 发起 Pull Request 合并到 main
```

---

## ❓ 常见问题

**Q: 如何测试单个 Agent?**
```bash
python -c "from agents import YourAgent; a = YourAgent(); print(a.health_check())"
```

**Q: 如何查看 API 文档?**
启动服务后访问 http://localhost:8000/docs

**Q: LLM 没配置怎么办?**
Agent5 会自动降级使用模板回复，不影响 Demo
