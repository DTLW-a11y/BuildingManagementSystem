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
import re
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from pydantic import BaseModel

from database import get_db
from models import EnergyRecord

router = APIRouter(prefix="/api/chat", tags=["智慧运维"])
logger = logging.getLogger(__name__)
CHAT_ROUTER_VERSION = "2026-04-18-rule-ai-split"
MAX_ANSWER_LENGTH = 800


def parse_datetime_safe(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    text = str(value).strip()

    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def safe_avg(values: List[Optional[float]], digits: int = 2) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), digits)


def fmt_number(value: Optional[float], unit: str = "") -> str:
    if value is None:
        return "暂无"
    return f"{value}{unit}"


# ===============================
# 1️⃣ 数据查询层
# ===============================
def query_data(db, building_id=None, start_time=None, end_time=None):
    q = db.query(EnergyRecord).order_by(EnergyRecord.monitor_time.asc())

    if building_id:
        q = q.filter(EnergyRecord.building_id == building_id)

    start_dt = parse_datetime_safe(start_time)
    if start_dt:
        dt = start_dt
        q = q.filter(EnergyRecord.monitor_time >= dt)

    end_dt = parse_datetime_safe(end_time)
    if end_dt:
        dt = end_dt
        q = q.filter(EnergyRecord.monitor_time <= dt)

    records = q.all()

    return [
        {
            "building_id": r.building_id,
            "building_name": r.building_name,
            "time": r.monitor_time.strftime("%Y-%m-%d %H:%M"),
            "power": r.power_consumption,
            "water": r.water_consumption,
            "ac_power": r.ac_power_consumption,
            "cop": r.cop,
            "env_temp": r.env_temperature,
            "device_status": r.device_status,
            "anomaly_flag": r.anomaly_flag,
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
        value = item.get(metric)
        if value is None:
            continue
        groups.setdefault(hour, []).append(value)

    return [
        {
            "hour": h,
            "avg": round(sum(v) / len(v), 2)
        }
        for h, v in sorted(groups.items(), key=lambda x: x[0])
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
    """知识库检索（关键词 + 上下文片段）。"""
    query_lower = query.lower()
    results = []

    keywords_map = {
        "cop": ["cop", "能效比", "能效"],
        "anomaly": ["异常", "故障", "报警", "告警"],
        "ac": ["空调", "制冷", "制热", "冷水机", "冷却"],
        "power": ["电力", "用电", "能耗", "电耗", "功率"],
        "water": ["水耗", "用水", "水量"],
        "maintenance": ["维护", "保养", "维修", "检修", "维保"],
        "temperature": ["温度", "出水", "回水", "供水"],
        "save_energy": ["节能", "省电", "节约", "优化"],
    }

    matched_topics = set()
    for topic, kws in keywords_map.items():
        if any(kw in query for kw in kws):
            matched_topics.add(topic)

    query_tokens = [w for w in re.split(r"[\s,，。！？；:：/]+", query_lower) if len(w) >= 2]

    for fname, content in KB.items():
        lines = content.split("\n")
        relevant_lines = []

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(token in line_lower for token in query_tokens):
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                relevant_lines.extend(lines[start:end])

        if not relevant_lines and matched_topics:
            for i, line in enumerate(lines):
                if any(kw in line for topic in matched_topics for kw in keywords_map[topic]):
                    start = max(0, i - 1)
                    end = min(len(lines), i + 3)
                    relevant_lines.extend(lines[start:end])

        if relevant_lines:
            # 去重并限制长度
            deduped = []
            seen = set()
            for line in relevant_lines:
                text = line.strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                deduped.append(text)
                if len(deduped) >= 20:
                    break

            if deduped:
                results.append("\n".join(deduped))

    return "\n\n".join(results[:3]) if results else ""


# ===============================
# 5️⃣ 请求结构
# ===============================
class ChatRequest(BaseModel):
    question: str
    building_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    query_mode: Optional[str] = "ai"


# ===============================
# 6️⃣ 问题分类
# ===============================
ANOMALY_KEYWORDS = [
    "异常", "故障", "报警", "告警", "诊断", "排查", "风险", "偏高", "偏低", "波动", "突增", "超标", "失稳"
]
ADVICE_KEYWORDS = [
    "建议", "如何", "怎么", "怎样", "优化", "措施", "改进", "节能", "方案", "降低", "提升", "策略"
]
DATA_KEYWORDS = [
    "能耗", "电耗", "水耗", "功率", "负荷", "统计", "趋势", "查询", "报表", "同比", "环比", "记录", "数据", "曲线", "峰值"
]
BUILDING_KEYWORDS = [
    "建筑", "楼", "楼栋", "楼宇", "机房", "机组", "设备", "园区", "站点", "空调"
]
BUILDING_PATTERNS = [
    r"\d+\s*号楼",
    r"[A-Za-z]\d{1,3}\s*(?:号楼|栋|楼)?",
    r"(?:building|tower)\s*[a-z0-9-]+",
]


def has_any_keyword(text: str, keywords: List[str]) -> bool:
    lower_text = text.lower()
    return any(k.lower() in lower_text for k in keywords)


def contains_building_context(question: str) -> bool:
    if has_any_keyword(question, BUILDING_KEYWORDS):
        return True
    return any(re.search(p, question, re.IGNORECASE) for p in BUILDING_PATTERNS)


def is_domain_related(question: str) -> bool:
    domain_extra = ["cop", "温度", "湿度", "设备状态", "制冷", "空调", "运维", "能效"]
    return (
        has_any_keyword(question, ANOMALY_KEYWORDS)
        or has_any_keyword(question, ADVICE_KEYWORDS)
        or has_any_keyword(question, DATA_KEYWORDS)
        or contains_building_context(question)
        or has_any_keyword(question, domain_extra)
    )


def classify_question(question: str) -> str:
    if has_any_keyword(question, ANOMALY_KEYWORDS):
        return "anomaly"
    elif has_any_keyword(question, ADVICE_KEYWORDS):
        return "advice"
    elif has_any_keyword(question, DATA_KEYWORDS):
        return "data"
    elif contains_building_context(question):
        return "data"
    else:
        return "general"


# ===============================
# 7️⃣ DB上下文
# ===============================
def get_db_context(db: Session, building_id, start_time, end_time):
    data = query_data(db, building_id, start_time, end_time)

    if not data:
        return {}

    power = [d.get("power") for d in data]
    water = [d.get("water") for d in data]
    ac_power = [d.get("ac_power") for d in data]
    cop = [d.get("cop") for d in data]
    env_temp = [d.get("env_temp") for d in data]
    anomaly_count = sum(1 for d in data if int(d.get("anomaly_flag") or 0) == 1)

    device_dist: Dict[str, int] = {}
    for item in data:
        status = str(item.get("device_status") or "未知")
        device_dist[status] = device_dist.get(status, 0) + 1

    max_power = round(max([p for p in power if p is not None]), 2) if any(p is not None for p in power) else None
    peak_record = max(data, key=lambda x: x.get("power") if x.get("power") is not None else float("-inf"))
    building_name = next((d.get("building_name") for d in data if d.get("building_name")), "")
    building_id_from_data = next((d.get("building_id") for d in data if d.get("building_id")), building_id)

    return {
        "total": len(data),
        "building_id": building_id_from_data,
        "building_name": building_name,
        "time_range": {
            "start": data[0].get("time"),
            "end": data[-1].get("time"),
        },
        "avg_power": safe_avg(power),
        "max_power": max_power,
        "avg_water": safe_avg(water),
        "avg_ac_power": safe_avg(ac_power),
        "avg_cop": safe_avg(cop),
        "avg_env_temp": safe_avg(env_temp),
        "anomaly_count": anomaly_count,
        "anomaly_rate": round(anomaly_count / len(data) * 100, 2),
        "device_status_dist": device_dist,
        "peak_record": {
            "time": peak_record.get("time"),
            "power": peak_record.get("power"),
            "cop": peak_record.get("cop"),
            "device_status": peak_record.get("device_status"),
        },
        "hourly": time_summary(data),
    }


def parse_building_ids(building_id: Optional[str]) -> List[str]:
    if not building_id:
        return []
    return [b.strip() for b in str(building_id).split(",") if b.strip()]


def get_rule_db_context(
    db: Session,
    building_id: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
) -> Dict[str, Any]:
    """规则问答的数据库上下文（聚合统计）。"""
    q = db.query(EnergyRecord)
    filters = []

    ids = parse_building_ids(building_id)
    if ids:
        filters.append(EnergyRecord.building_id.in_(ids))

    start_dt = parse_datetime_safe(start_time)
    if start_dt:
        filters.append(EnergyRecord.monitor_time >= start_dt)

    end_dt = parse_datetime_safe(end_time)
    if end_dt:
        filters.append(EnergyRecord.monitor_time <= end_dt)

    if filters:
        q = q.filter(and_(*filters))

    total = q.count()
    if total == 0:
        return {
            "total": 0,
            "recent_anomalies": [],
        }

    avg_power = q.with_entities(func.avg(EnergyRecord.power_consumption)).scalar() or 0
    max_power = q.with_entities(func.max(EnergyRecord.power_consumption)).scalar() or 0
    min_power = q.with_entities(func.min(EnergyRecord.power_consumption)).scalar() or 0
    total_power = q.with_entities(func.sum(EnergyRecord.power_consumption)).scalar() or 0
    avg_cop = (
        q.with_entities(func.avg(EnergyRecord.cop))
        .filter(EnergyRecord.ac_power_consumption > 0)
        .scalar()
        or 0
    )
    anomaly_count = q.filter(EnergyRecord.anomaly_flag == 1).count()

    recent_anomalies = (
        q.filter(EnergyRecord.anomaly_flag == 1)
        .order_by(desc(EnergyRecord.monitor_time))
        .limit(5)
        .all()
    )

    return {
        "total": total,
        "avg_power": round(avg_power, 2),
        "max_power": round(max_power, 2),
        "min_power": round(min_power, 2),
        "total_power": round(total_power, 2),
        "avg_cop": round(avg_cop, 3),
        "anomaly_count": anomaly_count,
        "anomaly_rate": round(anomaly_count / total * 100, 2) if total > 0 else 0,
        "recent_anomalies": [
            {
                "time": str(r.monitor_time),
                "building": r.building_name,
                "power": r.power_consumption,
                "reason": r.anomaly_reason,
            }
            for r in recent_anomalies
        ],
    }


def generate_rule_answer(question: str, db_context: Dict[str, Any], kb_content: str) -> str:
    """规则问答回复：用于快捷问题，不走模型调用。"""
    q = question.strip()
    total = db_context.get("total", 0)

    if any(kw in q for kw in ["能耗", "用电量", "电力", "电耗"]):
        if total == 0:
            return "当前查询条件下无数据，请调整查询范围。"

        answer = "**能耗统计分析结果**\n\n"
        answer += f"📊 查询记录数：{total} 条\n"
        answer += f"⚡ 总电力能耗：{db_context.get('total_power', 0)} kWh\n"
        answer += f"📈 平均小时能耗：{db_context.get('avg_power', 0)} kWh\n"
        answer += f"🔺 最高小时能耗：{db_context.get('max_power', 0)} kWh\n"
        answer += f"🔻 最低小时能耗：{db_context.get('min_power', 0)} kWh\n"
        answer += (
            f"⚠️ 异常记录：{db_context.get('anomaly_count', 0)} 条"
            f"（{db_context.get('anomaly_rate', 0)}%）\n"
        )

        if db_context.get("anomaly_rate", 0) > 10:
            answer += f"\n⚠️ **注意**：异常率较高（{db_context.get('anomaly_rate', 0)}%），建议立即排查原因。"
        elif db_context.get("avg_power", 0) > 100:
            answer += "\n💡 **节能建议**：平均能耗偏高，建议检查空调设定温度和非工作时段设备管理。"

        return answer

    elif any(kw in q for kw in ["cop", "COP", "能效比", "能效"]):
        if total == 0:
            return "当前查询条件下无数据。"

        avg_cop = db_context.get("avg_cop", 0)
        if avg_cop >= 3.5:
            rating = "优秀 ✅"
            advice = "空调系统能效表现优秀，继续保持。"
        elif avg_cop >= 3.0:
            rating = "良好 ✅"
            advice = "空调系统能效良好，可进一步优化冷凝器清洁度。"
        elif avg_cop >= 2.5:
            rating = "一般 ⚠️"
            advice = "空调系统能效一般，建议检查冷媒量、清洗冷凝器翅片。"
        else:
            rating = "较差 ❌"
            advice = "空调系统能效较差，建议立即检修，可能存在冷媒泄漏或设备老化。"

        return (
            "**COP能效分析**\n\n"
            f"📊 查询范围内平均COP：**{avg_cop}**\n"
            f"📋 能效评级：{rating}\n\n"
            f"💡 **建议**：{advice}\n\n"
            "📌 **参考标准**：\n"
            "- 优秀：COP ≥ 3.5\n"
            "- 良好：3.0 ≤ COP < 3.5\n"
            "- 一般：2.5 ≤ COP < 3.0\n"
            "- 较差：COP < 2.5"
        )

    elif any(kw in q for kw in ["异常", "故障", "报警", "能耗异常", "异常原因"]):
        if total == 0:
            return "当前查询条件下无数据。"

        anomaly_count = db_context.get("anomaly_count", 0)
        if anomaly_count == 0:
            return "✅ 当前查询范围内未发现能耗异常记录，系统运行正常。"

        answer = "**能耗异常分析报告**\n\n"
        answer += (
            f"⚠️ 发现 **{anomaly_count}** 条异常记录"
            f"（异常率 {db_context.get('anomaly_rate', 0)}%）\n\n"
        )

        recent_anomalies = db_context.get("recent_anomalies") or []
        if recent_anomalies:
            answer += "**最近异常记录：**\n"
            for a in recent_anomalies[:3]:
                answer += (
                    f"- {a.get('time')} | {a.get('building')} | "
                    f"能耗：{a.get('power')} kWh | 原因：{a.get('reason') or '未知'}\n"
                )

        answer += "\n**可能原因及处理建议：**\n"

        if kb_content:
            lines = kb_content.split("\n")
            for line in lines:
                if any(kw in line for kw in ["原因", "处理", "建议", "步骤"]):
                    answer += f"- {line.strip()}\n"
                    if len(answer) > MAX_ANSWER_LENGTH:
                        break

        if len(answer) < 300:
            answer += (
                "1. **能耗异常偏高**：检查大功率设备是否同时开启，排查设备故障\n"
                "2. **深夜用电异常**：确认是否有未关闭的设备，检查楼控系统\n"
                "3. **超额用电**：排查是否有违规接入大功率设备\n\n"
                "**处理流程**：发现异常 → 现场确认 → 定位设备 → 停机检修 → 恢复运行 → 记录归档"
            )

        return answer

    elif any(kw in q for kw in ["设备", "运行状态", "空调", "冷水机", "水泵"]):
        if total == 0:
            return "当前查询条件下无设备数据。"

        normal_count = total - db_context.get("anomaly_count", 0)
        answer = "**设备运行状态查询**\n\n"
        answer += f"📊 监测记录总数：{total}\n"
        answer += f"✅ 正常记录：{normal_count} 条\n"
        answer += f"❌ 异常记录：{db_context.get('anomaly_count', 0)} 条\n\n"

        if kb_content:
            answer += "**运维知识参考：**\n"
            relevant = [l for l in kb_content.split("\n") if l.strip() and len(l) > 10][:5]
            for line in relevant:
                answer += f"{line}\n"

        return answer

    elif any(kw in q for kw in ["水耗", "用水", "水量"]):
        if total == 0:
            return "当前查询条件下无数据。"
        return (
            "**水耗统计**\n\n"
            f"📊 查询记录数：{total} 条\n"
            "💧 该时段用水情况请参考统计分析模块的详细报表。\n\n"
            "💡 **节水建议**：检查冷却塔补水、卫生间漏水情况，推广节水器具。"
        )

    elif any(kw in q for kw in ["节能", "省电", "节约", "优化"]):
        return (
            "**节能优化建议**\n\n"
            "🌡️ **空调节能**：\n"
            "- 夏季室内设定温度不低于26°C，冬季不高于20°C\n"
            "- 定期清洗过滤网，保持COP≥3.0\n"
            "- 实施分时分区控制，减少非使用区域运行\n\n"
            "💡 **照明节能**：\n"
            "- 安装人体感应控制，无人自动关闭\n"
            "- 推广LED灯具替换\n\n"
            "🖥️ **设备节能**：\n"
            "- 设置办公设备自动休眠策略\n"
            "- 非工作时段断电管理\n\n"
            "📊 **数据驱动节能**：\n"
            "- 定期分析能耗趋势，识别高能耗时段\n"
            "- 对比同类建筑基准，找出节能空间"
        )

    elif any(kw in q for kw in ["维护", "保养", "维修", "检修", "维保"]):
        if kb_content:
            lines = kb_content.split("\n")
            relevant = []
            capture = False
            for line in lines:
                if "维护" in line or "保养" in line or "检修" in line:
                    capture = True
                if capture:
                    relevant.append(line)
                    if len(relevant) > 20:
                        break
            if relevant:
                return "**设备维护保养指南**\n\n" + "\n".join(relevant[:15])

        return (
            "**设备维护保养计划**\n\n"
            "📅 **每周**：检查运行参数，清理设备表面\n"
            "📅 **每月**：清洗过滤网，检查冷却水水质\n"
            "📅 **每季度**：校验传感器，清洗冷凝器\n"
            "📅 **每年**：系统大修，更换易损件，冷媒检测\n\n"
            "💡 建议建立维保记录台账，规范化管理。"
        )

    else:
        if kb_content:
            return (
                "**智能运维助手回复**\n\n"
                "根据知识库检索，以下是与您问题相关的信息：\n\n"
                f"{kb_content[:500]}...\n\n"
                "如需进一步了解，请提供更具体的问题，例如：\n"
                "- '查询B001教学楼本月能耗'\n"
                "- '分析系统COP值'\n"
                "- '查看近期能耗异常记录'\n"
                "- '提供节能建议'"
            )

        return (
            "您好！我是建筑能源智能运维助手。\n\n"
            "我可以帮您：\n"
            "- 📊 查询建筑能耗数据统计\n"
            "- 🔍 分析能耗异常原因\n"
            "- ⚡ 计算空调系统COP能效\n"
            "- 🔧 提供设备维护建议\n"
            "- 💡 给出节能优化建议\n\n"
            "请输入您的具体问题，例如：'查询教学楼本月能耗情况'"
        )


def run_rule_query(request: ChatRequest, db: Session) -> Dict[str, Any]:
    question = request.question.strip()
    db_context = get_rule_db_context(
        db,
        request.building_id,
        request.start_time,
        request.end_time,
    )
    kb_content = search_knowledge_base(question)
    answer = generate_rule_answer(question, db_context, kb_content)

    return {
        "question": question,
        "mode": "rule",
        "router_version": CHAT_ROUTER_VERSION,
        "answer": answer,
        "data_context": {
            "building_id": request.building_id,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "records_queried": db_context.get("total", 0),
        },
        "sources": list(KB.keys()),
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
FOCUS_RULES = [
    ("电力负荷", ["能耗", "电", "功率", "负荷", "峰值", "电耗"]),
    ("水系统", ["水耗", "用水", "水量", "水表"]),
    ("空调系统", ["空调", "冷机", "制冷", "冷冻水", "冷却"]),
    ("COP效率", ["cop", "能效", "效率"]),
    ("环境参数", ["温度", "湿度", "环境"]),
    ("设备状态", ["设备", "机组", "故障", "告警", "报警", "异常"]),
]


def detect_focus_items(question: str) -> List[str]:
    lower_question = question.lower()
    focus = []
    for label, keys in FOCUS_RULES:
        if any(k.lower() in lower_question for k in keys):
            focus.append(label)
    if not focus:
        if contains_building_context(question):
            return ["建筑总体运行"]
        return ["总体能耗"]
    return focus


def format_scope_text(db_context: Dict[str, Any]) -> str:
    name = db_context.get("building_name")
    bid = db_context.get("building_id")
    time_range = db_context.get("time_range") or {}

    target = ""
    if name and bid:
        target = f"对象：{name}（{bid}）"
    elif name:
        target = f"对象：{name}"
    elif bid:
        target = f"对象：{bid}"

    window = ""
    if time_range.get("start") and time_range.get("end"):
        window = f"时间范围：{time_range['start']} ~ {time_range['end']}"

    if target and window:
        return f"{target}；{window}"
    return target or window or "未指定建筑或时间范围"


def collect_reason_items(question: str, db_context: Dict[str, Any]) -> List[str]:
    focus = detect_focus_items(question)
    reason_items = []

    reason_items.append(
        f"用户关注焦点：{'、'.join(focus)}；样本{db_context.get('total', 0)}条。"
    )

    reason_items.append(
        f"电力特征：平均功率{fmt_number(db_context.get('avg_power'), 'kWh')}，峰值{fmt_number(db_context.get('max_power'), 'kWh')}。"
    )

    if "水系统" in focus:
        reason_items.append(f"水系统特征：平均水耗{fmt_number(db_context.get('avg_water'), 'm3')}。")

    if "空调系统" in focus:
        reason_items.append(f"空调特征：平均空调能耗{fmt_number(db_context.get('avg_ac_power'), 'kWh')}。")

    if "COP效率" in focus:
        reason_items.append(f"能效特征：平均COP为{fmt_number(db_context.get('avg_cop'))}。")

    if "环境参数" in focus:
        reason_items.append(f"环境特征：平均环境温度{fmt_number(db_context.get('avg_env_temp'), '℃')}。")

    if "设备状态" in focus and db_context.get("device_status_dist"):
        status_text = "，".join([f"{k}:{v}" for k, v in db_context["device_status_dist"].items()])
        reason_items.append(f"设备状态分布：{status_text}。")

    if db_context.get("anomaly_count", 0) > 0:
        reason_items.append(
            f"异常记录{db_context.get('anomaly_count')}条，异常率{db_context.get('anomaly_rate')}%。"
        )

    hourly = db_context.get("hourly") or []
    top_hours = sorted(hourly, key=lambda x: x.get("avg", 0), reverse=True)[:3]
    if top_hours:
        hour_desc = "；".join([f"{h['hour']}点约{h['avg']}kWh" for h in top_hours])
        reason_items.append(f"高负荷时段：{hour_desc}。")

    return reason_items


def collect_stats_items(q_type: str, db_context: Dict[str, Any]) -> List[str]:
    stats = db_context.get("stats") or {}
    items = []

    if q_type == "anomaly" and stats.get("summary"):
        summary = stats.get("summary") or {}
        items.append(
            f"统计接口补充：总异常{summary.get('total_anomalies', 0)}条，整体异常率{summary.get('overall_anomaly_rate', 0)}%。"
        )

        by_building = stats.get("by_building") or []
        if by_building:
            top = sorted(by_building, key=lambda x: x.get("anomaly_rate", 0), reverse=True)[0]
            items.append(
                f"异常最突出建筑：{top.get('building_name', top.get('building_id', '未知'))}，异常率{top.get('anomaly_rate', 0)}%。"
            )

    if q_type == "data" and stats.get("data"):
        data_rows = stats.get("data") or []
        if data_rows:
            top_row = sorted(data_rows, key=lambda x: x.get("total_power", 0), reverse=True)[0]
            items.append(
                f"统计接口补充：高负荷节点{top_row.get('period', '未知')}，总电耗约{top_row.get('total_power', 0)}kWh。"
            )

    return items


def collect_action_items(question: str) -> List[str]:
    focus = detect_focus_items(question)
    actions = [
        "核查同时间段设备启停日志与告警记录，确认是否存在非计划运行。",
        "建立分时段基线与阈值预警，对高负荷时段做持续跟踪。",
    ]

    if "COP效率" in focus or "空调系统" in focus:
        actions.append("重点复核空调系统COP、供回水温差与阀门控制逻辑。")

    if "水系统" in focus:
        actions.append("复核流量计与水表读数，排查跑冒滴漏或异常补水。")

    if "设备状态" in focus:
        actions.append("按设备状态分组排查异常机组，优先处理重复告警设备。")

    if "环境参数" in focus:
        actions.append("结合外温与占用率修正运行策略，避免环境扰动引起误判。")

    return actions


def build_fallback_answer(question: str, q_type: str, db_context: Dict[str, Any], kb_content: str) -> str:
    scope_text = format_scope_text(db_context)
    reason_items = collect_reason_items(question, db_context)
    reason_items.extend(collect_stats_items(q_type, db_context))
    action_items = collect_action_items(question)

    brief_question = question.replace("\n", " ").strip()[:120]
    kb_hint = kb_content.replace("\n", " ").strip()[:100] if kb_content else ""

    if q_type == "anomaly":
        selected_actions = action_items[:5]
        reason_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(reason_items[:5])])
        action_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(selected_actions)])
        kb_action = f"{len(selected_actions) + 1}. 知识库提示：{kb_hint}。\n" if kb_hint else ""
        return (
            "【问题】\n"
            f"用户问题：{brief_question}\n"
            f"判定为疑似异常场景，{scope_text}。\n\n"
            "【原因】\n"
            f"{reason_text}\n\n"
            "【措施】\n"
            f"{action_text}\n"
            + kb_action
        )

    if q_type == "data":
        reason_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(reason_items[:4])])
        return (
            "【数据分析】\n"
            f"用户问题：{brief_question}\n"
            f"分析范围：{scope_text}。\n"
            f"{reason_text}\n\n"
            "【趋势说明】\n"
            "建议将高负荷时段与外温、占用率、设备状态做联动比对，定位高耗根因。\n"
            + (f"【知识库提示】\n{kb_hint}\n" if kb_hint else "")
        )

    if q_type == "advice":
        selected_actions = action_items[:5]
        reason_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(reason_items[:3])])
        action_text = "\n".join([f"{i + 1}. {item}" for i, item in enumerate(selected_actions)])
        kb_action = f"{len(selected_actions) + 1}. 知识库提示：{kb_hint}。\n" if kb_hint else ""
        return (
            "【当前情况】\n"
            f"用户问题：{brief_question}\n"
            f"分析范围：{scope_text}。\n"
            f"{reason_text}\n\n"
            "【优化建议】\n"
            f"{action_text}\n"
            + kb_action
        )

    return "问题已收到，请补充建筑、时间范围或设备信息后我将给出更精确结论。"


def call_cloud_model(question: str, q_type: str, db_context: Dict[str, Any], kb_content: str):
    # 当前未接入真实云端大模型，返回可执行的规则化兜底答案，避免 prompt 泄漏。
    return build_fallback_answer(question, q_type, db_context, kb_content)


def looks_like_prompt_leak(answer: str) -> bool:
    markers = ["用户问题：", "数据库数据：", "请输出：", "不要进行故障诊断", "你是能耗分析专家", "你是运维工程师", "【云端模型】"]
    return any(m in answer for m in markers)


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

    if not answer or len(answer.strip()) < 20 or looks_like_prompt_leak(answer):
        answer = call_cloud_model(question, q_type, db_context, kb_content)

    return answer


@router.get("/suggestions")
def get_suggestions():
    return {
        "suggestions": [
            "查询本系统所有建筑的能耗情况",
            "分析空调系统COP能效是否正常",
            "最近有哪些能耗异常记录？",
            "提供建筑节能优化建议",
            "空调设备日常维护保养规范是什么？",
            "供回水温差异常怎么处理？",
            "深夜用电异常的原因和处理方法",
        ]
    }


# ===============================
# 12️⃣ 主接口
# ===============================
@router.post("/ask")
def ask_question(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        question = request.question.strip()
        if not question:
            return {"answer": "请输入问题"}

        query_mode = (request.query_mode or "ai").strip().lower()
        if query_mode == "rule":
            return run_rule_query(request, db)

        q_type = classify_question(question)

        if q_type == "general":
            if request.building_id or request.start_time or request.end_time or is_domain_related(question):
                q_type = "data"
            else:
                return {
                    "answer": "我目前支持建筑能耗数据查询、异常诊断和节能建议。请补充建筑、时间范围或指标（如功率/COP/设备状态）。"
                }

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
            "mode": "ai",
            "router_version": CHAT_ROUTER_VERSION,
            "type": q_type,
            "answer": answer,
            "data": db_context,
            "stats": stats_data
        }
    except Exception as e:
        logger.exception("ask_question failed")
        return JSONResponse(
            status_code=200,
            content={"answer": f"运维助手暂时不可用，请稍后重试。错误信息：{str(e)}"}
        )