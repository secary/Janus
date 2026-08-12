from loguru import logger
import os
import sys

# ⭐ 加这一段（关键）
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BASE_DIR)

import contextvars
from datetime import datetime
from sqlalchemy.orm import sessionmaker
import json
from queue import Queue, Empty
import threading
import time

from app.config import get_engine

# ===============================
# 基础配置
# ===============================

# LOG_DIR = os.path.join(BASE_DIR, "logs")
# os.makedirs(LOG_DIR, exist_ok=True)

engine = get_engine()
Session = sessionmaker(bind=engine)

# ===============================
# trace_id 管理
# ===============================

default_trace = contextvars.ContextVar("default_trace", default="-")

trace_ids = {
    "janus": contextvars.ContextVar("janus_trace_id", default="-"),
    "jervis": contextvars.ContextVar("jervis_trace_id", default="-"),
}

# ===============================
# 控制台 sink
# ===============================

def safe_sink(msg):
    record = msg.record
    module_name = record["extra"].get("name", "unknown")
    trace_id = trace_ids.get(module_name, default_trace).get()

    log_line = (
        f"{record['time'].strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} "
        f"[{record['level'].name}] {record['name']} [{trace_id}]: {record['message']}\n"
    )

    print(log_line, end="", file=sys.stderr if record["level"].no >= 30 else sys.stdout)

# ===============================
# 文件 sink
# ===============================

def file_sink_factory(module_prefix, LOG_DIR=os.path.join(BASE_DIR, "logs")):
    def sink(msg):
        record = msg.record
        if record["extra"].get("name") != module_prefix:
            return

        trace_id = trace_ids.get(module_prefix, default_trace).get()

        log_line = (
            f"{record['time'].strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} "
            f"[{record['level'].name}] {record['extra'].get('display', record['name'])} "
            f"[{trace_id}]: {record['message']}\n"
        )

        log_file = os.path.join(LOG_DIR, f"{module_prefix.capitalize()}.log")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)

    return sink

# ===============================
# ⭐ DB 批量队列（核心优化）
# ===============================

log_queue = Queue(maxsize=10000)

def db_worker():
    """后台线程：批量写数据库"""
    batch = []
    last_flush = time.time()

    while True:
        try:
            item = log_queue.get(timeout=1)
            batch.append(item)
        except Empty:
            pass

        # 批量写入条件
        if len(batch) >= 50 or (batch and time.time() - last_flush > 2):
            try:
                with Session() as session:
                    session.execute(
                        """
                        INSERT INTO logs (
                            timestamp, level, module, trace_id, source,
                            log_type, message, extra
                        )
                        VALUES (
                            :timestamp, :level, :module, :trace_id, :source,
                            :log_type, :message, :extra
                        )
                        """,
                        batch
                    )
                    session.commit()
            except Exception:
                pass  # ❗ 不能打日志（避免递归）

            batch.clear()
            last_flush = time.time()

# 启动后台线程
threading.Thread(target=db_worker, daemon=True).start()

# ===============================
# DB sink（只负责入队）
# ===============================
from sqlalchemy import text

def db_sink(msg):
    record = msg.record

    module_name = record["extra"].get("name", "unknown")

    trace_id = record["extra"].get("trace_id") 

    try:
        with Session() as session:
            session.execute(
                text("""
                    INSERT INTO logs (
                        timestamp, level, module, trace_id, source, log_type, message, extra
                    )
                    VALUES (
                        :timestamp, :level, :module, :trace_id, :source, :log_type, :message, :extra
                    )
                """),
                {
                    "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "level": record["level"].name,
                    "module": record["name"],
                    "trace_id": trace_id,
                    "source": module_name,
                    "log_type": record["extra"].get("type", "system"),
                    "message": record["message"],
                    "extra": json.dumps(record["extra"], ensure_ascii=False)
                }
            )
            session.commit()
    except:
        pass
# ===============================
# logger 初始化
# ===============================

logger.remove()

# 控制台
logger.add(safe_sink, level="INFO")

# 文件
# logger.add(file_sink_factory("janus"), level="DEBUG")
# logger.add(file_sink_factory("jervis"), level="DEBUG")

# ⭐ 数据库（所有日志 + 异步）
logger.add(db_sink, level="DEBUG", enqueue=True)
GLOBAL_LOGGER = logger
# ===============================
# trace_id 查询工具（保留）
# ===============================

from glob import glob

def find_logs_by_trace_id(trace_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT timestamp, level, module, message
                FROM logs
                WHERE trace_id = :trace_id
                ORDER BY timestamp ASC
            """),
            {"trace_id": trace_id}
        )

        return result.fetchall()


if __name__ == "__main__":
    # logger.info("test log")
    logs = find_logs_by_trace_id(input("Input trace id: "))
    for line in logs:
        print(line)
