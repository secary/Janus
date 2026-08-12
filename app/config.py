import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv(override=False)

DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'database': os.getenv('DB_NAME')
}



BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(BASE_DIR, "data", "ExchangeRates.csv")
WEBSITE = "https://www.boc.cn/sourcedb/whpj/"

# 货币列表
CURRENCIES = ["澳大利亚元", "日元", "美元"]

# 数据库连接
def get_engine():
    url = URL.create(
        "mysql+pymysql",
        username=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": 10,
            "read_timeout": 60,
            "write_timeout": 60,
        },
    )

def get_currency_code(name_cn: str) -> str:
    from app.db import get_currency_code as lookup_currency_code
    return lookup_currency_code(name_cn)
