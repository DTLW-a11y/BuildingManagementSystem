"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class EnergyRecord(Base):
    """能耗记录表"""
    __tablename__ = "energy_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(20), unique=True, index=True)
    building_id = Column(String(10), index=True)
    building_name = Column(String(50))
    building_type = Column(String(20), index=True)
    monitor_time = Column(DateTime, index=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    day = Column(Integer)
    hour = Column(Integer)
    power_consumption = Column(Float)       # 电力能耗 kWh
    water_consumption = Column(Float)       # 水耗 m³
    ac_power_consumption = Column(Float)    # 空调系统能耗 kWh
    ac_supply_temp = Column(Float)          # 空调出水温度 °C
    ac_return_temp = Column(Float)          # 空调回水温度 °C
    cop = Column(Float)                     # COP值
    env_temperature = Column(Float)         # 环境温度 °C
    env_humidity = Column(Float)            # 环境湿度 %RH
    occupancy_density = Column(Float)       # 人员密度 人/100㎡
    device_id = Column(String(20), index=True)
    device_status = Column(String(10))      # 正常/异常
    anomaly_flag = Column(Integer, default=0)  # 0=正常, 1=异常
    anomaly_reason = Column(Text, default="")
