import importlib
import os
import unittest
from unittest.mock import patch, sentinel


class LoggerConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import once: logger configuration installs process-wide sinks.
        cls.config = importlib.import_module("app.logger_config")

    def test_loggers_share_one_trace_id_but_keep_module_source(self):
        with patch.object(
            self.config._logger, "bind", return_value=sentinel.bound_logger
        ) as bind:
            result = self.config.get_logger("janus")

        self.assertIs(result, sentinel.bound_logger)
        bind.assert_called_once_with(module="janus", trace_id=self.config.TRACE_ID)

    def test_trace_id_uses_single_environment_variable(self):
        with patch.dict(os.environ, {"TRACE_ID": "test-trace"}, clear=False):
            config = importlib.reload(self.config)

        self.assertEqual(config.TRACE_ID, "test-trace")
        with patch.object(config._logger, "bind") as bind:
            config.get_logger("janus")
        bind.assert_called_once_with(module="janus", trace_id="test-trace")

        # Restore the process trace after the patched environment is removed.
        importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
