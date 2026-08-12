"""Backward-compatible training entry point backed by model tuners."""

from app.tune import TUNERS, tune_currency
from app.tune import main as tune_main

TRAINERS = TUNERS


def train_currency(model_name: str, currency: str):
    return tune_currency(model_name, currency)


def main(model_name: str = "lstm"):
    tune_main(model_name)
