# 建筑能源智能管理系统

**Building Energy Intelligent Management System (BEIMS)**

基于 Python FastAPI + SQLite + ECharts 的建筑能源智能管理与运营优化平台，面向"双碳"目标，集能耗数据管理、多维统计分析、智慧运维问答于一体。

---

## 系统功能

### 1. 数据层
- 支持CSV文件导入，标准化数据接入
- SQLite数据库存储，支持扩展至PostgreSQL

### 2. 查询统计模块（MCP协议风格）
- **多条件精准查询**：支持按建筑编号、建筑类型、时间范围、设备状态等联合查询
- **时段汇总分析**：按月/天/小时/建筑分组统计电耗、水耗、空调能耗
- **COP能效分析**：计算并评估空调系统能效比，展示月度变化趋势
- **异常数据分析**：统计各建筑异常记录、异常率、异常原因分布
- **可视化图表**：ECharts柱状图、折线图、饼图等多种图表展示
- **报表导出**：一键导出查询结果为CSV文件

### 3. 智慧运维模块
- **领域知识库**：集成能耗数据字典和设备运维手册
- **智能问答（RAG风格）**：响应能耗查询、COP分析、异常诊断等问题
- **快捷问题模板**：常见运维问题一键提问
- **数据上下文感知**：问答结合实时数据库数据给出精准答复

### 4. Web系统
- 仪表盘：KPI总览 + 建筑能耗分布饼图 + 近期趋势折线图
- 数据管理：CSV上传导入、数据集统计
- 数据查询：多条件查询表格 + 分页 + 导出
- 统计分析：三类分析各有独立图表和数据表
- 智慧运维：聊天界面 + 快捷问题侧边栏


---

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3.8+, FastAPI, SQLAlchemy |
| 数据库 | SQLite（可换PostgreSQL） |
| 前端 | HTML5, Vanilla JS, ECharts 5 |
| 数据 | CSV, Pandas |
| 知识库 | 基于规则的RAG风格检索 |

---

## 快速开始

## 用户文档

- 用户使用手册：`docs/user-manual.md`

### 前置条件
- Python 3.8+
- pip

### 一键启动

```bash
# 克隆仓库后执行
bash start.sh
```

启动脚本将自动：
1. 安装Python依赖
2. （可选）构建Vue前端
3. 启动Web服务（端口8000）

首次使用请进入“数据管理”页面，手动上传CSV数据文件（如 `data/energy_data.csv`）。

### 手动启动

```bash
# 1. 安装依赖
pip install -r backend/requirements.txt

# 2. 启动后端
cd backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 访问系统

| 地址 | 说明 |
|------|------|
| http://localhost:8000 | Web管理界面 |
| http://localhost:8000/docs | Swagger API文档 |
| http://localhost:8000/health | 健康检查 |

---

## 项目结构

```
.
├── data/
│   ├── generate_dataset.py     # 数据集生成脚本
│   ├── energy_data.csv         # 生成的能耗数据集
│   └── data_dictionary.md      # 数据字典说明
├── backend/
│   ├── app.py                  # FastAPI主应用
│   ├── models.py               # 数据库模型
│   ├── database.py             # 数据库配置
│   ├── requirements.txt        # Python依赖
│   ├── routers/
│   │   ├── data.py             # 数据导入路由
│   │   ├── query.py            # 查询路由（MCP协议风格）
│   │   ├── statistics.py       # 统计分析路由
│   │   └── chat.py             # 智慧运维问答路由
│   └── knowledge_base/
│       ├── energy_dictionary.txt   # 能耗数据字典
│       └── equipment_manual.txt    # 设备运维手册
├── frontend/
│   ├── index.html              # 前端主页
│   ├── css/style.css           # 全局样式
│   └── js/app.js               # 前端逻辑
├── start.sh                    # 一键启动脚本
└── README.md
```

---

## API接口说明

### 数据管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/data/import | 上传并导入CSV数据 |
| GET | /api/data/stats | 数据集统计信息 |
| DELETE | /api/data/clear | 清空数据库 |

### 查询接口（MCP协议风格）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/query/records | 多条件查询（支持分页） |
| GET | /api/query/export | 导出查询结果CSV |

**查询参数**：`building_id`, `building_type`, `start_time`, `end_time`, `year`, `month`, `device_status`, `anomaly_only`, `min_power`, `max_power`, `page`, `page_size`

### 统计分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/stats/period_summary | 时段能耗汇总 |
| GET | /api/stats/cop_analysis | COP能效分析 |
| GET | /api/stats/anomaly_analysis | 异常数据分析 |
| GET | /api/stats/overview | 系统总览数据 |

### 智慧运维
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat/ask | 运维问答 |
| GET | /api/chat/suggestions | 快捷问题列表 |

---

## 数据集说明

见 [data/data_dictionary.md](data/data_dictionary.md)

**核心字段**：
- 基础信息：建筑编号/名称/类型、监测时间
- 能耗数据：电力能耗(kWh)、水耗(m³)、空调能耗(kWh)
- 空调参数：出水温度、回水温度、COP值
- 环境数据：温度(°C)、湿度(%RH)、人员密度
- 设备状态：设备编号、运行状态、异常标志

---

## 常见问题

**Q: 启动后访问页面显示空数据？**  
A: 需要先导入数据。访问"数据管理"页面上传 `data/energy_data.csv`。

**Q: 如何使用自定义数据？**  
A: 按照 `data/data_dictionary.md` 中的字段格式准备CSV文件，通过"数据管理"页面上传即可。

**Q: 如何升级为真实LLM？**  
A: 修改 `backend/routers/chat.py` 中的 `generate_answer` 函数，替换为调用OpenAI/本地LLM的API即可。

---

## 项目背景

本项目为中国大学生服务外包创新创业大赛 A08 赛题实现方案，围绕"建筑能源智能管理与运营优化关键技术研究"主题，基于人工智能大模型技术和数据分析方法，构建集查询统计与智慧运维于一体的建筑能源智能管理系统。
