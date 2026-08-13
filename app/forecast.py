"""Generate and persist exchange-rate forecasts."""

import os
import time

import numpy as np
import pandas as pd
import torch

from app.config import CURRENCIES, get_currency_code
from app.db import upsert_predictions
from app.logger_config import get_logger
from app.methods import fetch_history, load_latest_model, preprocess, scale

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "rate_lstm"
)

logger = get_logger("janus")


def insert_predictions(df: pd.DataFrame):
    records = [
        {
            "Date": row["Date"],
            "Currency": row["Currency"],
            "Predicted_rate": row["Predicted_Rates"],
            "Locals": row["Locals"],
        }
        for _, row in df.iterrows()
    ]
    upsert_predictions(records)
    logger.info(f"成功写入 {len(records)} 条预测数据")


def lstm_predict(currency: str, days: int = 7):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_latest_model(MODEL_DIR, currency, device)

    currency = currency.upper()
    df = preprocess(fetch_history(currency, 30))
    data = scale(df[["Rate"]])

    steps_per_day = 48
    future_steps = days * steps_per_day
    last_seq = data[-steps_per_day:].copy()
    future_scaled = []

    model.eval()
    for _ in range(future_steps):
        inp = torch.tensor(last_seq[np.newaxis, ...], dtype=torch.float32).to(device)
        with torch.no_grad():
            pred = model(inp).cpu().numpy().flatten()
        future_scaled.append(pred[0])
        last_seq = np.vstack([last_seq[1:], pred.reshape(1, 1)])

    future = scale(np.array(future_scaled).reshape(-1, 1), inverse=True)
    step = df.index[1] - df.index[0]
    future_dates = [df.index[-1] + (index + 1) * step for index in range(future_steps)]
    result = pd.DataFrame(
        {
            "Date": future_dates,
            "Currency": currency,
            "Predicted_Rates": future.flatten(),
            "Locals": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()),
        }
    )
    logger.info(f"未来 {days} 日内 {currency} 汇率预测完成，共 {len(result)} 条")
    return result


def main():
    all_results = []
    for currency in CURRENCIES:
        currency_en = get_currency_code(currency)
        if not currency_en:
            logger.warning(f"{currency} 未存在于数据库内")
            continue
        if len(fetch_history(currency_en, 30)) < 500:
            logger.warning(f"当前 {currency} 数据不足，暂不预测")
            continue
        result = lstm_predict(currency_en)
        if result is not None and not result.empty:
            all_results.append(result)

    if all_results:
        insert_predictions(pd.concat(all_results, ignore_index=True))
    else:
        logger.warning("没有任何币种的预测结果被生成")
