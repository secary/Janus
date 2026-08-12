"""Main scheduler entry point for Janus worker tasks."""

import argparse

from loguru import logger


def fetch():
    from app.fetcher import main

    main()


def predict():
    from app.forecast import main

    main()


def train(model_name="lstm"):
    from app.train import main

    main(model_name)


def tune(model_name="lstm"):
    from app.tune import main

    main(model_name)


TASKS = {"fetch": fetch, "predict": predict, "train": train, "tune": tune}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=TASKS, nargs="?", default="fetch")
    parser.add_argument("model", nargs="?", default="lstm")
    args = parser.parse_args()
    if args.command in {"train", "tune"}:
        TASKS[args.command](args.model)
    else:
        TASKS[args.command]()
    logger.complete()


if __name__ == "__main__":
    main()
