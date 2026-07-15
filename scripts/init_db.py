import os
import sys

import pymysql
from dotenv import load_dotenv
from pymysql.constants import CLIENT

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_FILE = os.path.join(BASE_DIR, "scripts", "init_db_schema.sql")
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def connect():
    return pymysql.connect(
        host=required_env("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=required_env("DB_USER"),
        password=required_env("DB_PASSWORD"),
        database=required_env("DB_NAME"),
        charset="utf8mb4",
        autocommit=False,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )


def main():
    with open(SCHEMA_FILE, "r", encoding="utf-8") as file:
        schema_sql = file.read()

    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
            while cursor.nextset():
                pass
        connection.commit()
        print("DB 初始化完成（SQL schema）")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    sys.path.append(BASE_DIR)
    main()
