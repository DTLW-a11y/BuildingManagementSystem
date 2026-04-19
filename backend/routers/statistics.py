"""
统计分析路由
实现时段汇总、COP计算分析、数据异常分析等核心统计功能
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from database import get_db
from models import EnergyRecord

router = APIRouter(prefix="/api/stats", tags=["统计分析"])


@router.get("/period_summary", summary="时段能耗汇总分析")
def period_summary(
    building_id: Optional[str] = Query(None, description="建筑编号，多个用逗号分隔"),
    group_by: str = Query("month", description="分组方式：month/day/hour/building"),
    start_time: Optional[str] = Query(None, description="开始时间 YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间 YYYY-MM-DD HH:MM:SS"),
    year: Optional[int] = Query(None, description="年份"),
    db: Session = Depends(get_db),
):
    """
    时段能耗汇总分析。
    支持按月、按天、按小时、按建筑分组统计。
    返回：电力能耗总量、平均值、最大值、记录数。
    """
    q = db.query(EnergyRecord)
    filters = []

    if building_id:
        ids = [b.strip() for b in building_id.split(",")]
        filters.append(EnergyRecord.building_id.in_(ids))
    if start_time:
        filters.append(EnergyRecord.monitor_time >= datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"))
    if end_time:
        filters.append(EnergyRecord.monitor_time <= datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S"))
    if year:
        filters.append(EnergyRecord.year == year)
    if filters:
        q = q.filter(and_(*filters))

    if group_by == "month":
        results = (
            q.with_entities(
                EnergyRecord.year,
                EnergyRecord.month,
                func.sum(EnergyRecord.power_consumption).label("total_power"),
                func.avg(EnergyRecord.power_consumption).label("avg_power"),
                func.max(EnergyRecord.power_consumption).label("max_power"),
                func.sum(EnergyRecord.water_consumption).label("total_water"),
                func.sum(EnergyRecord.ac_power_consumption).label("total_ac_power"),
                func.count(EnergyRecord.id).label("record_count"),
            )
            .group_by(EnergyRecord.year, EnergyRecord.month)
            .order_by(EnergyRecord.year, EnergyRecord.month)
            .all()
        )
        data = [
            {
                "period": f"{r.year}-{r.month:02d}",
                "total_power": round(r.total_power or 0, 2),
                "avg_power": round(r.avg_power or 0, 2),
                "max_power": round(r.max_power or 0, 2),
                "total_water": round(r.total_water or 0, 2),
                "total_ac_power": round(r.total_ac_power or 0, 2),
                "record_count": r.record_count,
            }
            for r in results
        ]

    elif group_by == "hour":
        results = (
            q.with_entities(
                EnergyRecord.hour,
                func.avg(EnergyRecord.power_consumption).label("avg_power"),
                func.sum(EnergyRecord.power_consumption).label("total_power"),
                func.count(EnergyRecord.id).label("record_count"),
            )
            .group_by(EnergyRecord.hour)
            .order_by(EnergyRecord.hour)
            .all()
        )
        data = [
            {
                "period": f"{r.hour:02d}:00",
                "avg_power": round(r.avg_power or 0, 2),
                "total_power": round(r.total_power or 0, 2),
                "record_count": r.record_count,
            }
            for r in results
        ]

    elif group_by == "building":
        results = (
            q.with_entities(
                EnergyRecord.building_id,
                EnergyRecord.building_name,
                EnergyRecord.building_type,
                func.sum(EnergyRecord.power_consumption).label("total_power"),
                func.avg(EnergyRecord.power_consumption).label("avg_power"),
                func.sum(EnergyRecord.water_consumption).label("total_water"),
                func.sum(EnergyRecord.ac_power_consumption).label("total_ac_power"),
                func.count(EnergyRecord.id).label("record_count"),
            )
            .group_by(
                EnergyRecord.building_id,
                EnergyRecord.building_name,
                EnergyRecord.building_type,
            )
            .order_by(EnergyRecord.building_id)
            .all()
        )
        data = [
            {
                "period": r.building_name,
                "building_id": r.building_id,
                "building_type": r.building_type,
                "total_power": round(r.total_power or 0, 2),
                "avg_power": round(r.avg_power or 0, 2),
                "total_water": round(r.total_water or 0, 2),
                "total_ac_power": round(r.total_ac_power or 0, 2),
                "record_count": r.record_count,
            }
            for r in results
        ]

    elif group_by == "day":
        results = (
            q.with_entities(
                EnergyRecord.year,
                EnergyRecord.month,
                EnergyRecord.day,
                func.sum(EnergyRecord.power_consumption).label("total_power"),
                func.avg(EnergyRecord.power_consumption).label("avg_power"),
                func.count(EnergyRecord.id).label("record_count"),
            )
            .group_by(EnergyRecord.year, EnergyRecord.month, EnergyRecord.day)
            .order_by(EnergyRecord.year, EnergyRecord.month, EnergyRecord.day)
            .all()
        )
        data = [
            {
                "period": f"{r.year}-{r.month:02d}-{r.day:02d}",
                "total_power": round(r.total_power or 0, 2),
                "avg_power": round(r.avg_power or 0, 2),
                "record_count": r.record_count,
            }
            for r in results
        ]
    else:
        return {"error": "不支持的分组方式，请使用 month/day/hour/building"}

    return {
        "group_by": group_by,
        "total_items": len(data),
        "data": data,
    }


@router.get("/cop_analysis", summary="COP系数分析")
def cop_analysis(
    building_id: Optional[str] = Query(None, description="建筑编号"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    db: Session = Depends(get_db),
):
    """
    COP（能效比）分析。
    按建筑和月份分析空调系统COP值变化趋势，评估系统能效。
    COP = 制冷/制热量 / 输入功率，值越高能效越好。
    """
    q = db.query(EnergyRecord).filter(EnergyRecord.ac_power_consumption > 0)
    filters = []

    if building_id:
        ids = [b.strip() for b in building_id.split(",")]
        filters.append(EnergyRecord.building_id.in_(ids))
    if year:
        filters.append(EnergyRecord.year == year)
    if month:
        filters.append(EnergyRecord.month == month)
    if filters:
        q = q.filter(and_(*filters))

    # 按建筑和月份分组计算COP统计
    results = (
        q.with_entities(
            EnergyRecord.building_id,
            EnergyRecord.building_name,
            EnergyRecord.month,
            func.avg(EnergyRecord.cop).label("avg_cop"),
            func.min(EnergyRecord.cop).label("min_cop"),
            func.max(EnergyRecord.cop).label("max_cop"),
            func.avg(EnergyRecord.ac_power_consumption).label("avg_ac_power"),
            func.count(EnergyRecord.id).label("record_count"),
        )
        .group_by(
            EnergyRecord.building_id,
            EnergyRecord.building_name,
            EnergyRecord.month,
        )
        .order_by(EnergyRecord.building_id, EnergyRecord.month)
        .all()
    )

    data = [
        {
            "building_id": r.building_id,
            "building_name": r.building_name,
            "month": r.month,
            "avg_cop": round(r.avg_cop or 0, 3),
            "min_cop": round(r.min_cop or 0, 3),
            "max_cop": round(r.max_cop or 0, 3),
            "avg_ac_power": round(r.avg_ac_power or 0, 2),
            "record_count": r.record_count,
            "efficiency_rating": (
                "优" if (r.avg_cop or 0) >= 3.5 else
                "良" if (r.avg_cop or 0) >= 3.0 else
                "中" if (r.avg_cop or 0) >= 2.5 else "差"
            ),
        }
        for r in results
    ]

    # 整体平均COP
    overall = q.with_entities(func.avg(EnergyRecord.cop)).scalar()

    return {
        "overall_avg_cop": round(overall or 0, 3),
        "total_items": len(data),
        "data": data,
    }


@router.get("/anomaly_analysis", summary="能耗异常分析")
def anomaly_analysis(
    building_id: Optional[str] = Query(None, description="建筑编号"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    db: Session = Depends(get_db),
):
    """
    数据异常分析。
    统计各建筑的异常记录数量、异常率及异常类型分布。
    """
    q = db.query(EnergyRecord)
    filters = []

    if building_id:
        ids = [b.strip() for b in building_id.split(",")]
        filters.append(EnergyRecord.building_id.in_(ids))
    if year:
        filters.append(EnergyRecord.year == year)
    if month:
        filters.append(EnergyRecord.month == month)
    if filters:
        q = q.filter(and_(*filters))

    # 按建筑分组统计异常
    results = (
        q.with_entities(
            EnergyRecord.building_id,
            EnergyRecord.building_name,
            func.count(EnergyRecord.id).label("total_count"),
            func.sum(EnergyRecord.anomaly_flag).label("anomaly_count"),
            func.max(
                case((EnergyRecord.anomaly_flag == 1, EnergyRecord.power_consumption), else_=None)
            ).label("max_anomaly_power"),
        )
        .group_by(EnergyRecord.building_id, EnergyRecord.building_name)
        .order_by(EnergyRecord.building_id)
        .all()
    )

    data = []
    for r in results:
        total = r.total_count or 0
        anomaly = int(r.anomaly_count or 0)
        data.append({
            "building_id": r.building_id,
            "building_name": r.building_name,
            "total_count": total,
            "anomaly_count": anomaly,
            "normal_count": total - anomaly,
            "anomaly_rate": round(anomaly / total * 100, 2) if total > 0 else 0,
            "max_anomaly_power": round(r.max_anomaly_power or 0, 2),
        })

    # 异常记录时段分布
    hour_dist = (
        q.filter(EnergyRecord.anomaly_flag == 1)
        .with_entities(
            EnergyRecord.hour,
            func.count(EnergyRecord.id).label("count"),
        )
        .group_by(EnergyRecord.hour)
        .order_by(EnergyRecord.hour)
        .all()
    )

    # 异常原因统计
    reason_dist = (
        q.filter(EnergyRecord.anomaly_flag == 1, EnergyRecord.anomaly_reason != "")
        .with_entities(
            EnergyRecord.anomaly_reason,
            func.count(EnergyRecord.id).label("count"),
        )
        .group_by(EnergyRecord.anomaly_reason)
        .all()
    )

    total_records = sum(r["total_count"] for r in data)
    total_anomalies = sum(r["anomaly_count"] for r in data)

    return {
        "summary": {
            "total_records": total_records,
            "total_anomalies": total_anomalies,
            "overall_anomaly_rate": round(total_anomalies / total_records * 100, 2) if total_records > 0 else 0,
        },
        "by_building": data,
        "hour_distribution": [
            {"hour": r.hour, "count": r.count} for r in hour_dist
        ],
        "reason_distribution": [
            {"reason": r.anomaly_reason, "count": r.count} for r in reason_dist
        ],
    }


@router.get("/overview", summary="系统总览数据")
def get_overview(db: Session = Depends(get_db)):
    """获取系统总览统计数据，用于仪表盘展示"""
    total = db.query(func.count(EnergyRecord.id)).scalar() or 0
    if total == 0:
        return {"message": "暂无数据"}

    total_power = db.query(func.sum(EnergyRecord.power_consumption)).scalar() or 0
    total_water = db.query(func.sum(EnergyRecord.water_consumption)).scalar() or 0
    avg_cop = db.query(func.avg(EnergyRecord.cop)).filter(
        EnergyRecord.ac_power_consumption > 0
    ).scalar() or 0
    anomaly_count = db.query(func.count(EnergyRecord.id)).filter(
        EnergyRecord.anomaly_flag == 1
    ).scalar() or 0

    # 最近30条记录的能耗趋势（按时间排序）
    recent = (
        db.query(
            EnergyRecord.monitor_time,
            func.sum(EnergyRecord.power_consumption).label("total_power"),
        )
        .group_by(EnergyRecord.monitor_time)
        .order_by(EnergyRecord.monitor_time.desc())
        .limit(30)
        .all()
    )

    # 各建筑总能耗
    building_power = (
        db.query(
            EnergyRecord.building_name,
            func.sum(EnergyRecord.power_consumption).label("total"),
        )
        .group_by(EnergyRecord.building_name)
        .order_by(func.sum(EnergyRecord.power_consumption).desc())
        .all()
    )

    return {
        "kpis": {
            "total_records": total,
            "total_power_kwh": round(total_power, 2),
            "total_water_m3": round(total_water, 2),
            "avg_cop": round(avg_cop, 3),
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_count / total * 100, 2),
        },
        "building_power_distribution": [
            {"name": r.building_name, "value": round(r.total, 2)}
            for r in building_power
        ],
        "recent_trend": [
            {
                "time": str(r.monitor_time),
                "total_power": round(r.total_power, 2),
            }
            for r in reversed(recent)
        ],
    }
