"""
建筑能耗数据集生成脚本
生成包含1000+条记录的模拟能耗数据集，覆盖多种建筑类型和监测参数。
"""

import csv
import random
import math
from datetime import datetime, timedelta

random.seed(42)

# 建筑配置
BUILDINGS = [
    {"id": "B001", "name": "教学楼A", "type": "教学楼", "area": 8000},
    {"id": "B002", "name": "教学楼B", "type": "教学楼", "area": 6500},
    {"id": "B003", "name": "办公楼", "type": "办公楼", "area": 5000},
    {"id": "B004", "name": "图书馆", "type": "图书馆", "area": 12000},
    {"id": "B005", "name": "实验楼", "type": "实验楼", "area": 7000},
]

# 监测设备配置
DEVICES = {
    "B001": "DEV-001",
    "B002": "DEV-002",
    "B003": "DEV-003",
    "B004": "DEV-004",
    "B005": "DEV-005",
}


def get_season(month: int) -> str:
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "autumn"


def get_temperature(month: int, hour: int) -> float:
    """根据月份和小时生成合理的环境温度"""
    base_temps = {
        1: 2, 2: 5, 3: 12, 4: 18, 5: 23, 6: 28,
        7: 32, 8: 31, 9: 25, 10: 18, 11: 10, 12: 4
    }
    base = base_temps[month]
    # 日内温度变化
    hour_offset = 4 * math.sin((hour - 6) * math.pi / 12)
    noise = random.uniform(-2, 2)
    return round(base + hour_offset + noise, 1)


def get_humidity(temp: float, season: str) -> float:
    """根据温度和季节生成湿度"""
    if season == "summer":
        base = random.uniform(70, 90)
    elif season == "winter":
        base = random.uniform(30, 55)
    else:
        base = random.uniform(50, 75)
    noise = random.uniform(-5, 5)
    return round(min(95, max(20, base + noise)), 1)


def get_occupancy(building_type: str, hour: int, weekday: int) -> float:
    """获取人员密度（人/100㎡）"""
    is_weekend = weekday >= 5

    if building_type == "办公楼":
        if is_weekend:
            return round(random.uniform(0, 2), 1)
        if 9 <= hour <= 17:
            return round(random.uniform(8, 15), 1)
        elif 8 <= hour <= 9 or 17 <= hour <= 19:
            return round(random.uniform(3, 8), 1)
        else:
            return round(random.uniform(0, 1), 1)

    elif building_type in ["教学楼"]:
        if is_weekend:
            return round(random.uniform(0, 3), 1)
        if 8 <= hour <= 12 or 14 <= hour <= 18:
            return round(random.uniform(10, 20), 1)
        elif 12 <= hour <= 14 or 18 <= hour <= 21:
            return round(random.uniform(3, 10), 1)
        else:
            return round(random.uniform(0, 2), 1)

    elif building_type == "图书馆":
        if is_weekend:
            if 9 <= hour <= 21:
                return round(random.uniform(5, 15), 1)
            return round(random.uniform(0, 2), 1)
        if 8 <= hour <= 22:
            return round(random.uniform(5, 18), 1)
        return round(random.uniform(0, 1), 1)

    elif building_type == "实验楼":
        if is_weekend:
            if 9 <= hour <= 18:
                return round(random.uniform(2, 8), 1)
            return round(random.uniform(0, 1), 1)
        if 8 <= hour <= 22:
            return round(random.uniform(4, 12), 1)
        return round(random.uniform(0, 2), 1)

    return round(random.uniform(0, 5), 1)


def get_ac_temperatures(temp: float, season: str) -> tuple:
    """获取空调出水/回水温度"""
    if season == "summer":
        supply_temp = round(random.uniform(7, 12), 1)
        return_temp = round(supply_temp + random.uniform(4, 7), 1)
    elif season == "winter":
        supply_temp = round(random.uniform(45, 55), 1)
        return_temp = round(supply_temp - random.uniform(5, 10), 1)
    else:
        # 春秋季空调少用
        supply_temp = round(random.uniform(10, 20), 1)
        return_temp = round(supply_temp + random.uniform(2, 5), 1)
    return supply_temp, return_temp


def get_power_consumption(
    building: dict, hour: int, temp: float,
    occupancy: float, season: str, weekday: int
) -> float:
    """计算电力能耗（kWh）"""
    area = building["area"]
    btype = building["type"]

    # 基础负荷系数（W/㎡）
    base_load = {"教学楼": 15, "办公楼": 20, "图书馆": 12, "实验楼": 25}.get(btype, 15)

    # 时段系数
    is_weekend = weekday >= 5
    if is_weekend:
        time_factor = 0.4 if not (9 <= hour <= 20) else 0.6
    else:
        if 8 <= hour <= 22:
            time_factor = 1.0
        elif 6 <= hour <= 8 or 22 <= hour <= 23:
            time_factor = 0.5
        else:
            time_factor = 0.2

    # 空调负荷
    if season == "summer" and temp > 26:
        ac_factor = 1.0 + (temp - 26) * 0.08
    elif season == "winter" and temp < 5:
        ac_factor = 1.0 + (5 - temp) * 0.06
    else:
        ac_factor = 0.3

    # 人员负荷
    occ_factor = 1.0 + occupancy * 0.02

    power = area * base_load * time_factor * ac_factor * occ_factor / 1000
    noise = random.uniform(0.95, 1.05)
    return round(power * noise, 2)


def get_ac_consumption(power: float, season: str, temp: float) -> float:
    """空调系统能耗（占总能耗比例）"""
    if season == "summer" and temp > 26:
        ratio = random.uniform(0.45, 0.65)
    elif season == "winter" and temp < 5:
        ratio = random.uniform(0.35, 0.55)
    elif season in ["spring", "autumn"] and 15 <= temp <= 28:
        ratio = random.uniform(0.1, 0.25)
    else:
        ratio = random.uniform(0.2, 0.4)
    return round(power * ratio, 2)


def get_water_consumption(
    building: dict, power: float, occupancy: float
) -> float:
    """水耗（m³）"""
    base = building["area"] * 0.0005  # 基础水耗
    occ_contribution = occupancy * 0.01 * building["area"] / 100
    noise = random.uniform(0.9, 1.1)
    return round((base + occ_contribution) * noise, 2)


def calculate_cop(ac_power: float, temp: float, season: str) -> float:
    """计算COP（制冷/制热系数）"""
    if ac_power <= 0:
        return 0.0
    if season == "summer":
        # 制冷COP = 制冷量 / 输入功率，简化模型
        cop = 3.5 - (temp - 26) * 0.05 if temp > 26 else 3.5
    elif season == "winter":
        cop = 2.8 - (5 - temp) * 0.04 if temp < 5 else 2.8
    else:
        cop = 3.0
    noise = random.uniform(0.9, 1.1)
    return round(max(1.0, cop * noise), 2)


def is_anomaly(power: float, building: dict, hour: int, season: str) -> tuple:
    """判断数据是否异常"""
    area = building["area"]
    max_expected = area * 30 / 1000  # 最大期望功耗

    # 随机生成约5%的异常数据
    if random.random() < 0.05:
        return True, "能耗异常偏高"
    if power > max_expected * 1.5:
        return True, "超额用电"
    if hour in [2, 3, 4] and power > area * 5 / 1000:
        if random.random() < 0.3:
            return True, "深夜用电异常"
    return False, ""


def generate_dataset(output_file: str, num_records: int = 1500):
    """生成能耗数据集"""
    records = []

    # 起始时间：2024-01-01 00:00
    start_date = datetime(2024, 1, 1, 0, 0)

    # 为每个建筑生成数据，时间跨度约1年（按小时采样）
    hours_per_building = num_records // len(BUILDINGS)

    for building in BUILDINGS:
        device_id = DEVICES[building["id"]]

        for i in range(hours_per_building):
            # 均匀分布在一年内
            hour_offset = int(i * 8760 / hours_per_building)
            current_time = start_date + timedelta(hours=hour_offset)

            month = current_time.month
            hour = current_time.hour
            weekday = current_time.weekday()
            season = get_season(month)

            temp = get_temperature(month, hour)
            humidity = get_humidity(temp, season)
            occupancy = get_occupancy(building["type"], hour, weekday)

            power = get_power_consumption(building, hour, temp, occupancy, season, weekday)
            ac_power = get_ac_consumption(power, season, temp)
            water = get_water_consumption(building, power, occupancy)
            supply_temp, return_temp = get_ac_temperatures(temp, season)
            cop = calculate_cop(ac_power, temp, season)

            anomaly, anomaly_reason = is_anomaly(power, building, hour, season)
            if anomaly and random.random() < 0.7:
                power = round(power * random.uniform(1.3, 2.0), 2)

            status = "异常" if anomaly else "正常"

            records.append({
                "record_id": f"R{len(records)+1:06d}",
                "building_id": building["id"],
                "building_name": building["name"],
                "building_type": building["type"],
                "monitor_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "year": current_time.year,
                "month": current_time.month,
                "day": current_time.day,
                "hour": current_time.hour,
                "power_consumption": power,
                "water_consumption": water,
                "ac_power_consumption": ac_power,
                "ac_supply_temp": supply_temp,
                "ac_return_temp": return_temp,
                "cop": cop,
                "env_temperature": temp,
                "env_humidity": humidity,
                "occupancy_density": occupancy,
                "device_id": device_id,
                "device_status": status,
                "anomaly_flag": 1 if anomaly else 0,
                "anomaly_reason": anomaly_reason,
            })

    # 打乱记录顺序（可选，保持时间顺序）
    # random.shuffle(records)

    fieldnames = [
        "record_id", "building_id", "building_name", "building_type",
        "monitor_time", "year", "month", "day", "hour",
        "power_consumption", "water_consumption", "ac_power_consumption",
        "ac_supply_temp", "ac_return_temp", "cop",
        "env_temperature", "env_humidity", "occupancy_density",
        "device_id", "device_status", "anomaly_flag", "anomaly_reason",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"数据集已生成：{output_file}")
    print(f"总记录数：{len(records)}")
    print(f"建筑数量：{len(BUILDINGS)}")
    print(f"时间范围：{records[0]['monitor_time']} ~ {records[-1]['monitor_time']}")

    # 统计异常数量
    anomalies = sum(1 for r in records if r["anomaly_flag"] == 1)
    print(f"异常记录数：{anomalies}（{anomalies/len(records)*100:.1f}%）")

    return records


if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    generate_dataset(os.path.join(script_dir, "energy_data.csv"), num_records=1500)
