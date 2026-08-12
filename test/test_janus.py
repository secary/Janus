import sys
import unittest
from unittest.mock import MagicMock, patch

import janus


class SchedulerTests(unittest.TestCase):
    def test_dispatches_selected_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["janus", "predict"]),
            patch.dict(janus.TASKS, {"predict": task}),
        ):
            janus.main()

        task.assert_called_once_with()

    def test_passes_model_name_to_training_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["janus", "train", "chronos"]),
            patch.dict(janus.TASKS, {"train": task}),
        ):
            janus.main()

        task.assert_called_once_with("chronos")

    def test_passes_model_name_to_tuning_task(self):
        task = MagicMock()
        with (
            patch.object(sys, "argv", ["janus", "tune", "chronos"]),
            patch.dict(janus.TASKS, {"tune": task}),
        ):
            janus.main()

        task.assert_called_once_with("chronos")


if __name__ == "__main__":
    unittest.main()
