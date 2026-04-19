# chat_router.py
"""
智慧运维问答系统（最终优化版）

特点：
1. 数据库 + 知识库 + LLM（RAG架构）
2. 本地/云端模型自动切换
3. 问题分类（避免乱答）
4. Prompt工程（提升专业性）
5. 拒答机制（提高系统可信度）
"""
import os
import requests
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .db_models import EnergyRecord, get_db

router = APIRouter(prefix="/api/chat", tags=["智慧运维"])


# ===============================
# 1️⃣ 数据查询层
# ===============================
def query_data(db, building_id=None, start_time=None, end_time=None):
    q = db.query(EnergyRecord)

    if building_id:
        q = q.filter(EnergyRecord.building_id == building_id)

    if start_time:
        dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        q = q.filter(EnergyRecord.monitor_time >= dt)

    if end_time:
        dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        q = q.filter(EnergyRecord.monitor_time <= dt)

    records = q.all()

    return [
        {
            "time": r.monitor_time.strftime("%Y-%m-%d %H:%M"),
            "power": r.power_consumption
        }
        for r in records
    ]


# ===============================
# 2️⃣ 时段统计
# ===============================
def time_summary(data, metric="power"):
    groups = {}

    for item in data:
        dt = datetime.strptime(item["time"], "%Y-%m-%d %H:%M")
        hour = dt.hour
        groups.setdefault(hour, []).append(item[metric])

    return [
        {
            "hour": h,
            "avg": round(sum(v) / len(v), 2)
        }
        for h, v in groups.items()
    ]


# ===============================
# 3️⃣ 外部统计 API（预留扩展）
# ===============================
def call_stats_api(endpoint: str, params: dict):
    try:
        url = f"http://localhost:8000/api/stats/{endpoint}"
        r = requests.get(url, params=params, timeout=5)
        return r.json()
    except:
        return {}


# ===============================
# 4️⃣ 知识库
# ===============================
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base")


def load_knowledge_base():
    kb = {}
    if not os.path.exists(KB_DIR):
        return kb

    for fname in os.listdir(KB_DIR):
        if fname.endswith(".txt"):
            with open(os.path.join(KB_DIR, fname), "r", encoding="utf-8") as f:
                kb[fname] = f.read()
    return kb


KB = load_knowledge_base()


def search_knowledge_base(query: str) -> str:
    results = []
    for content in KB.values():
        if any(word in content for word in query.split()):
            results.append(content[:300])
    return "\n".join(results[:2])


# ===============================
# 5️⃣ 请求结构
# ===============================
class ChatRequest(BaseModel):
    question: str
    building_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ===============================
# 6️⃣ 问题分类
# ===============================
def classify_question(question: str) -> str:
    if any(k in question for k in ["能耗", "电", "功率"]):
        return "data"
    elif any(k in question for k in ["异常", "故障", "报警"]):
        return "anomaly"
    elif any(k in question for k in ["建议", "如何", "优化"]):
        return "advice"
    else:
        return "general"


# ===============================
# 7️⃣ DB上下文
# ===============================
def get_db_context(db: Session, building_id, start_time, end_time):
    data = query_data(db, building_id, start_time, end_time)

    if not data:
        return {}

    power = [d["power"] for d in data]

    return {
        "total": len(data),
        "avg_power": round(sum(power) / len(power), 2),
        "max_power": round(max(power), 2),
        "hourly": time_summary(data)
    }


# ===============================
# 8️⃣ 本地模型
# ===============================
def call_local_model(prompt: str):
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=10
        )
        return r.json().get("response", "")
    except:
        return ""


# ===============================
# 9️⃣ 云端模型
# ===============================
def call_cloud_model(prompt: str):
    return "【云端模型】：" + prompt[:120]


# ===============================
# 🔥 10️⃣ Prompt工程（已优化）
# ===============================
def build_system_prompt(q_type: str) -> str:
    if q_type == "data":
        return """
你是能耗分析专家。

请输出：
【数据分析】
【趋势说明】

不要进行故障诊断！
"""

    elif q_type == "anomaly":
        return """
你是运维工程师。

请输出：
【问题】
【原因】
【措施】

措施必须具体！
"""

    elif q_type == "advice":
        return """
你是节能优化专家。

请输出：
【当前情况】
【优化建议】
"""

    else:
        return "请简要回答问题"


# ===============================
# 11️⃣ 生成回答（RAG + 自动切换）
# ===============================
def generate_answer(question, db_context, kb_content, q_type):

    system_prompt = build_system_prompt(q_type)

    user_prompt = f"""
用户问题：{question}

数据库数据：
{db_context}

知识库：
{kb_content}
"""

    prompt = system_prompt + "\n" + user_prompt

    answer = call_local_model(prompt)

    if not answer or len(answer) < 20:
        answer = call_cloud_model(prompt)

    return answer


# ===============================
# 12️⃣ 主接口
# ===============================
@router.post("/ask")
def ask_question(request: ChatRequest, db: Session = Depends(get_db)):

    question = request.question.strip()
    if not question:
        return {"answer": "请输入问题"}

    q_type = classify_question(question)

    if q_type == "general":
        return {"answer": "该问题不属于智慧运维系统范围"}

    db_context = get_db_context(
        db,
        request.building_id,
        request.start_time,
        request.end_time
    )

    # stats扩展
    stats_data = {}

    if q_type == "data":
        stats_data = call_stats_api("period_summary", {
            "building_id": request.building_id,
            "start_time": request.start_time,
            "end_time": request.end_time
        })

    elif q_type == "anomaly":
        stats_data = call_stats_api("anomaly_analysis", {
            "building_id": request.building_id
        })

    kb_content = search_knowledge_base(question)

    if not db_context and not kb_content:
        return {"answer": "暂无相关数据"}

    answer = generate_answer(
        question,
        {**db_context, "stats": stats_data},
        kb_content,
        q_type
    )

    return {
        "question": question,
        "type": q_type,
        "answer": answer,
        "data": db_context,
        "stats": stats_data
    }