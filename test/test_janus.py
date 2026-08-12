import sys
import unittest
from unittest.mock import MagicMock, patch

import Janus


class SchedulerTests(unittest.TestCase):
    def test_dispatches_selected_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["Janus", "predict"]),
            patch.dict(Janus.TASKS, {"predict": task}),
        ):
            Janus.main()

        task.assert_called_once_with()

    def test_passes_model_name_to_training_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["Janus", "train", "chronos"]),
            patch.dict(Janus.TASKS, {"train": task}),
        ):
            Janus.main()

        task.assert_called_once_with("chronos")

    def test_passes_model_name_to_tuning_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["Janus", "tune", "chronos"]),
            patch.dict(Janus.TASKS, {"tune": task}),
        ):
            Janus.main()

        task.assert_called_once_with("chronos")


if __name__ == "__main__":
    unittest.main()
