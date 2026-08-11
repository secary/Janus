import sys
import os

# 自动加入项目根目录到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from loguru import logger
import uuid
from config.logger_config import trace_ids

# ✅ 绑定 loguru 的 name 字段，用于日志分类输出
logger = logger.bind(name="jervis")
# 设置 trace_id（独立运行时使用 uuid；也支持从环境变量传入）
trace_id = os.getenv("TRACE_ID_JERVIS") or f"JERVIS-{uuid.uuid4()}"
trace_ids["jervis"].set(trace_id)

import pandas as pd
import numpy as np
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from config.settings import get_engine
from utils.models import History

from sklearn.preprocessing import MinMaxScaler
import torch
from models.lstm import RateLSTM  # ✅ 保持绝对路径

scaler = MinMaxScaler()

def fetch_history(currency: str | None=None, days: int | None=None) -> pd.DataFrame:
    """
    返回最近 30 天的 History 记录，结果为 Pandas DataFrame。
    """
    Session = sessionmaker(bind=get_engine())
    session = Session()
    currency = currency.upper()
    
    try:
        query = session.query(History)
        
        if days:
            start_time = datetime.now() - timedelta(days=days)
            query = session.query(History).filter(History.Date >= start_time)

        if currency:
            query = query.filter(History.Currency == currency)

        # 得到 ORM 对象列表
        rows = query.order_by(History.Date.asc()).all()

        # 转成字典列表
        data = [
            {
                "Date": r.Date,
                "Currency": r.Currency,
                "Rate": r.Rate,
                "Locals": r.Locals,
            }
            for r in rows
        ]

        return pd.DataFrame(data)
    finally:
        session.close()
        

def batchify(X, y, batch_size):
    for i in range(0, len(X), batch_size):
        yield X[i:i+batch_size], y[i:i+batch_size]

def scale(x, scaler=scaler, inverse: bool=False):
    if not inverse:
        return scaler.fit_transform(x)
    
    return scaler.inverse_transform(x)

     
def build_sequences(series, seq_len, verbose: bool = False):
    X, y = [], []
    for i in range(len(series) - seq_len):
        X.append(series[i : i + seq_len])
        y.append(series[i + seq_len])
    X, y = np.array(X), np.array(y)
    
    if verbose:
        print(f"Tensor shape: {X.shape}")
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def split(X, y, train_ratio: float, verbose: bool = False) -> tuple:
    TRAIN_SIZE = int(len(X) * train_ratio)
    X_train, y_train = X[:TRAIN_SIZE], y[:TRAIN_SIZE]
    X_test,  y_test  = X[TRAIN_SIZE:], y[TRAIN_SIZE:]
    
    if verbose:
        print(f"Train size: {X_train.shape[0]}\nTest size: {X_test.shape[0]}")
    return X_train, y_train, X_test, y_test
    
def load_latest_model(model_dir: str, currency: str, device: str, verbose: bool=False) -> RateLSTM:
    """
    从指定目录中加载最新的 RateLSTM 模型（.pth 文件）。
    如果找不到模型，将自动调用训练函数。
    """
    currency = currency.upper()
    os.makedirs(model_dir, exist_ok=True)
    
    def find_latest_file():
        files = [
            f for f in os.listdir(model_dir)
            if f.endswith(".pth") and f"RateLSTM_{currency}_" in f
        ]
        files.sort()
        return files[-1] if files else None

    # 尝试第一次查找模型
    latest_file = find_latest_file()

    if not latest_file:
        logger.error(f"⚠️ 未找到 {currency} 模型，尝试自动训练...")
        import tune_lstm
        tune_lstm.tune(currency)  # 自动训练
        latest_file = find_latest_file()

        if not latest_file:
            logger.error(f"❌ 自动训练后仍未找到模型: {currency}")

    latest_path = os.path.join(model_dir, latest_file)
    if verbose:
        print(f"🔍 Loading latest {currency} model: {latest_path}")

    model = RateLSTM().to(device)
    model.load_state_dict(torch.load(latest_path, map_location=device))
    model.eval()
    return model
    
from sklearn.metrics import mean_absolute_error, mean_squared_error

def evaluate_metrics(y_true, y_pred, verbose: bool = True) -> dict:
    """
    评估预测结果的常用回归指标。

    参数:
        y_true: 真实值 (1D array 或 Tensor)
        y_pred: 预测值 (1D array 或 Tensor)
        verbose: 是否打印指标

    返回:
        一个包含 MAE, MSE, RMSE, MAPE 的字典
    """
    # 若为 tensor，转为 numpy
    if hasattr(y_true, 'detach'):
        y_true = y_true.detach().cpu().numpy()
    if hasattr(y_pred, 'detach'):
        y_pred = y_pred.detach().cpu().numpy()

    y_true = np.array(y_true).flatten()
    y_pred = np.array(y_pred).flatten()

    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)

    # 避免除以 0
    nonzero_mask = y_true != 0
    if np.any(nonzero_mask):
        mape = np.mean(np.abs((y_true[nonzero_mask] - y_pred[nonzero_mask]) / y_true[nonzero_mask])) * 100
    else:
        mape = np.nan

    if verbose:
        print(f"MAE  : {mae:.8f}")
        print(f"MSE  : {mse:.8f}")
        print(f"RMSE : {rmse:.8f}")
        print(f"MAPE : {mape:.2f}%")

    return {
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "mape": mape
    }
    
def preprocess(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()[["Date", 'Rate']] 
    data["Date"] = pd.to_datetime(data["Date"])
    data = data.set_index("Date").sort_index()
    data = data.resample("0.5h").mean().interpolate()
    return data