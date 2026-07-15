import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
import uuid
from config.logger_config import trace_ids
# 设置 trace_id（独立运行时使用 uuid；也支持从环境变量传入）
trace_id = os.getenv("TRACE_ID_JERVIS") or f"JERVIS-{uuid.uuid4()}"
trace_ids["jervis"].set(trace_id)

# ✅ 绑定 loguru 的 name 字段，用于日志分类输出
logger = logger.bind(name="jervis",trace_id=trace_id)

# 获取项目根目录（Jervis.py 所在目录的上一级）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "RateLSTM")

import pandas as pd
import numpy as np
import torch
import time

from methods import fetch_history, load_latest_model, scale, preprocess
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import insert as mysql_insert
from config.settings import get_engine, get_currency_code, CURRENCIES # 你已有这个
from utils.models import AppConfig, Prediction # 你的 Prediction ORM


DEFAULT_PREDICTION_METHOD = "lstm"
DEFAULT_PREDICTION_HORIZON_DAYS = 7


def insert_predictions(df: pd.DataFrame):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        records = [
            {
                "Date": row["Date"],
                "Currency": row["Currency"],
                "Predicted_rate": row["Predicted_Rates"],
                "Locals": row["Locals"],
            }
            for _, row in df.iterrows()
        ]

        # 保留历史预测；同一时间点重复生成时只更新该记录，避免主键冲突
        stmt = mysql_insert(Prediction.__table__).values(records)
        stmt = stmt.on_duplicate_key_update(
            Predicted_rate=stmt.inserted.Predicted_rate,
            Locals=stmt.inserted.Locals,
        )
        session.execute(stmt)
        session.commit()
        logger.info(f"✅ 成功写入 {len(records)} 条预测数据")

    except Exception as e:
        session.rollback()
        logger.error(f"❌ 导入 prediction 表失败: {e}")

    finally:
        session.close()


def load_prediction_config() -> tuple[str, int]:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        rows = session.query(AppConfig).filter(
            AppConfig.config_key.in_(["prediction_method", "prediction_horizon_days"])
        ).all()
        values = {row.config_key: row.config_value for row in rows}
        method = values.get("prediction_method", DEFAULT_PREDICTION_METHOD)
        if method not in {"lstm", "last_observed"}:
            logger.warning(f"⚠️ 不支持的预测方法 {method}，回退到 {DEFAULT_PREDICTION_METHOD}")
            method = DEFAULT_PREDICTION_METHOD

        try:
            horizon_days = int(values.get("prediction_horizon_days", DEFAULT_PREDICTION_HORIZON_DAYS))
        except (TypeError, ValueError):
            horizon_days = DEFAULT_PREDICTION_HORIZON_DAYS

        horizon_days = min(max(horizon_days, 1), 30)
        return method, horizon_days
    except Exception as exc:
        logger.warning(f"⚠️ 读取预测配置失败，使用默认配置: {exc}")
        return DEFAULT_PREDICTION_METHOD, DEFAULT_PREDICTION_HORIZON_DAYS
    finally:
        session.close()


def lstm_predict(currency: str, days: int=7):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_latest_model(MODEL_DIR, currency, device)

    currency = currency.upper()
    df = preprocess(fetch_history(currency, 30))
    data = scale(df[['Rate']])

    seq = 48
    # Generate future predictions
    future_steps = days * seq
    last_seq = data[-seq:].copy()
    future_scaled = []

    model.eval()
    for _ in range(future_steps):
        inp = torch.tensor(last_seq[np.newaxis, ...], dtype=torch.float32).to(device)
        with torch.no_grad():
            pred = model(inp).cpu().numpy().flatten()
        future_scaled.append(pred[0])
        last_seq = np.vstack([last_seq[1:], pred.reshape(1, 1)])

    future_scaled = np.array(future_scaled).reshape(-1, 1)
    future = scale(future_scaled, inverse=True)
    step = df.index[1] - df.index[0]
    future_dates = [df.index[-1] + (i+1)*step for i in range(future_steps)]

    df_forecast = pd.DataFrame({
        "Date": future_dates,
        "Currency": currency,
        "Predicted_Rates": future.flatten(),
        "Locals": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    })
    
    logger.info(f"🔮 未来{days}日内{currency}汇率预测完成，共 {len(df_forecast)} 条")
    
    return df_forecast


def last_observed_predict(currency: str, days: int=7):
    currency = currency.upper()
    df = preprocess(fetch_history(currency, 30))
    if df.empty:
        logger.warning(f"⚠️ {currency}历史数据为空，无法使用 last_observed 预测")
        return pd.DataFrame()

    seq = 48
    future_steps = days * seq
    latest_rate = float(df["Rate"].dropna().iloc[-1])
    step = pd.Timedelta(minutes=30)
    future_dates = [df.index[-1] + (i + 1) * step for i in range(future_steps)]

    df_forecast = pd.DataFrame({
        "Date": future_dates,
        "Currency": currency,
        "Predicted_Rates": latest_rate,
        "Locals": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    })
    logger.info(f"🔮 使用 last_observed 生成未来{days}日内{currency}预测，共 {len(df_forecast)} 条")
    return df_forecast

def main():
    try:
        all_results = []  # ⬅️ 存储所有币种的预测结果
        prediction_method, horizon_days = load_prediction_config()
        logger.info(f"当前预测配置：method={prediction_method}, horizon_days={horizon_days}")

        for currency in CURRENCIES:
            currency_en = get_currency_code(currency)
            if not currency_en:
                logger.warning(f"⚠️ {currency}未存在于数据库内")
                continue

            history_rows = fetch_history(currency_en, 30)
            if prediction_method == "lstm" and len(history_rows) < 500:
                logger.warning(f"⚠️ 当前{currency}数据不足，暂不预测")
                continue
            if history_rows.empty:
                logger.warning(f"⚠️ 当前{currency}无历史数据，暂不预测")
                continue

            if prediction_method == "last_observed":
                result = last_observed_predict(currency_en, horizon_days)
            else:
                result = lstm_predict(currency_en, horizon_days)
            if result is not None and not result.empty:
                all_results.append(result)
            else:
                logger.warning(f"⚠️ {currency}预测结果为空")

        # 🔗 合并所有币种的预测结果为一个 DataFrame
        if all_results:
            merged_df = pd.concat(all_results, ignore_index=True)
            # ✍️ 写入数据库
            insert_predictions(merged_df)
        else:
                logger.warning("⚠️ 没有任何币种的预测结果被生成")

    except Exception as e:
        logger.exception(f"❌ 出现错误：{e}")


if __name__ == "__main__":
    logger.info("Nice to meet you. Lucky Jervis、来たわ!")
    main()
    logger.complete()
   
