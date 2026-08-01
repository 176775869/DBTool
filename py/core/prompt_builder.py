"""
prompt_builder.py - 读取 feed_config.json，按场景拼接投喂内容
支持进化笔记自动注入，支持策略历史加载，支持多目录搜索
System Prompt 包含角色设定、规则、数据、策略快照、系统提示、盘中时间等所有背景上下文
User Prompt 仅包含场景指令和用户自定义指令

改进点：
- 增强文件路径解析，优先从项目根目录搜索
- 详细的调试日志，打印每个文件加载状态和大小
- 健壮的错误处理，避免因单个文件缺失导致整体崩溃
- 数据截断按配置生效
"""
import os
import glob
import json
import requests
from datetime import datetime

# ---------- 常量 ----------
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'feed_config.json')
EVOLUTION_LOG_PATH = os.path.join(CONFIG_DIR, 'evolution_log.txt')
MAX_EVOLUTION_ITEMS = 15

# 项目根目录（假设 prompt_builder.py 在 py/core/ 下）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_SEARCH_DIRS = [
    os.path.join(PROJECT_ROOT, 'py', 'data'),
    os.path.join(PROJECT_ROOT, 'py', 'collectors'),
    PROJECT_ROOT,
]

# 数据文件语义标签
DATA_LABELS = {
    'index_data': '【大盘指数数据】',
    'limit_up': '【涨停个股数据】',
    'zhaban': '【炸板个股数据】',
    'limit_down': '【跌停个股数据】',
    'sector_ma': '【板块均线状态数据】',
    'sector': '【板块行情数据（含涨幅、涨跌比、主力净流入）】',
    'mid_cap': '【核心中军行情数据（含涨跌幅、成交额）】',
    'top_amount': '【全市场成交额Top20】',
    'qs_pool': '【强势股数据】',
    'market_context': '【产业催化电报】',
    'subscription': '【盘中监控数据】',
    'strategy': '【历史策略快照】',
}

# ---------- 辅助函数 ----------
def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_holidays():
    """加载交易日历：优先从网络获取最新假期，失败则从本地 config 读取"""
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
    cal_path = os.path.join(config_dir, 'trade_calendar.json')
    holidays_set = set()
    try:
        current_year = datetime.now().year
        years_to_fetch = [current_year, current_year - 1]
        all_holidays = {}
        for year in years_to_fetch:
            url = f"https://timor.tech/api/holiday/year/{year}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0:
                    holiday_dict = data.get('holiday', {})
                    all_holidays.update(holiday_dict)
        if all_holidays:
            os.makedirs(config_dir, exist_ok=True)
            with open(cal_path, 'w', encoding='utf-8') as f:
                json.dump({'holidays': sorted(all_holidays.keys())}, f, ensure_ascii=False, indent=2)
            print(f"[PROMPT] 已从网络更新交易日历，共 {len(all_holidays)} 个假期")
            return set(all_holidays.keys())
    except Exception as e:
        print(f"[PROMPT] 网络获取假期失败: {e}，尝试读取本地缓存...")

    if os.path.exists(cal_path):
        try:
            with open(cal_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                holidays_set = set(data.get('holidays', []))
            print(f"[PROMPT] 从本地加载假期，共 {len(holidays_set)} 天")
        except Exception as e:
            print(f"[PROMPT] 读取本地假期文件失败: {e}")
            return set()
    else:
        print("[PROMPT] 本地假期文件不存在，且网络获取失败，将不使用假期判断")
    return holidays_set

def is_trade_day(dt, holidays_set):
    if dt.weekday() >= 5:
        return False
    return dt.strftime('%Y-%m-%d') not in holidays_set

def find_nearest_trade_day(dt, holidays_set, direction='next'):
    from datetime import timedelta
    delta = 1 if direction == 'next' else -1
    cur = dt + timedelta(days=delta)
    while True:
        if is_trade_day(cur, holidays_set):
            return cur
        cur = cur + timedelta(days=delta)

def get_system_note():
    today = datetime.now()
    holidays = load_holidays()
    if is_trade_day(today, holidays):
        note = f"当前日期：{today.strftime('%Y年%m月%d日')}（今日为交易日）。"
    else:
        prev_trade = find_nearest_trade_day(today, holidays, 'prev')
        next_trade = find_nearest_trade_day(today, holidays, 'next')
        note = f"当前日期：{today.strftime('%Y年%m月%d日')}（休市），上一个交易日为{prev_trade.strftime('%Y年%m月%d日')}，下一个交易日为{next_trade.strftime('%Y年%m月%d日')}。以下数据来自上一个交易日。"
    return note

def save_evolution_note(note):
    if not note or not note.strip():
        return
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f"[{timestamp}] {note.strip()}\n"
    with open(EVOLUTION_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(entry)

def load_evolution_notes():
    if not os.path.exists(EVOLUTION_LOG_PATH):
        return ""
    with open(EVOLUTION_LOG_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    recent = lines[-MAX_EVOLUTION_ITEMS:] if len(lines) > MAX_EVOLUTION_ITEMS else lines
    if not recent:
        return ""
    return "【历史经验教训（AI 过去犯过的错，本次必须避免）】\n" + "".join(recent)

def get_label(filename):
    for key, label in DATA_LABELS.items():
        if key in filename:
            return label
    return ''

def resolve_file(file_ref, base_dir, max_limit=0, max_qs=0, max_limit_down=0, max_zhaban=0):
    """
    解析文件引用，支持 AUTO_LATEST: 模式自动查找最新文件，并支持按配置截断行数
    返回 (内容, 文件路径)
    """
    if file_ref.startswith('AUTO_LATEST:'):
        pattern = file_ref[len('AUTO_LATEST:'):]
        # 在所有搜索路径中查找匹配文件
        found = []
        for d in DATA_SEARCH_DIRS:
            full_pattern = os.path.join(d, pattern)
            matches = glob.glob(full_pattern)
            found.extend(matches)
        if not found:
            # 额外尝试：直接以 base_dir 为根（兼容旧逻辑）
            full_pattern = os.path.join(base_dir, pattern)
            matches = glob.glob(full_pattern)
            found.extend(matches)

        if not found:
            print(f"[PROMPT] 警告：未找到匹配文件 {pattern}，搜索路径: {DATA_SEARCH_DIRS}")
            return "", None

        # 按修改时间排序，取最新
        latest = max(found, key=os.path.getmtime)
        print(f"[PROMPT] 加载文件: {os.path.basename(latest)} (大小 {os.path.getsize(latest)} 字节)")
        with open(latest, 'r', encoding='utf-8') as f:
            content = f.read()

        # 根据文件类型和配置截断行数
        basename = os.path.basename(latest)
        max_items = None
        if 'limit_down' in basename:
            max_items = max_limit_down if max_limit_down > 0 else None
        elif 'zhaban' in basename:
            max_items = max_zhaban if max_zhaban > 0 else None
        elif 'limit_up' in basename or 'limit' in basename:
            max_items = max_limit if max_limit > 0 else None
        elif 'qs_pool' in basename:
            max_items = max_qs if max_qs > 0 else None

        if max_items and max_items > 0:
            lines = content.split('\n')
            header_end = 0
            for i, line in enumerate(lines):
                if line.startswith('序号') or line.startswith('排名'):
                    header_end = i + 1
                    break
            if header_end > 0:
                truncated = '\n'.join(lines[:header_end + max_items])
                print(f"[PROMPT] 截断 {basename} 至 {max_items} 行（原 {len(lines)} 行）")
                content = truncated
        return content, latest
    else:
        # 普通相对路径，尝试在 base_dir 下查找
        path = os.path.join(base_dir, file_ref)
        if not os.path.exists(path):
            # 也尝试在项目根目录下查找
            alt_path = os.path.join(PROJECT_ROOT, file_ref)
            if os.path.exists(alt_path):
                path = alt_path
            else:
                print(f"[PROMPT] 警告：文件不存在 {file_ref}")
                return "", None
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, path

def build_prompt(scene='replay', extra_note=None):
    """
    构建 system_prompt 和 user_prompt
    返回 (system_prompt, user_prompt)
    """
    config = load_config()
    sc = config[scene]
    base_dir = PROJECT_ROOT  # 以项目根目录为基准

    # ---- 用户指令（纯指令） ----
    user_instruction = sc.get('prompt_intro', '') + '\n\n'
    if extra_note:
        user_instruction += f"【用户额外指令（必须严格执行）】{extra_note}\n\n"
        save_evolution_note(extra_note)

    # ---- 构建 System Prompt ----
    system_prompt = sc.get('system_prompt', '')
    system_prompt += '\n\n' + get_system_note()

    # 监控场景注入盘中时间
    if scene == 'monitor':
        now = datetime.now()
        time_hint = f"【盘中时间】当前时间：{now.strftime('%H:%M:%S')}（北京时间）。"
        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            time_hint += " 尚未开盘，请等待9:30。"
        elif now.hour == 9 and now.minute >= 30 and now.hour < 10:
            time_hint += " 处于早盘竞价阶段，D2弱转强信号优先。"
        elif now.hour >= 10 and now.hour < 14:
            time_hint += " 处于盘中交易阶段，综合判断。"
        elif now.hour >= 14 and now.hour < 15:
            time_hint += " 处于尾盘阶段，D3中军回踩低吸信号优先。"
        else:
            time_hint += " 已经收盘，请等待下一个交易日。"
        system_prompt += '\n\n' + time_hint

    preload_parts = []

    # 进化笔记（仅复盘）
    if scene == 'replay':
        evo = load_evolution_notes()
        if evo:
            preload_parts.append(evo)
        # 历史策略快照
        history_days = sc.get('strategy_history_days', 0)
        if history_days > 0:
            strategy_pattern = os.path.join(PROJECT_ROOT, 'strategy_*.md')
            all_strategy_files = sorted(glob.glob(strategy_pattern), key=os.path.getmtime, reverse=True)
            for sf in all_strategy_files[:history_days]:
                with open(sf, 'r', encoding='utf-8') as f:
                    content = f.read()
                    preload_parts.append(f"--- 策略快照：{os.path.basename(sf)} ---\n{content}\n")

    # 加载配置文件中的所有文件
    for fr in sc.get('files', []):
        content, fpath = resolve_file(
            fr, base_dir,
            max_limit=sc.get('max_limit_up', 0),
            max_qs=sc.get('max_qs_pool', 0),
            max_limit_down=sc.get('max_limit_down', 0),
            max_zhaban=sc.get('max_zhaban', 0)
        )
        if content is None or fpath is None:
            continue  # 文件缺失，跳过
        label = get_label(os.path.basename(fpath))
        if label:
            preload_parts.append(f"{label}\n---\n{content}")
        else:
            preload_parts.append(f"--- 文件：{os.path.basename(fpath)} ---\n{content}")

    # 将所有预加载内容拼接到 system_prompt
    if preload_parts:
        system_prompt += '\n\n' + '\n\n'.join(preload_parts)

    # ----- 调试信息 -----
    print(f"[BUILD] 场景: {scene}")
    print(f"[BUILD] system_prompt 长度: {len(system_prompt)} 字符")
    print(f"[BUILD] user_instruction 长度: {len(user_instruction)} 字符")
    print(f"[BUILD] system_prompt 前200字符: {system_prompt[:200].replace(chr(10), ' ')}...")
    print(f"[BUILD] user_instruction 前200字符: {user_instruction[:200].replace(chr(10), ' ')}...")

    return system_prompt, user_instruction

if __name__ == '__main__':
    # 测试：直接运行本文件可查看生成的 prompt 预览
    sp, up = build_prompt('replay')
    print("\n" + "="*60)
    print("SYSTEM PROMPT (前500字符):")
    print(sp[:500])
    print("\n" + "="*60)
    print("USER PROMPT (前500字符):")
    print(up[:500])
    print("\n" + "="*60)
    print(f"总长度: system={len(sp)}, user={len(up)}")