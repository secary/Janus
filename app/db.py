"""Raw SQL database access for the worker."""

from sqlalchemy import text

from app.config import get_engine


def fetch_currency_map():
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT name_cn, code_en FROM currency_map")
        ).mappings()
        return {row["name_cn"]: row["code_en"] for row in rows}


def get_currency_code(name_cn: str):
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT code_en FROM currency_map WHERE name_cn = :name_cn LIMIT 1"),
            {"name_cn": name_cn},
        ).scalar_one_or_none()


def upsert_history(rows):
    if not rows:
        return
    with get_engine().begin() as connection:
        connection.execute(
            text("""
                INSERT INTO history (`Date`, Currency, Rate, Locals)
                VALUES (:Date, :Currency, :Rate, :Locals)
                ON DUPLICATE KEY UPDATE Locals = VALUES(Locals), Rate = VALUES(Rate)
            """),
            rows,
        )


def fetch_history(currency: str, start_time):
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("""
                SELECT `Date`, Currency, Rate, Locals
                FROM history
                WHERE Currency = :currency AND `Date` >= :start_time
                ORDER BY `Date` ASC
            """),
            {"currency": currency.upper(), "start_time": start_time},
        ).mappings()
        return list(rows)


def upsert_predictions(rows):
    if not rows:
        return
    with get_engine().begin() as connection:
        connection.execute(
            text("""
                INSERT INTO prediction (`Date`, Currency, Predicted_rate, Locals)
                VALUES (:Date, :Currency, :Predicted_rate, :Locals)
                ON DUPLICATE KEY UPDATE
                    Predicted_rate = VALUES(Predicted_rate), Locals = VALUES(Locals)
            """),
            rows,
        )
