import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import os
import uuid
from loguru import logger
from config.logger_config import trace_ids
from flask import g

# 设置 trace_id（适用于主进程或脚本执行）
trace_id = os.getenv("TRACE_ID_JAVELIN") or f"JAVELIN-{uuid.uuid4()}"
trace_ids["javelin"].set(trace_id)

# 绑定 loguru logger（确保日志输出至 Javelin.log）
logger = logger.bind(name="javelin")

from flask import Blueprint, jsonify, request, render_template
# from main.fetcher import get_exchange_rate
# from main.storage import store_data
from config.settings import WEBSITE, CURRENCIES, get_engine
from utils.models import History, Threshold, Prediction, AutomationSwitch
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import re

main = Blueprint("main", __name__)
Session = sessionmaker(bind=get_engine())

def get_log():
    trace_id = getattr(g, "trace_id", None)

    if not trace_id:
        trace_id = f"JAVELIN-{uuid.uuid4()}"
        trace_ids["javelin"].set(trace_id)
        g.trace_id = trace_id

    return logger.bind(name="javelin", trace_id=trace_id)

@main.route("/", methods=["GET"])
def index():
    return render_template("index.html")
    
@main.route("/api/history", methods=["GET"])
def api_history():
    
    log = get_log()
    log.info("访问了 /api/history 查看历史记录")
    
    session = Session()
    try:
        currency = request.args.get("currency")
        query = session.query(History)
        if currency:
            query = query.filter(History.Currency == currency)
        results = query.order_by(History.Date.desc()).limit(100).all()
        data = [
            {
                "Date": row.Date.strftime("%Y-%m-%d %H:%M:%S"),
                "Currency": row.Currency,
                "Rate": row.Rate,
                "Locals": row.Locals
            } for row in results
        ]
        return jsonify(data)
    finally:
        session.close()

@main.route("/api/logs/latest", methods=["GET"])
def api_logs_latest():
    log = get_log()
    log.info("访问了 /api/logs/latest 查看最新爬虫日志")

    from sqlalchemy import text
    session = Session()

    try:
        rows = session.execute(
            text("""
                SELECT timestamp, level, message
                FROM logs
                WHERE source = 'janus'   -- ⭐关键
                ORDER BY timestamp DESC
                LIMIT 50
            """)
        ).fetchall()

        # 倒序改正（让前端从旧到新显示）
        rows = rows[::-1]

        return jsonify([
            {
                "timestamp": r[0],
                "level": r[1],
                "message": r[2]
            }
            for r in rows
        ])

    finally:
        session.close()

@main.route("/api/config", methods=["GET"])
def api_config_get():
    log = get_log()
    log.info("访问了 /api/config 查看监控配置")
    session = Session()
    try:
        thresholds = session.query(Threshold).all()
        return jsonify([
            {"Currency": t.Currency, "Upper": t.Upper, "Lower": t.Lower}
            for t in thresholds
        ])
    finally:
        session.close()

@main.route("/api/config", methods=["POST"])
def api_config_post():
    log = get_log()
    log.info("访问了 /api/config 更新监控配置")
    data = request.get_json()
    if not data or "Currency" not in data:
        logger.error("请求中缺少 Currency 字段")
        return jsonify({"error": "请求中缺少 Currency 字段"}), 400

    session = Session()
    try:
        t = session.query(Threshold).filter_by(Currency=data["Currency"]).first()
        if t:
            t.Upper = data.get("Upper", t.Upper)
            t.Lower = data.get("Lower", t.Lower)
        else:
            t = Threshold(
                Currency=data["Currency"],
                Upper=data.get("Upper"),
                Lower=data.get("Lower")
            )
            session.add(t)
        session.commit()
        log.info(f"更新了 {t.Currency} 的监控配置: 上限 {t.Upper}, 下限 {t.Lower}")
        return jsonify({"message": "配置已更新", "Currency": t.Currency, "Upper": t.Upper, "Lower": t.Lower})
    except Exception as e:
        session.rollback()
        logger.error(f"更新监控配置失败: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# @main.route("/api/switch/status", methods=["GET"])
# def get_switch_status():
#     log.info("访问了 /api/switch/status 获取当前自动化状态")
#     session = Session()
#     try:
#         switch = session.query(AutomationSwitch).filter_by(key="auto_enabled").first()
#         status_str = "开启" if (switch and switch.value) else "关闭"
#         return jsonify({"status": status_str})
#     finally:
#         session.close()


# @main.route("/api/switch/toggle", methods=["POST"])
# def toggle_switch():
#     log.info("访问了 /api/switch/toggle 切换自动化状态")
#     session = Session()
#     try:
#         switch = session.query(AutomationSwitch).filter_by(key="auto_enabled").first()
#         if switch:
#             switch.value = not switch.value
#         else:
#             switch = AutomationSwitch(key="auto_enabled", value=True)
#             session.add(switch)
#         session.commit()
#         status_str = "开启" if switch.value else "关闭"
#         log.info(f"✅ 自动化开关已设置为：{status_str}")
#         return jsonify({"status": status_str})
#     except Exception as e:
#         session.rollback()
#         logger.error(f"切换自动化开关失败: {e}")
#         return jsonify({"error": str(e)}), 500
#     finally:
#         session.close()

@main.route("/api/latest", methods=["GET"])
def get_latest_rates():
    log = get_log()
    log.info("访问了 /api/latest 获取最新汇率")
    session = Session()
    try:
        # 1️⃣ 获取每种货币的最新一条历史记录
        row_number = func.row_number().over(
            partition_by=History.Currency,
            order_by=History.Date.desc()
        ).label("rnk")

        subquery = session.query(
            History.Date,
            History.Currency,
            History.Rate,
            row_number
        ).subquery()

        latest_history = session.query(subquery).filter(subquery.c.rnk == 1).all()

        response = []

        # 2️⃣ 为每个历史记录找到相邻预测记录
        for row in latest_history:
            predicted = session.query(Prediction).filter(
                and_(
                    Prediction.Currency == row.Currency,
                    Prediction.Date > row.Date
                )
            ).order_by(Prediction.Date.asc()).first()

            response.append({
                "Date": row.Date.strftime("%Y-%m-%d %H:%M:%S"),
                "Currency": row.Currency,
                "Rate": row.Rate,
                "PredictedRate": predicted.Predicted_rate if predicted else None,
                "PredictionDate": predicted.Date.strftime("%Y-%m-%d %H:%M:%S") if predicted else None
            })

        return jsonify(response)

    finally:
        session.close()

@main.route("/api/history/chart", methods=["GET"])
def api_history_chart():
    log = get_log()
    log.info("访问了 /api/history/chart 获取当日历史+预测数据")
    session = Session()
    try:
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)  # 当天 00:00:00

        # 历史（当天到此刻）
        history_rows = (
            session.query(History)
            .filter(History.Date >= today_start, History.Date <= now)
            .all()
        )

        # 预测（当天到此刻，不包含未来）
        prediction_rows = (
            session.query(Prediction)
            .filter(Prediction.Date >= today_start, Prediction.Date <= now)
            .all()
        )

        from collections import defaultdict
        history_map = defaultdict(dict)
        for row in history_rows:
            ts = row.Date.replace(second=0, microsecond=0)
            history_map[row.Currency][ts] = row.Rate

        prediction_map = defaultdict(dict)
        for row in prediction_rows:
            ts = row.Date.replace(second=0, microsecond=0)
            prediction_map[row.Currency][ts] = row.Predicted_rate

        response = {}
        for cur in set(list(history_map.keys()) + list(prediction_map.keys())):
            all_times = sorted(set(history_map[cur].keys()) | set(prediction_map[cur].keys()))
            merged = []
            for dt in all_times:
                merged.append({
                    "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "rate": history_map[cur].get(dt),
                    "predicted": prediction_map[cur].get(dt)
                })
            response[cur] = merged

        return jsonify(response)
    finally:
        session.close()


        
@main.route("/history", methods=["GET"])
def history_page():
    return render_template("history.html")
