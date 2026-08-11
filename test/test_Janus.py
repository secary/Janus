import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def import_janus():
    """隔离模块导入阶段的币种映射数据库查询。"""
    fake_session = MagicMock()
    fake_session.query.return_value.all.return_value = [
        SimpleNamespace(name_cn="美元", code_en="USD"),
    ]
    with patch("sqlalchemy.orm.sessionmaker", return_value=lambda: fake_session):
        sys.modules.pop("main.Janus", None)
        return importlib.import_module("main.Janus")


class GetExchangeRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.janus = import_janus()

    def test_rejects_non_list_currency_argument(self):
        with patch.object(self.janus, "askurl") as askurl:
            result = self.janus.get_exchange_rate("https://example.test", "美元")

        self.assertEqual(result, {})
        askurl.assert_not_called()

    def test_parses_configured_currency_from_html(self):
        html = """
        <table><tr>
          <td>美元</td><td>710.00</td><td>711.00</td><td>712.34</td>
          <td>713.00</td><td>714.00</td><td>2026.08.11 10:30:00</td>
        </tr></table>
        """
        with patch.object(self.janus, "askurl", return_value=html):
            result = self.janus.get_exchange_rate(
                "https://example.test", ["美元"]
            )

        self.assertEqual(
            result,
            {"USD": {"现汇卖出价": "712.34", "日期": "2026.08.11 10:30:00"}},
        )

    def test_returns_empty_result_when_request_fails(self):
        with patch.object(self.janus, "askurl", return_value=None):
            result = self.janus.get_exchange_rate(
                "https://example.test", ["美元"]
            )

        self.assertEqual(result, {})


class StoreDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.janus = import_janus()

    def test_inserts_new_history_and_commits(self):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch.object(self.janus, "get_engine", return_value=MagicMock()),
            patch.object(self.janus, "sessionmaker", return_value=lambda: session),
            patch.object(self.janus.os.path, "exists", return_value=False),
        ):
            self.janus.store_data(
                {"USD": {"现汇卖出价": "712.34", "日期": "2026-08-11 10:30:00"}}
            )

        session.add.assert_called_once()
        added = session.add.call_args.args[0]
        self.assertEqual(added.Currency, "USD")
        self.assertEqual(added.Rate, 712.34)
        session.commit.assert_called_once_with()
        session.close.assert_called_once_with()

    def test_updates_existing_record_without_duplicate_insert(self):
        existing = SimpleNamespace(Locals="old")
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = existing

        with (
            patch.object(self.janus, "get_engine", return_value=MagicMock()),
            patch.object(self.janus, "sessionmaker", return_value=lambda: session),
            patch.object(self.janus.os.path, "exists", return_value=False),
        ):
            self.janus.store_data(
                {"USD": {"现汇卖出价": "712.34", "日期": "2026-08-11 10:30:00"}}
            )

        session.add.assert_not_called()
        self.assertNotEqual(existing.Locals, "old")
        session.commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
