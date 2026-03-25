from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, JSON, BigInteger
from datetime import datetime

Base = declarative_base()

class History(Base):
    __tablename__ = 'history'

    Date = Column(DateTime, primary_key=True)
    Currency = Column(String(20), primary_key=True)
    Rate = Column(Float)
    Locals = Column(String(50))

class Threshold(Base):
    __tablename__ = 'thresholds'

    Currency = Column(String(20), primary_key=True)
    Upper = Column(Float)
    Lower = Column(Float)


class AutomationSwitch(Base):
    __tablename__ = 'auto_switch'
    
    key = Column(String(50), primary_key=True)  # 例如：'auto_enabled'
    value = Column(Boolean, nullable=False)  
    
class CurrencyMap(Base):
    __tablename__ = "currency_map"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    name_cn      = Column(String(20), unique=True, nullable=False)  # 中文名
    code_en      = Column(String(10), unique=True, nullable=False)  # 英文代码
    
    
class Prediction(Base):
    __tablename__ = "prediction"
    Date = Column(DateTime, primary_key=True)
    Currency = Column(String(20), primary_key=True)
    Predicted_rate = Column(Float, nullable=False)
    Locals = Column(String(50))
    
class Logs(Base):
    __tablename__ = "logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 基础字段
    timestamp = Column(DateTime)
    level = Column(String(20))

    trace_id = Column(String(100))
    module = Column(String(100))
    source = Column(String(50))       # janus / javelin / jervis
    log_type = Column(String(20))     # system / request / job

    message = Column(Text)

    # request 专用
    method = Column(String(10))
    path = Column(String(255))
    ip = Column(String(50))
    status_code = Column(Integer)
    latency_ms = Column(Integer)

    # job 专用
    job_name = Column(String(100))
    script = Column(String(100))
    exit_code = Column(Integer)

    # 扩展
    extra = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)