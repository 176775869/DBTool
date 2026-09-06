import tushare as ts
import os, sys
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

ts.set_token(os.environ.get('TUSHARE_TOKEN'))
pro = ts.pro_api()

def get_output_path(filename):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, filename)

if __name__ == '__main__':
    trade_date = datetime.now().strftime('%Y%m%d')
    # 获取全市场股票涨跌幅、换手、成交额、量比等
    df = pro.daily_basic(trade_date=trade_date, fields='ts_code,close,pct_chg,turnover_rate,volume,amount')
    if df is None or df.empty:
        sys.exit(1)
    # 加入量比（需前一日成交量，这里简化为成交额/流通市值，不严格）
    # 原脚本有量比、新高次数等，这里简化筛选：涨幅>0，换手>5%，成交额>1亿
    df = df[(df['pct_chg'] > 0) & (df['turnover_rate'] > 5) & (df['amount'] > 1e8)]
    df = df.sort_values('pct_chg', ascending=False).head(50)
    if df.empty:
        with open(get_output_path(f'qs_pool_data_{trade_date}.txt'), 'w') as f:
            f.write(f"日期: {trade_date}\n强势股总数: 0\n")
        sys.exit(0)
    lines = [f"日期: {trade_date}", f"强势股总数: {len(df)}", ""]
    lines.append("序号\t名称\t代码\t涨幅\t换手\t成交(亿)\t趋势评分")
    for i, row in df.iterrows():
        # 计算简化评分（仅示例）
        score = row['pct_chg'] + row['turnover_rate'] / 10
        lines.append(f"{i+1}\t{row['ts_code']}\t{row['ts_code'][:8]}\t{row['pct_chg']:.1f}%\t{row['turnover_rate']:.2f}%\t{row['amount']/1e8:.2f}\t{score:.2f}")
    with open(get_output_path(f'qs_pool_data_{trade_date}.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print("✅ 强势股池已保存")