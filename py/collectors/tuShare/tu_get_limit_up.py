import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from tu_logger import get_logger, log_result

logger = get_logger('tu_get_limit_up')

dotenv_path = find_dotenv()
if not dotenv_path:
    logger.error('.env not found')
    sys.exit(1)
load_dotenv(dotenv_path)

TOKEN = os.environ.get('TUSHARE_TOKEN')
if not TOKEN:
    logger.error('TUSHARE_TOKEN not set')
    sys.exit(1)

logger.info('Token loaded (first 4 chars: %s...)', TOKEN[:4])

API_URL = "http://api.tushare.pro"

def fetch_limit_list(trade_date, limit_type='U'):
    start_time = time.time()
    payload = {
        "api_name": "limit_list",
        "token": TOKEN,
        "params": {"trade_date": trade_date, "limit_type": limit_type},
        "fields": "ts_code,name,close,pct_chg,limit_times,first_time,last_time,open,high,low,turnover_rate,amount,limit_amount"
    }
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        elapsed = time.time() - start_time
        logger.info('HTTP status: %d, time: %.2fs', resp.status_code, elapsed)
        if resp.status_code != 200:
            logger.error('HTTP error: %d', resp.status_code)
            return None, elapsed
    except Exception as e:
        logger.error('Request exception: %s', e)
        return None, time.time() - start_time

    try:
        result = resp.json()
    except Exception as e:
        logger.error('JSON decode error: %s', e)
        return None, elapsed

    if result.get('code') != 0:
        logger.error('API error: %s', result.get('msg'))
        return None, elapsed

    data = result.get('data', {})
    df = pd.DataFrame(data.get('items', []), columns=data.get('fields', []))
    logger.info('Fetched %d records', len(df))
    return df, elapsed

def get_output_path(filename):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'py', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def main():
    trade_date = datetime.now().strftime('%Y%m%d')
    logger.info('Fetching limit up for %s', trade_date)

    df, elapsed = fetch_limit_list(trade_date, 'U')
    if df is None:
        log_result(logger, False, 'fetch_limit_list returned None')
        sys.exit(1)
    if df.empty:
        log_result(logger, False, 'No limit up today')
        # 生成空文件
        out_file = get_output_path(f'limit_up_data_{trade_date}.txt')
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(f"日期: {trade_date}\n涨停总数: 0\n最高连板: 0\n")
        logger.info('Empty file saved to %s', out_file)
        sys.exit(0)

    total = len(df)
    max_limit = df['limit_times'].max()
    top_stocks = df[df['limit_times'] == max_limit]['name'].tolist()

    log_result(logger, True, f'Got {total} limit up stocks', total, elapsed)

    out_file = get_output_path(f'limit_up_data_{trade_date}.txt')
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"日期: {trade_date}\n涨停总数: {total}\n最高连板: {max_limit}连板\n")
        if top_stocks:
            f.write(f"最高连板股: {', '.join(top_stocks)}\n")
        f.write("\n序号\t名称\t代码\t涨幅\t连板\t首封\t换手\t成交(亿)\t封单额(亿)\n")
        for i, row in df.iterrows():
            f.write(f"{i+1}\t{row['name']}\t{row['ts_code'][:8]}\t{row['pct_chg']:.1f}%\t{row['limit_times']}\t{row['first_time']}\t{row['turnover_rate']:.2f}%\t{row['amount']/1e8:.2f}\t{row['limit_amount']/1e8:.2f}\n")
    logger.info('Saved to %s', out_file)

if __name__ == '__main__':
    main()