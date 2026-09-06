"""
采集调度器 v2.2
- 支持 use_tushare 开关
- 自动在 py/collectors/ 下寻找脚本
- Tushare 版本位于 py/collectors/tuShare/tu_*.py
- 修复 Windows 下的编码问题
- 传递环境变量给子进程
- 子进程输出直接显示在终端
"""
import os
import time
import glob
import json
import subprocess
import logging

# ---------- 项目根目录 ----------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLLECTORS_DIR = os.path.join(PROJECT_ROOT, 'py', 'collectors')
DATA_DIR = os.path.join(PROJECT_ROOT, 'py', 'data')

# ---------- 配置加载 ----------
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'py', 'config', 'feed_config.json')

def load_use_tushare():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg.get('use_tushare', False)
    except Exception:
        return False

# ---------- 文件映射 ----------
SCRIPT_FILE_MAP = {
    'get_index_only.py': 'index_data_*.txt',
    'get_limit_up.py': 'limit_up_data_*.txt',
    'get_sector.py': 'sector_data_*.txt',
    'get_sector_ma.py': 'sector_ma_data_*.txt',
    'get_zhaban.py': 'zhaban_data_*.txt',
    'get_limit_down.py': 'limit_down_data_*.txt',
    'get_qs_pool.py': 'qs_pool_data_*.txt',
    'get_top_amount.py': 'top_amount_data_*.txt',
    'get_mid_cap.py': 'mid_cap_data_*.txt',
    'get_history.py': 'history_compare_*.txt',
    'get_subscription_data.py': 'subscription_*.txt',
    'market_context_builder.py': 'market_context_*.txt',
}

# ---------- 辅助函数 ----------
def find_latest_file(pattern):
    search_pattern = os.path.join(DATA_DIR, pattern)
    files = glob.glob(search_pattern)
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    return os.path.getmtime(latest)

def should_collect(script_name, interval_seconds, force=False):
    if force:
        return True
    if interval_seconds <= 0:
        return True
    file_pattern = SCRIPT_FILE_MAP.get(script_name)
    if not file_pattern:
        return True
    latest_mtime = find_latest_file(file_pattern)
    if latest_mtime is None:
        return True
    elapsed = time.time() - latest_mtime
    return elapsed > interval_seconds

def get_script_path(script_name):
    """根据 use_tushare 配置返回脚本的完整路径"""
    use_tushare = load_use_tushare()
    if use_tushare:
        tu_path = os.path.join(COLLECTORS_DIR, 'tuShare', f'tu_{script_name}')
        if os.path.exists(tu_path):
            return tu_path
        logging.warning(f'Tushare 版本不存在，回退到原版: {script_name}')
    return os.path.join(COLLECTORS_DIR, script_name)

def run_collector(script_name, force=False):
    path = get_script_path(script_name)
    if not os.path.exists(path):
        logging.error(f'采集脚本不存在: {path}')
        return False

    try:
        # 直接显示子进程输出（不捕获），这样日志和 print 都能看到
        result = subprocess.run(
            ['python', path],
            cwd=PROJECT_ROOT,
            timeout=30,
            env=os.environ.copy()
        )
        if result.returncode != 0:
            logging.error(f'{script_name} 执行失败 (code={result.returncode})')
            return False
        logging.info(f'采集完成: {script_name}')
        return True
    except subprocess.TimeoutExpired:
        logging.warning(f'{script_name} 超时(30s)，跳过')
        return False
    except Exception as e:
        logging.error(f'{script_name} 异常: {e}')
        return False