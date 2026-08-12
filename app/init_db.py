"""Initialize database tables from an idempotent SQL file."""

from pathlib import Path

from app.config import get_engine


SCHEMA_FILE = Path(__file__).resolve().parents[1] / "data" / "schema.sql"


def load_statements(schema_file: Path = SCHEMA_FILE):
    sql = schema_file.read_text(encoding="utf-8")
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def init_db(schema_file: Path = SCHEMA_FILE):
    statements = load_statements(schema_file)
    with get_engine().begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
    print(f"DB initialization complete: {len(statements)} statements")


if __name__ == "__main__":
    init_db()
