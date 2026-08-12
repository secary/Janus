import importlib
import sys
import unittest
from unittest.mock import patch

import pandas as pd


def import_fetcher():
    with patch("app.db.fetch_currency_map", return_value={"美元": "USD"}):
        sys.modules.pop("app.fetcher", None)
        return importlib.import_module("app.fetcher")


class GetExchangeRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fetcher = import_fetcher()

    def test_rejects_non_list_currency_argument(self):
        with patch.object(self.fetcher, "askurl") as askurl:
            result = self.fetcher.get_exchange_rate("https://example.test", "美元")
        self.assertEqual(result, {})
        askurl.assert_not_called()

    def test_parses_configured_currency_from_html(self):
        html = """
        <table><tr>
          <td>美元</td><td>710.00</td><td>711.00</td><td>712.34</td>
          <td>713.00</td><td>714.00</td><td>2026.08.11 10:30:00</td>
        </tr></table>
        """
        with patch.object(self.fetcher, "askurl", return_value=html):
            result = self.fetcher.get_exchange_rate("https://example.test", ["美元"])
        self.assertEqual(
            result,
            {"USD": {"现汇卖出价": "712.34", "日期": "2026.08.11 10:30:00"}},
        )


class StoreDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fetcher = import_fetcher()

    def test_upserts_normalized_history_record(self):
        with (
            patch.object(self.fetcher, "upsert_history") as upsert,
            patch.object(self.fetcher.os.path, "exists", return_value=False),
        ):
            self.fetcher.store_data(
                {"USD": {"现汇卖出价": "712.34", "日期": "2026-08-11 10:30:00"}}
            )
        row = upsert.call_args.args[0][0]
        self.assertEqual(row["Currency"], "USD")
        self.assertEqual(row["Rate"], 712.34)
        self.assertEqual(row["Date"], pd.Timestamp("2026-08-11 10:30:00"))


if __name__ == "__main__":
    unittest.main()
