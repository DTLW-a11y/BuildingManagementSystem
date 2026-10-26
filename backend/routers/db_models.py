# db_models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class EnergyRecord(Base):
    __tablename__ = "energy_records"
    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(String)
    building_name = Column(String)
    monitor_time = Column(DateTime)
    power_consumption = Column(Float)
    ac_power_consumption = Column(Float)
    cop = Column(Float)
    anomaly_flag = Column(Integer)
    anomaly_reason = Column(String)

# 数据库连接
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"  # 或替换成你的数据库
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()