"""Model-independent tuning registry."""

import os
from collections.abc import Callable

import torch
from loguru import logger

from app.config import CURRENCIES, get_currency_code
from app.methods import build_sequences, fetch_history, preprocess, scale, split
from app.models.lstm import RateLSTM

Tuner = Callable[[str], object]
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def tune_lstm(currency: str):
    data = preprocess(fetch_history(currency, 30))
    scaled = scale(data[["Rate"]])
    X, y = build_sequences(scaled, seq_len=48)
    X_train, y_train, _, _ = split(X, y, train_ratio=0.8)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return RateLSTM.tune(
        X=X_train,
        y=y_train,
        currency=currency,
        device=device,
        save_dir=os.path.join(MODEL_DIR, "RateLSTM"),
    )


TUNERS: dict[str, Tuner] = {"lstm": tune_lstm}
MIN_HISTORY_ROWS = 500


def tune_currency(model_name: str, currency: str):
    try:
        tuner = TUNERS[model_name]
    except KeyError as error:
        supported = ", ".join(sorted(TUNERS))
        raise ValueError(
            f"Unsupported model {model_name!r}; choose from: {supported}"
        ) from error
    return tuner(currency)


def main(model_name: str = "lstm"):
    if model_name not in TUNERS:
        supported = ", ".join(sorted(TUNERS))
        raise ValueError(f"Unsupported model {model_name!r}; choose from: {supported}")

    for currency in CURRENCIES:
        currency_code = get_currency_code(currency)
        if not currency_code:
            logger.warning(f"{currency} 未存在于数据库内")
            continue
        if len(fetch_history(currency_code, 30)) < MIN_HISTORY_ROWS:
            logger.warning(f"当前 {currency} 数据不足，暂不调优 {model_name}")
            continue

        logger.info(f"开始调优 {currency_code} 的 {model_name} 模型")
        tune_currency(model_name, currency_code)
        logger.info(f"{currency_code} 的 {model_name} 模型调优完成")
