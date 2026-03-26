import sys
import os

# 添加项目根目录
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from sqlalchemy.orm import sessionmaker
from config.settings import get_engine
from utils.models import Base, CurrencyMap
import pandas as pd
from utils.models import History  # ⚠️ 确认路径和你项目一致


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

    session.commit()
    session.close()

    print("✅ DB 初始化完成（表 + 币种映射）")


if __name__ == "__main__":
    init_db()
    