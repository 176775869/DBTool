# coding=utf-8
"""
获取全市场成交额Top20（修复版：主域名 + 降级方案）
"""
import requests
import json
import time
import os
import glob
from datetime import datetime

def get_output_path(filename):
    return os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"), filename)

def fetch_all_stocks(max_retries=3):
    # 改用标准域名，不带数字前缀（原 23.push2 已不稳定）
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=5000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f6"
        "&fs=m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23"
        "&fields=f2,f3,f6,f8,f12,f14,f20,f21"
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'utf-8'
            text = resp.text
            # 有些接口返回的是callback包裹的，但这里直接返回json
            if '(' in text and ')' in text:
                s = text.index('(') + 1
                e = text.rindex(')')
                text = text[s:e]
            data = json.loads(text)
            if data.get('data') and data['data'].get('diff'):
                return data['data']['diff']
            print(f"第{attempt+1}次尝试：返回数据为空")
        except Exception as e:
            print(f"第{attempt+1}次尝试失败: {e}")
        if attempt < max_retries - 1:
            time.sleep(2)
    print("获取成交额数据失败，尝试降级方案...")
    return None

def get_fallback_top_amount():
    """从历史数据中读取最近一次有效的Top20"""
    data_dir = os.path.dirname(get_output_path(''))
    pattern = os.path.join(data_dir, 'top_amount_data_*.txt')
    files = glob.glob(pattern)
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    with open(latest, 'r', encoding='utf-8') as f:
        content = f.read()
    # 检查是否包含有效数据
    if '全市场成交额Top20' in content:
        return content
    return None

if __name__ == '__main__':
    date_str = datetime.now().strftime('%Y%m%d')
    
    print("获取全市场成交额数据...")
    items = fetch_all_stocks()
    
    if items is None:
        print("实时获取失败，尝试使用历史缓存...")
        fallback = get_fallback_top_amount()
        if fallback:
            # 直接写入历史缓存，但日期改为今天
            lines = fallback.split('\n')
            # 替换第一行的日期
            if lines and lines[0].startswith('日期:'):
                lines[0] = f"日期: {date_str}"
            content = '\n'.join(lines)
            fn = get_output_path(f'top_amount_data_{date_str}.txt')
            with open(fn, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 使用历史缓存保存至 {fn}")
        else:
            print("❌ 无历史缓存可用，退出")
            exit(1)
    else:
        # 正常处理
        top20 = items[:20]
        lines = [f"日期: {date_str}", "全市场成交额Top20", ""]
        for i, item in enumerate(top20, 1):
            name = item.get('f14', '')
            code = item.get('f12', '')
            pct = float(item.get('f3', 0)) if item.get('f3', '-') != '-' else 0
            amount = float(item.get('f6', 0)) / 1e8
            market_cap = float(item.get('f20', 0)) / 1e8 if item.get('f20') not in ('-', '', None) else 0
            lines.append(f"{i}. {name}({code}): {pct:+.2f}% 成交{amount:.1f}亿 总市值{market_cap:.0f}亿")
        
        fn = get_output_path(f'top_amount_data_{date_str}.txt')
        with open(fn, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"✅ 已保存至 {fn}")