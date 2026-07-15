import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
import time
import random
import traceback
import pandas as pd
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
from loguru import logger

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from config.logger_config import trace_ids
from config.settings import WEBSITE, CURRENCIES, get_engine, CSV_FILE

# 设置 trace_id（在初始化前设定）
trace_id = os.getenv("TRACE_ID_JANUS") or f"JANUS-{uuid.uuid4()}"
trace_ids["janus"].set(trace_id)

# 绑定 loguru logger（重要：为日志分类添加标识）
logger = logger.bind(name="janus", trace_id=trace_id)

with get_engine().connect() as conn:
    rows = conn.execute(text("SELECT name_cn, code_en FROM currency_map")).mappings().all()
CN2EN = {row["name_cn"]: row["code_en"] for row in rows}

def askurl(url, timeout=15, retries=3, delay=10):
    import socket
    socket.setdefaulttimeout(timeout)

    USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...',
    'Mozilla/5.0 (X11; Linux x86_64)...']

    
    for attempt in range(1, retries + 1):
        user_agent = random.choice(USER_AGENTS)
        headers = {'User-Agent': user_agent}
        request = urllib.request.Request(url, headers=headers)

        try:
            logger.debug(f" 第 {attempt} 次尝试，URL: {url}, UA: {user_agent}")
            response = urllib.request.urlopen(request, timeout=timeout)
            html = response.read().decode('utf-8')
            logger.debug(f" ✅ 成功，第 {attempt} 次，请求状态码: {response.getcode()}")
            return html

        except urllib.error.HTTPError as e:
            logger.warning(f" ⚠️ 第 {attempt} 次失败 - HTTPError: {e.code}, {e.reason}")
            logger.debug(f" 响应头: {e.headers}")
        except urllib.error.URLError as e:
            logger.warning(f" ⚠️ 第 {attempt} 次失败 - URLError: {e.reason}")
        except TimeoutError as e:
            logger.warning(f" ⚠️ 第 {attempt} 次失败 - TimeoutError: {e}")
        except Exception:
            logger.exception(f" ❌ 第 {attempt} 次失败 - 未知异常")
            logger.debug(traceback.format_exc())

        if attempt < retries:
            sleep_time = delay + random.uniform(2, 5)
            logger.info(f" 将在 {sleep_time:.1f} 秒后重试...")

    logger.error(f" ❌ 所有 {retries} 次尝试均失败，放弃请求。")
    return None

def get_exchange_rate(url, currencies, save_html=False):
    if not isinstance(currencies, list):
        logger.error("❌ currencies 参数必须是一个列表")
        return {}

    html = askurl(url)
    if not html:
        logger.error("❌ 未能获取 HTML 内容")
        return {}
    
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    for currency in currencies:
        target_td = soup.find('td', string=currency)
        if target_td:
            row = target_td.find_parent('tr')
            row_data = [td.get_text(strip=True) for td in row.find_all('td')]
            name_cn = row_data[0]
            name_en = CN2EN.get(name_cn, name_cn)
            result[name_en] = {
                "现汇卖出价": row_data[3],
                "日期": row_data[6]
            }
        
        else:
            logger.warning(f"❌ 未找到包含 '{currency}' 的 <td> 标签")
            
    if save_html:
        timestamp = time.strftime("%Y%m%d_%H%M%S")  # 正确、安全的时间格式
        file = f'source_{timestamp}.html'
        path = os.path.join('data', 'source', file)
        os.makedirs(os.path.dirname(path), exist_ok=True)  # 确保目录存在
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"📁 html源文件已保存至 {path}")

    logger.debug(f"汇率抓取结果: {result}")
    return result


def store_data(data_dict):
    all_data = []

    for currency, data in data_dict.items():
        row = {
            "Date": pd.to_datetime(data.get("日期"), errors="coerce"),
            "Currency": currency,
            "Rate": float(data.get("现汇卖出价")),
            "Locals": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
        }
        all_data.append(row)

    if not all_data:
        logger.warning("未抓取到任何数据，无法存储。")
        return

    df_new = pd.DataFrame(all_data)

    if os.path.exists(CSV_FILE):
        df_existing = pd.read_csv(CSV_FILE)
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_updated = df_new

    # try:
    #     df_updated.to_csv(CSV_FILE, index=False)
    #     logger.info(f"✅ 数据成功存储到 {CSV_FILE}")
    # except Exception as e:
    #     logger.error(f"❌ csv保存错误: {e}")

    engine = get_engine()

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO history (`Date`, Currency, Rate, Locals)
                    VALUES (:Date, :Currency, :Rate, :Locals)
                    ON DUPLICATE KEY UPDATE
                        Locals = VALUES(Locals)
                    """
                ),
                all_data,
            )
        logger.info("✅ 数据成功更新到 exchange.history 数据库表")
    except OperationalError as e:
        logger.error(f"❌ 数据库操作错误: {e.orig}")
        if "Can't connect to MySQL server" in str(e.orig):
            logger.warning("请检查 MySQL 服务器是否在正确的地址运行")
    except Exception as e:
        logger.exception(f"❌ 其他错误: {e}")

def main():
    try:
        logger.info(f"⚓ 开始抓取人民币兑换 {', '.join(CURRENCIES)} 汇率数据")
        
        rates_data = get_exchange_rate(WEBSITE, CURRENCIES)
        if not rates_data:
            logger.warning("⚠️ 未获取任何汇率数据")
            return

        store_data(rates_data)
        logger.info("汇率数据抓取完成")

        # 输出数据为 DataFrame
        df = pd.DataFrame(rates_data)
        print(f"当前汇率：\n{df}")

    except Exception as e:
        logger.exception(f"❌ 出现错误：{e}")

if __name__ == '__main__':
    logger.info("Janus、了解！任せなさい！")
    main()
    logger.complete()
