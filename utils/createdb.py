import sys
import os

# 添加项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from config.settings import get_engine
from utils.models import Base, CurrencyMap, ScheduleConfig
import pandas as pd
from utils.models import History  # ⚠️ 确认路径和你项目一致


DEFAULT_SCHEDULES = [
    {
        "job_key": "exchange_crawler",
        "job_name": "汇率抓取",
        "cron_expression": "*/30 * * * *",
        "command": "/app/.venv/bin/python /app/main/Janus.py",
        "enabled": True,
        "description": "抓取中国银行汇率并写入 history 表",
    },
    {
        "job_key": "exchange_prediction",
        "job_name": "汇率预测",
        "cron_expression": "0 2 * * *",
        "command": "/app/.venv/bin/python /app/predictor/Jervis.py",
        "enabled": True,
        "description": "生成未来汇率预测并写入 prediction 表",
    },
    {
        "job_key": "model_training",
        "job_name": "模型训练",
        "cron_expression": "0 3 1 * *",
        "command": "/app/.venv/bin/python /app/predictor/tune_lstm.py",
        "enabled": True,
        "description": "周期性训练 LSTM 模型",
    },
]


def import_csv_to_db(csv_path):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    if not os.path.exists(csv_path):
        print(f"❌ CSV 文件不存在: {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path)

        # ✅ 标准化字段（兼容你当前 storage.py 的结构）
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Rate"] = df["Rate"].astype(float)

        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            exists = session.query(History).filter_by(
                Date=row["Date"],
                Currency=row["Currency"]
            ).first()

            if exists:
                # 更新 Locals 或 Rate（可选）
                exists.Rate = row["Rate"]
                exists.Locals = row.get("Locals")
                updated += 1
            else:
                new_entry = History(
                    Date=row["Date"],
                    Currency=row["Currency"],
                    Rate=row["Rate"],
                    Locals=row.get("Locals")
                )
                session.add(new_entry)
                inserted += 1

        session.commit()
        print(f"✅ CSV 导入完成：新增 {inserted} 条，更新 {updated} 条")

    except Exception as e:
        session.rollback()
        print(f"❌ 导入失败: {e}")
    finally:
        session.close()

def init_db():
    engine = get_engine()
    Session = sessionmaker(bind=engine)

    # ✅ 建表（只做一次）
    Base.metadata.create_all(engine)
    ensure_history_indexes(engine)

    session = Session()

    # ✅ 默认币种
    data = [
        ("USD", "美元"),
        ("JPY", "日元"),
        ("AUD", "澳大利亚元"),
    ]

    for code, name in data:
        exists = session.query(CurrencyMap).filter_by(code_en=code).first()
        if not exists:
            session.add(CurrencyMap(code_en=code, name_cn=name))

    for item in DEFAULT_SCHEDULES:
        exists = session.query(ScheduleConfig).filter_by(job_key=item["job_key"]).first()
        if not exists:
            session.add(ScheduleConfig(**item))

    session.commit()
    session.close()

    print("✅ DB 初始化完成（表 + 币种映射）")


def ensure_history_indexes(engine):
    index_name = "idx_history_currency_date"
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'history'
                  AND INDEX_NAME = :index_name
                LIMIT 1
                """
            ),
            {"index_name": index_name},
        ).first()

        if not exists:
            conn.execute(text(f"CREATE INDEX {index_name} ON history (Currency, Date)"))


if __name__ == "__main__":
    init_db()
    
