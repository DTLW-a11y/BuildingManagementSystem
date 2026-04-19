"""
查询路由 - 基于MCP协议风格的多条件精准查询接口
"""
import csv
import io
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import get_db
from models import EnergyRecord

router = APIRouter(prefix="/api/query", tags=["数据查询"])


def build_query(
    db: Session,
    building_id: Optional[str] = None,
    building_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    device_status: Optional[str] = None,
    anomaly_only: Optional[bool] = False,
    min_power: Optional[float] = None,
    max_power: Optional[float] = None,
):
    """构建查询条件"""
    q = db.query(EnergyRecord)
    filters = []

    if building_id:
        ids = [b.strip() for b in building_id.split(",")]
        filters.append(EnergyRecord.building_id.in_(ids))
    if building_type:
        filters.append(EnergyRecord.building_type == building_type)
    if start_time:
        dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        filters.append(EnergyRecord.monitor_time >= dt)
    if end_time:
        dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        filters.append(EnergyRecord.monitor_time <= dt)
    if year:
        filters.append(EnergyRecord.year == year)
    if month:
        filters.append(EnergyRecord.month == month)
    if device_status:
        filters.append(EnergyRecord.device_status == device_status)
    if anomaly_only:
        filters.append(EnergyRecord.anomaly_flag == 1)
    if min_power is not None:
        filters.append(EnergyRecord.power_consumption >= min_power)
    if max_power is not None:
        filters.append(EnergyRecord.power_consumption <= max_power)

    if filters:
        q = q.filter(and_(*filters))

    return q


@router.get("/records", summary="多条件查询能耗记录")
def query_records(
    building_id: Optional[str] = Query(None, description="建筑编号，多个用逗号分隔，如B001,B002"),
    building_type: Optional[str] = Query(None, description="建筑类型：教学楼/办公楼/图书馆/实验楼"),
    start_time: Optional[str] = Query(None, description="开始时间，格式：YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式：YYYY-MM-DD HH:MM:SS"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份（1-12）"),
    device_status: Optional[str] = Query(None, description="设备状态：正常/异常"),
    anomaly_only: Optional[bool] = Query(False, description="仅查询异常记录"),
    min_power: Optional[float] = Query(None, description="最小电力能耗（kWh）"),
    max_power: Optional[float] = Query(None, description="最大电力能耗（kWh）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页记录数"),
    db: Session = Depends(get_db),
):
    """
    MCP协议风格的多条件查询接口。
    支持按建筑编号、建筑类型、时间范围、设备状态等条件精准查询。
    """
    q = build_query(
        db, building_id, building_type, start_time, end_time,
        year, month, device_status, anomaly_only, min_power, max_power
    )

    total = q.count()
    records = (
        q.order_by(EnergyRecord.monitor_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "records": [
            {
                "record_id": r.record_id,
                "building_id": r.building_id,
                "building_name": r.building_name,
                "building_type": r.building_type,
                "monitor_time": str(r.monitor_time),
                "power_consumption": r.power_consumption,
                "water_consumption": r.water_consumption,
                "ac_power_consumption": r.ac_power_consumption,
                "ac_supply_temp": r.ac_supply_temp,
                "ac_return_temp": r.ac_return_temp,
                "cop": r.cop,
                "env_temperature": r.env_temperature,
                "env_humidity": r.env_humidity,
                "occupancy_density": r.occupancy_density,
                "device_id": r.device_id,
                "device_status": r.device_status,
                "anomaly_flag": r.anomaly_flag,
                "anomaly_reason": r.anomaly_reason,
            }
            for r in records
        ],
    }


@router.get("/export", summary="导出查询结果为CSV")
def export_records(
    building_id: Optional[str] = Query(None),
    building_type: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    device_status: Optional[str] = Query(None),
    anomaly_only: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
):
    """导出查询结果为CSV文件"""
    q = build_query(
        db, building_id, building_type, start_time, end_time,
        year, month, device_status, anomaly_only
    )
    records = q.order_by(EnergyRecord.monitor_time).all()

    output = io.StringIO()
    fieldnames = [
        "record_id", "building_id", "building_name", "building_type",
        "monitor_time", "year", "month", "day", "hour",
        "power_consumption", "water_consumption", "ac_power_consumption",
        "ac_supply_temp", "ac_return_temp", "cop",
        "env_temperature", "env_humidity", "occupancy_density",
        "device_id", "device_status", "anomaly_flag", "anomaly_reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in records:
        writer.writerow({
            "record_id": r.record_id,
            "building_id": r.building_id,
            "building_name": r.building_name,
            "building_type": r.building_type,
            "monitor_time": str(r.monitor_time),
            "year": r.year,
            "month": r.month,
            "day": r.day,
            "hour": r.hour,
            "power_consumption": r.power_consumption,
            "water_consumption": r.water_consumption,
            "ac_power_consumption": r.ac_power_consumption,
            "ac_supply_temp": r.ac_supply_temp,
            "ac_return_temp": r.ac_return_temp,
            "cop": r.cop,
            "env_temperature": r.env_temperature,
            "env_humidity": r.env_humidity,
            "occupancy_density": r.occupancy_density,
            "device_id": r.device_id,
            "device_status": r.device_status,
            "anomaly_flag": r.anomaly_flag,
            "anomaly_reason": r.anomaly_reason,
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=energy_data_export.csv"},
    )
