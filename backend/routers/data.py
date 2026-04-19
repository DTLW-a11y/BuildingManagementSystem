"""
数据导入路由
支持CSV文件导入和数据查看
"""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import EnergyRecord

router = APIRouter(prefix="/api/data", tags=["数据管理"])


@router.post("/import", summary="导入CSV能耗数据")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    导入能耗数据CSV文件。
    支持的字段：record_id, building_id, building_name, building_type,
    monitor_time, year, month, day, hour, power_consumption, water_consumption,
    ac_power_consumption, ac_supply_temp, ac_return_temp, cop,
    env_temperature, env_humidity, occupancy_density,
    device_id, device_status, anomaly_flag, anomaly_reason
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持CSV格式文件")

    content = await file.read()
    decoded = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    inserted = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader):
        try:
            existing = db.query(EnergyRecord).filter(
                EnergyRecord.record_id == row["record_id"]
            ).first()
            if existing:
                skipped += 1
                continue

            record = EnergyRecord(
                record_id=row["record_id"],
                building_id=row["building_id"],
                building_name=row["building_name"],
                building_type=row["building_type"],
                monitor_time=datetime.strptime(row["monitor_time"], "%Y-%m-%d %H:%M:%S"),
                year=int(row["year"]),
                month=int(row["month"]),
                day=int(row["day"]),
                hour=int(row["hour"]),
                power_consumption=float(row["power_consumption"]),
                water_consumption=float(row["water_consumption"]),
                ac_power_consumption=float(row["ac_power_consumption"]),
                ac_supply_temp=float(row["ac_supply_temp"]),
                ac_return_temp=float(row["ac_return_temp"]),
                cop=float(row["cop"]),
                env_temperature=float(row["env_temperature"]),
                env_humidity=float(row["env_humidity"]),
                occupancy_density=float(row["occupancy_density"]),
                device_id=row["device_id"],
                device_status=row["device_status"],
                anomaly_flag=int(row["anomaly_flag"]),
                anomaly_reason=row.get("anomaly_reason", ""),
            )
            db.add(record)
            inserted += 1

            if inserted % 200 == 0:
                db.commit()

        except Exception as e:
            errors.append(f"第{i+2}行: {str(e)}")
            if len(errors) > 10:
                break

    db.commit()

    return {
        "message": "导入完成",
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors[:10],
    }


@router.get("/stats", summary="获取数据集基本统计")
def get_data_stats(db: Session = Depends(get_db)):
    """获取数据集基本统计信息"""
    total = db.query(func.count(EnergyRecord.id)).scalar()
    if total == 0:
        return {"total_records": 0, "message": "数据库为空，请先导入数据"}

    buildings = db.query(
        EnergyRecord.building_id,
        EnergyRecord.building_name,
        EnergyRecord.building_type,
        func.count(EnergyRecord.id).label("record_count"),
    ).group_by(
        EnergyRecord.building_id,
        EnergyRecord.building_name,
        EnergyRecord.building_type,
    ).all()

    anomalies = db.query(func.count(EnergyRecord.id)).filter(
        EnergyRecord.anomaly_flag == 1
    ).scalar()

    time_range = db.query(
        func.min(EnergyRecord.monitor_time),
        func.max(EnergyRecord.monitor_time),
    ).first()

    return {
        "total_records": total,
        "anomaly_count": anomalies,
        "anomaly_rate": round(anomalies / total * 100, 2) if total > 0 else 0,
        "buildings": [
            {
                "building_id": b.building_id,
                "building_name": b.building_name,
                "building_type": b.building_type,
                "record_count": b.record_count,
            }
            for b in buildings
        ],
        "time_range": {
            "start": str(time_range[0]) if time_range[0] else None,
            "end": str(time_range[1]) if time_range[1] else None,
        },
    }


@router.delete("/clear", summary="清空数据库（谨慎操作）")
def clear_data(db: Session = Depends(get_db)):
    """清空所有能耗记录"""
    count = db.query(func.count(EnergyRecord.id)).scalar()
    db.query(EnergyRecord).delete()
    db.commit()
    return {"message": f"已删除 {count} 条记录"}
