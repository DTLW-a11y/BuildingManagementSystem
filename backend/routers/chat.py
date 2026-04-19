"""
智慧运维问答路由
基于知识库（RAG风格）和规则引擎的智能问答系统
"""
import re
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from database import get_db
from models import EnergyRecord

router = APIRouter(prefix="/api/chat", tags=["智慧运维"])

# 加载知识库
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base")

def load_knowledge_base() -> dict:
    """加载知识库文本"""
    kb = {}
    for fname in os.listdir(KB_DIR):
        if fname.endswith(".txt"):
            fpath = os.path.join(KB_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                kb[fname] = f.read()
    return kb

KB = load_knowledge_base()


class ChatRequest(BaseModel):
    question: str
    building_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


def search_knowledge_base(query: str) -> str:
    """在知识库中搜索相关内容（简单关键词匹配）"""
    query_lower = query.lower()
    results = []

    keywords_map = {
        "cop": ["cop", "能效比", "能效"],
        "anomaly": ["异常", "故障", "报警"],
        "ac": ["空调", "制冷", "制热", "冷水机", "冷却"],
        "power": ["电力", "用电", "能耗", "电耗"],
        "water": ["水耗", "用水", "水量"],
        "maintenance": ["维护", "保养", "维修", "检修"],
        "temperature": ["温度", "出水", "回水", "供水"],
        "save_energy": ["节能", "省电", "节约"],
    }

    matched_topics = set()
    for topic, kws in keywords_map.items():
        if any(kw in query for kw in kws):
            matched_topics.add(topic)

    for fname, content in KB.items():
        lines = content.split("\n")
        relevant_lines = []
        for i, line in enumerate(lines):
            if any(kw in line for kw in query.split() if len(kw) > 2):
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                relevant_lines.extend(lines[start:end])
        if relevant_lines:
            results.append("\n".join(relevant_lines[:20]))

    return "\n\n".join(results[:3]) if results else ""


def get_db_context(
    db: Session,
    building_id: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
    question: str,
) -> dict:
    """从数据库获取相关上下文数据"""
    q = db.query(EnergyRecord)
    filters = []

    if building_id:
        ids = [b.strip() for b in building_id.split(",")]
        filters.append(EnergyRecord.building_id.in_(ids))
    if start_time:
        try:
            dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            filters.append(EnergyRecord.monitor_time >= dt)
        except ValueError:
            pass
    if end_time:
        try:
            dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            filters.append(EnergyRecord.monitor_time <= dt)
        except ValueError:
            pass

    if filters:
        q = q.filter(and_(*filters))

    total = q.count()
    if total == 0:
        return {"total": 0}

    avg_power = q.with_entities(func.avg(EnergyRecord.power_consumption)).scalar() or 0
    max_power = q.with_entities(func.max(EnergyRecord.power_consumption)).scalar() or 0
    min_power = q.with_entities(func.min(EnergyRecord.power_consumption)).scalar() or 0
    total_power = q.with_entities(func.sum(EnergyRecord.power_consumption)).scalar() or 0
    avg_cop = q.with_entities(func.avg(EnergyRecord.cop)).filter(
        EnergyRecord.ac_power_consumption > 0
    ).scalar() or 0
    anomaly_count = q.filter(EnergyRecord.anomaly_flag == 1).count()

    # 最近5条异常记录
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


MAX_ANSWER_LENGTH = 800


def generate_answer(question: str, db_context: dict, kb_content: str) -> str:
    """
    生成问答回复（基于规则+知识库）
    实际生产环境可替换为LLM API调用
    """
    q = question.strip()
    total = db_context.get("total", 0)

    # 规则1：能耗统计类问题
    if any(kw in q for kw in ["能耗", "用电量", "电力", "电耗"]):
        if total == 0:
            return "当前查询条件下无数据，请调整查询范围。"

        answer = f"**能耗统计分析结果**\n\n"
        answer += f"📊 查询记录数：{total} 条\n"
        answer += f"⚡ 总电力能耗：{db_context['total_power']} kWh\n"
        answer += f"📈 平均小时能耗：{db_context['avg_power']} kWh\n"
        answer += f"🔺 最高小时能耗：{db_context['max_power']} kWh\n"
        answer += f"🔻 最低小时能耗：{db_context['min_power']} kWh\n"
        answer += f"⚠️ 异常记录：{db_context['anomaly_count']} 条（{db_context['anomaly_rate']}%）\n"

        if db_context['anomaly_rate'] > 10:
            answer += f"\n⚠️ **注意**：异常率较高（{db_context['anomaly_rate']}%），建议立即排查原因。"
        elif db_context['avg_power'] > 100:
            answer += f"\n💡 **节能建议**：平均能耗偏高，建议检查空调设定温度和非工作时段设备管理。"

        return answer

    # 规则2：COP分析
    elif any(kw in q for kw in ["cop", "COP", "能效比", "能效"]):
        if total == 0:
            return "当前查询条件下无数据。"

        avg_cop = db_context['avg_cop']
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
            f"**COP能效分析**\n\n"
            f"📊 查询范围内平均COP：**{avg_cop}**\n"
            f"📋 能效评级：{rating}\n\n"
            f"💡 **建议**：{advice}\n\n"
            f"📌 **参考标准**：\n"
            f"- 优秀：COP ≥ 3.5\n"
            f"- 良好：3.0 ≤ COP < 3.5\n"
            f"- 一般：2.5 ≤ COP < 3.0\n"
            f"- 较差：COP < 2.5"
        )

    # 规则3：异常分析
    elif any(kw in q for kw in ["异常", "故障", "报警", "能耗异常", "异常原因"]):
        if total == 0:
            return "当前查询条件下无数据。"

        anomaly_count = db_context['anomaly_count']
        if anomaly_count == 0:
            return "✅ 当前查询范围内未发现能耗异常记录，系统运行正常。"

        answer = f"**能耗异常分析报告**\n\n"
        answer += f"⚠️ 发现 **{anomaly_count}** 条异常记录（异常率 {db_context['anomaly_rate']}%）\n\n"

        if db_context['recent_anomalies']:
            answer += "**最近异常记录：**\n"
            for a in db_context['recent_anomalies'][:3]:
                answer += f"- {a['time']} | {a['building']} | 能耗：{a['power']} kWh | 原因：{a['reason'] or '未知'}\n"

        answer += "\n**可能原因及处理建议：**\n"

        # 从知识库提取相关内容
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

    # 规则4：设备运行状态
    elif any(kw in q for kw in ["设备", "运行状态", "空调", "冷水机", "水泵"]):
        if total == 0:
            return "当前查询条件下无设备数据。"

        # 查询设备状态
        normal_count = total - db_context.get('anomaly_count', 0)
        answer = f"**设备运行状态查询**\n\n"
        answer += f"📊 监测记录总数：{total}\n"
        answer += f"✅ 正常记录：{normal_count} 条\n"
        answer += f"❌ 异常记录：{db_context['anomaly_count']} 条\n\n"

        if kb_content:
            answer += "**运维知识参考：**\n"
            relevant = [l for l in kb_content.split("\n") if l.strip() and len(l) > 10][:5]
            for line in relevant:
                answer += f"{line}\n"

        return answer

    # 规则5：水耗查询
    elif any(kw in q for kw in ["水耗", "用水", "水量"]):
        if total == 0:
            return "当前查询条件下无数据。"
        return (
            f"**水耗统计**\n\n"
            f"📊 查询记录数：{total} 条\n"
            f"💧 该时段用水情况请参考统计分析模块的详细报表。\n\n"
            f"💡 **节水建议**：检查冷却塔补水、卫生间漏水情况，推广节水器具。"
        )

    # 规则6：节能建议
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

    # 规则7：维护保养
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

    # 默认回复：在知识库中搜索
    else:
        if kb_content:
            return (
                f"**智能运维助手回复**\n\n"
                f"根据知识库检索，以下是与您问题相关的信息：\n\n"
                f"{kb_content[:500]}...\n\n"
                f"如需进一步了解，请提供更具体的问题，例如：\n"
                f"- '查询B001教学楼本月能耗'\n"
                f"- '分析系统COP值'\n"
                f"- '查看近期能耗异常记录'\n"
                f"- '提供节能建议'"
            )
        else:
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


@router.post("/ask", summary="智慧运维问答")
def ask_question(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    智慧运维问答接口。
    支持能耗查询、异常分析、COP分析、节能建议等运维相关问题。
    """
    question = request.question.strip()
    if not question:
        return {"answer": "请输入您的问题。", "sources": []}

    # 获取数据库上下文
    db_context = get_db_context(
        db,
        request.building_id,
        request.start_time,
        request.end_time,
        question,
    )

    # 搜索知识库
    kb_content = search_knowledge_base(question)

    # 生成回复
    answer = generate_answer(question, db_context, kb_content)

    return {
        "question": question,
        "answer": answer,
        "data_context": {
            "building_id": request.building_id,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "records_queried": db_context.get("total", 0),
        },
        "sources": list(KB.keys()),
    }


@router.get("/suggestions", summary="获取问题建议列表")
def get_suggestions():
    """返回常见运维问题建议，辅助用户快速提问"""
    return {
        "suggestions": [
            "查询教学楼A本月总能耗",
            "分析系统COP值是否正常",
            "最近有哪些能耗异常记录？",
            "如何提高空调系统能效？",
            "B004图书馆设备运行状态如何？",
            "夜间用电量是否异常？",
            "空调系统供回水温差偏大怎么处理？",
            "提供本季度节能优化建议",
        ]
    }
