"""
数据库初始化脚本：建表并从CSV导入能耗数据
"""
import csv
import os
import sys
from datetime import datetime

# 确保可以导入当前目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from models import EnergyRecord


def load_csv(csv_path: str) -> int:
    """从CSV文件导入能耗数据，跳过已存在的记录，返回导入数量"""
    init_db()
    db = SessionLocal()

    total_before = db.query(EnergyRecord).count()
    if total_before > 0:
        print(f"数据库已有 {total_before} 条记录，跳过导入。")
        db.close()
        return 0

    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = EnergyRecord(
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
            db.add(r)
            count += 1
            if count % 300 == 0:
                db.commit()

    db.commit()
    db.close()
    print(f"成功导入 {count} 条能耗记录。")
    return count


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "..", "data", "energy_data.csv")

    if not os.path.exists(csv_path):
        print(f"数据文件不存在：{csv_path}")
        print("请先准备CSV数据文件并放置到 data/energy_data.csv，或通过Web端\"数据管理\"页面手动导入。")
        sys.exit(1)

    load_csv(csv_path)
