import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from tu_logger import get_logger, log_result

logger = get_logger('tu_get_top_amount')

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

def fetch_daily_basic(trade_date, top_n=20):
    start_time = time.time()
    payload = {
        "api_name": "daily_basic",
        "token": TOKEN,
        "params": {"trade_date": trade_date},
        "fields": "ts_code,close,pct_chg,amount,circ_mv"
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
    if not df.empty:
        df = df.sort_values('amount', ascending=False).head(top_n)
    logger.info('Fetched %d records', len(df))
    return df, elapsed

def get_output_path(filename):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'py', 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def main():
    trade_date = datetime.now().strftime('%Y%m%d')
    logger.info('Fetching top amount for %s', trade_date)

    df, elapsed = fetch_daily_basic(trade_date, 20)
    if df is None:
        log_result(logger, False, 'fetch_daily_basic returned None')
        sys.exit(1)
    if df.empty:
        log_result(logger, False, 'No data')
        sys.exit(1)

    log_result(logger, True, f'Got top {len(df)} stocks', len(df), elapsed)

    out_file = get_output_path(f'top_amount_data_{trade_date}.txt')
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"日期: {trade_date}\n全市场成交额Top20\n\n")
        for i, row in df.iterrows():
            f.write(f"{i+1}. {row['ts_code'][:8]}: {row['pct_chg']:.2f}% 成交{row['amount']/1e8:.1f}亿 总市值{row['circ_mv']/1e8:.0f}亿\n")
    logger.info('Saved to %s', out_file)

if __name__ == '__main__':
    main()