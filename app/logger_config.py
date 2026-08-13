"""Application logging setup and trace-aware logger factory."""

from __future__ import annotations

import json
import os
import sys
import uuid

from loguru import logger as _logger
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.config import get_engine

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
engine = get_engine()
Session = sessionmaker(bind=engine)


# One trace identifies the complete worker invocation, regardless of module.
TRACE_ID = os.getenv("TRACE_ID") or f"JANUS-{uuid.uuid4()}"


def _format(record: dict) -> str:
    trace_id = record["extra"].get("trace_id", "-")
    return (
        f"{record['time'].strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} "
        f"[{record['level'].name}] {record['name']} [{trace_id}]: "
        f"{record['message']}\n"
    )


def _console_sink(message):
    record = message.record
    print(
        _format(record),
        end="",
        file=sys.stderr if record["level"].no >= 30 else sys.stdout,
    )


def _db_sink(message):
    record = message.record
    extra = record["extra"]
    try:
        with Session() as session:
            session.execute(
                text("""
                    INSERT INTO logs
                    (timestamp, level, module, trace_id, source, log_type, message, extra)
                    VALUES (:timestamp, :level, :module, :trace_id, :source, :log_type, :message, :extra)
                """),
                {
                    "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "level": record["level"].name,
                    "module": record["name"],
                    "trace_id": extra.get("trace_id", "-"),
                    "source": extra.get("module", record["name"]),
                    "log_type": extra.get("type", "system"),
                    "message": record["message"],
                    "extra": json.dumps(extra, ensure_ascii=False),
                },
            )
            session.commit()
    except Exception:  # noqa: BLE001, S110 - logging failures must not recurse
        pass


_logger.remove()
_logger.add(_console_sink, level="INFO")
_logger.add(_db_sink, level="DEBUG", enqueue=True)


def get_logger(module: str):
    """Return a module-tagged logger sharing the process trace id."""
    return _logger.bind(module=module, trace_id=TRACE_ID)


def find_logs_by_trace_id(trace_id: str):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT timestamp, level, module, message FROM logs
                WHERE trace_id = :trace_id ORDER BY timestamp ASC
            """),
            {"trace_id": trace_id},
        ).fetchall()


if __name__ == "__main__":
    for line in find_logs_by_trace_id(input("Input trace id: ")):
        print(line)
