import requests
import pandas as pd
from datetime import datetime

# ===== 配置 =====
TOKEN = "a51f3a6d4f0775a888fafa7c97869049ef34dadd193e91a4dee5b2b9"  # 从 https://tushare.pro 获取
API_URL = "http://api.tushare.pro"

# ===== 调用函数 =====
def fetch_index_daily(ts_code, start_date=None, end_date=None, fields=None):
    """
    获取指数日线行情
    
    参数:
        ts_code: 指数代码，如 '000001.SH' (上证指数)
        start_date: 开始日期，格式 'YYYYMMDD'
        end_date: 结束日期，格式 'YYYYMMDD'
        fields: 返回字段列表，逗号分隔
    """
    params = {}
    if ts_code:
        params['ts_code'] = ts_code
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    
    payload = {
        "api_name": "index_daily",
        "token": TOKEN,
        "params": params,
        "fields": fields or "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
    }
    
    response = requests.post(API_URL, json=payload)
    result = response.json()
    
    if result.get('code') != 0:
        raise Exception(f"API错误: {result.get('msg')}")
    
    # 解析返回数据
    data = result.get('data', {})
    fields_list = data.get('fields', [])
    items = data.get('items', [])
    
    df = pd.DataFrame(items, columns=fields_list)
    return df

# ===== 使用示例 =====
if __name__ == "__main__":
    # 获取上证指数最近30个交易日数据
    df = fetch_index_daily(
        ts_code='000001.SH',
        end_date=datetime.now().strftime('%Y%m%d')
    )
    print(df.head(10))