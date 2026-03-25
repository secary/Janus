import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from utils.models import CurrencyMap
from sqlalchemy.orm import sessionmaker

load_dotenv(override=False)

DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME')
}



BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(BASE_DIR, "data", "ExchangeRates.csv")
WEBSITE = "https://www.boc.cn/sourcedb/whpj/"

# 货币列表
CURRENCIES = ["澳大利亚元", "日元", "美元"]

# 数据库连接
def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    )

def get_currency_code(name_cn: str) -> str:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = session.query(CurrencyMap).filter_by(name_cn=name_cn).first()
        if result:
            return result.code_en
        else:
            return None
         
    finally:
        session.close()

