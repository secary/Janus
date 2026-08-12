"""Raw SQL database access for the worker."""

from pathlib import Path

from sqlalchemy import text

from app.config import get_engine

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "data" / "schema.sql"


def initialize_database(schema_file: Path = SCHEMA_FILE):
    sql = schema_file.read_text(encoding="utf-8")
    statements = [
        statement.strip() for statement in sql.split(";") if statement.strip()
    ]
    with get_engine().begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
    print(f"DB initialization complete: {len(statements)} statements")


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
    conditions = ["Currency = :currency"]
    parameters = {"currency": currency.upper()}
    if start_time is not None:
        conditions.append("`Date` >= :start_time")
        parameters["start_time"] = start_time

    with get_engine().connect() as connection:
        rows = connection.execute(
            text(f"""
                SELECT `Date`, Currency, Rate, Locals
                FROM history
                WHERE {" AND ".join(conditions)}
                ORDER BY `Date` ASC
            """),
            parameters,
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


if __name__ == "__main__":
    initialize_database()
