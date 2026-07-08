"""
金价监控脚本 — 企业级趋势状态机 + Bark 推送

告警类型（每个 tick 按优先级链判断，最多触发一种，互斥不冲突）：
  1. 突破告警：无趋势时涨/跌超过 breakout_threshold → 进入趋势，base 锁定
  2. 回调/反弹告警：趋势中从极值反向运动超过 reversal_threshold → 退出趋势，base 重置为当前价
  3. 里程碑告警：趋势内每跨过一个 milestone_step 台阶推一次"持续上涨/下跌"
  4. 震荡盘整告警：无趋势时滚动窗口波幅 >= volatility_amplitude 且冷却已过，独立类型兜底

方向永远明确：所有文案用 +X.XX% / -X.XX%，禁用 ±。

配合 cron job 使用：
  schedule: "*/4 * * * *"
  no_agent: true
  script: "gold_monitor.py"
  deliver: "local"
"""
import json
import sys
import os
import subprocess
from datetime import datetime
from urllib.request import urlopen, Request, ProxyHandler, build_opener
from urllib.parse import quote

# ============ 配置 ============
# 优先从 config.yaml 读取，也可直接修改此处
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yaml')
PRICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gold_last_price.json')
JIN10_CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jin10_client.py')
TIME_FMT = '%Y-%m-%d %H:%M:%S'
# ==============================

# 告警类型常量
ALERT_BREAKOUT_UP = 'breakout_up'
ALERT_BREAKOUT_DOWN = 'breakout_down'
ALERT_MILESTONE_UP = 'milestone_up'
ALERT_MILESTONE_DOWN = 'milestone_down'
ALERT_REVERSAL_UP = 'reversal_up'
ALERT_REVERSAL_DOWN = 'reversal_down'
ALERT_VOLATILITY = 'volatility'

# 默认阈值（config.yaml 缺字段时使用）
DEFAULTS = {
    'python_exe': None,  # 运行时填 sys.executable
    'bark_key': '',
    'quote_code': 'CZBJCJ',
    'breakout_threshold': 0.01,
    'reversal_threshold': 0.01,
    'milestone_step': 0.01,
    'volatility_amplitude': 0.02,
    'volatility_window': 10,
    'cooldown_minutes': 10,
    'proxy': '',
}


def load_config():
    """从 config.yaml 加载配置，向后兼容旧 threshold 字段"""
    config = dict(DEFAULTS)
    config['python_exe'] = sys.executable

    if not os.path.isfile(CONFIG_FILE):
        print(f"[警告] 未找到 {CONFIG_FILE}，使用默认配置", file=sys.stderr)
        return config

    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)

        monitor = raw.get('monitor', {}) or {}
        bark = raw.get('bark', {}) or {}
        proxy_cfg = raw.get('proxy', {}) or {}

        config['bark_key'] = bark.get('key', config['bark_key'])
        config['quote_code'] = monitor.get('quote_code', config['quote_code'])
        config['proxy'] = proxy_cfg.get('address', '') if proxy_cfg.get('enabled') else ''

        # 新阈值字段，缺省回退到旧 threshold（若存在），再回退到默认
        legacy = monitor.get('threshold', None)
        config['breakout_threshold'] = monitor.get('breakout_threshold', legacy if legacy is not None else config['breakout_threshold'])
        config['reversal_threshold'] = monitor.get('reversal_threshold', legacy if legacy is not None else config['reversal_threshold'])
        config['milestone_step'] = monitor.get('milestone_step', legacy if legacy is not None else config['milestone_step'])
        config['volatility_amplitude'] = monitor.get('volatility_amplitude', config['volatility_amplitude'])
        config['volatility_window'] = int(monitor.get('volatility_window', config['volatility_window']))
        config['cooldown_minutes'] = int(monitor.get('cooldown_minutes', config['cooldown_minutes']))
        return config
    except Exception as e:
        print(f"[警告] 读取配置失败: {e}，使用默认配置", file=sys.stderr)
        return config


def get_price(config):
    """调用 jin10_client 获取报价"""
    try:
        result = subprocess.run(
            [config['python_exe'], JIN10_CLIENT, 'quote', config['quote_code']],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        if result.returncode != 0:
            return None, None, f"jin10_client执行失败: {result.stderr}"

        data = json.loads(result.stdout)
        inner = data.get('data', data)
        price = inner.get('close') or inner.get('last') or inner.get('price')

        if price is not None:
            return float(price), data, None
        return None, data, "返回数据中找不到价格字段"
    except subprocess.TimeoutExpired:
        return None, None, "调用jin10_client超时"
    except json.JSONDecodeError as e:
        return None, None, f"解析jin10_client输出失败: {e}"
    except Exception as e:
        return None, None, f"获取价格异常: {e}"


def load_state():
    """读取监控状态"""
    try:
        with open(PRICE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_state(data):
    """保存监控状态"""
    with open(PRICE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def send_bark(config, title, content):
    """通过 Bark 推送消息（有代理走代理，否则直连）。失败时输出完整内容到 stdout"""
    bark_key = config.get('bark_key', '')
    if not bark_key:
        print(f"❌ Bark未配置key\n{title}\n{content}")
        return False

    bark_api = f'https://api.day.app/{bark_key}'
    url = f"{bark_api}/{quote(title, safe='')}/{quote(content, safe='')}"
    req = Request(url, method='GET')
    req.add_header('User-Agent', 'Mozilla/5.0')

    proxy = config.get('proxy', '')
    try:
        if proxy:
            proxy_handler = ProxyHandler({'http': proxy, 'https': proxy})
            opener = build_opener(proxy_handler)
            resp = opener.open(req, timeout=15)
        else:
            resp = urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"❌ Bark推送失败: {e}\n{title}\n{content}")
        return False


# ============ 状态构造与工具 ============

def build_state(base_price, trend, trend_peak, trend_valley,
                last_milestone, price_window,
                last_alert_time=None, last_alert_type=None,
                last_volatility_alert_time=None):
    """构造状态字典，字段对应新 schema"""
    return {
        'base_price': base_price,
        'trend': trend,
        'trend_peak': trend_peak,
        'trend_valley': trend_valley,
        'last_milestone': last_milestone,
        'last_alert_time': last_alert_time,
        'last_alert_type': last_alert_type,
        'price_window': price_window,
        'last_volatility_alert_time': last_volatility_alert_time,
    }


def migrate_state(old):
    """检测旧 schema（base_price/peak/valley/time，无 trend 字段）则返回 None 触发重建"""
    if old is None:
        return None
    if 'trend' not in old:
        return None
    # 兼容历史数据缺失字段
    old.setdefault('trend_peak', old.get('base_price'))
    old.setdefault('trend_valley', old.get('base_price'))
    old.setdefault('last_milestone', 0)
    old.setdefault('last_alert_time', None)
    old.setdefault('last_alert_type', None)
    old.setdefault('price_window', [])
    old.setdefault('last_volatility_alert_time', None)
    return old


def compute_window_amplitude(price_window):
    """计算滚动窗口内的波幅：返回 (max_price, min_price, amplitude)"""
    if not price_window:
        return None, None, 0.0
    prices = [item['p'] for item in price_window]
    wmax = max(prices)
    wmin = min(prices)
    if wmin <= 0:
        return wmax, wmin, 0.0
    return wmax, wmin, (wmax - wmin) / wmin


def cooldown_passed(last_time_str, cooldown_minutes):
    """同类告警冷却判断：last_time_str 为 None 或距现在 >= cooldown_minutes 返回 True"""
    if not last_time_str:
        return True
    try:
        last = datetime.strptime(last_time_str, TIME_FMT)
    except ValueError:
        return True
    elapsed = (datetime.now() - last).total_seconds() / 60.0
    return elapsed >= cooldown_minutes


def milestone_count(change_ratio, step):
    """计算已跨过的里程碑台阶数，规避浮点除法边界问题"""
    if step <= 0:
        return 0
    return int(round(change_ratio / step, 6))


def pct(value):
    """格式化百分比，带正负号，方向永远明确"""
    return f"{'+' if value >= 0 else ''}{value*100:.2f}%"


# ============ 告警文案函数 ============

def alert_breakout_up(current, base, change, now_str):
    title = f"📈 积存金突破上涨 {pct(change)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"基准: {base:.2f}元/克\n"
               f"涨幅: {pct(change)}\n"
               f"时间: {now_str}")
    return ALERT_BREAKOUT_UP, title, content


def alert_breakout_down(current, base, change, now_str):
    title = f"📉 积存金突破下跌 {pct(change)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"基准: {base:.2f}元/克\n"
               f"跌幅: {pct(change)}\n"
               f"时间: {now_str}")
    return ALERT_BREAKOUT_DOWN, title, content


def alert_milestone_up(current, base, change, peak, now_str):
    title = f"📈 积存金持续上涨 {pct(change)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"基准: {base:.2f}元/克\n"
               f"累计涨幅: {pct(change)}\n"
               f"高点: {peak:.2f}元/克\n"
               f"时间: {now_str}")
    return ALERT_MILESTONE_UP, title, content


def alert_milestone_down(current, base, change, valley, now_str):
    title = f"📉 积存金持续下跌 {pct(change)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"基准: {base:.2f}元/克\n"
               f"累计跌幅: {pct(change)}\n"
               f"低点: {valley:.2f}元/克\n"
               f"时间: {now_str}")
    return ALERT_MILESTONE_DOWN, title, content


def alert_reversal_up(current, peak, retrace, change, now_str):
    title = f"⚠️ 积存金冲高回落 {pct(-retrace)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"高点: {peak:.2f}元/克\n"
               f"回撤: {pct(-retrace)}\n"
               f"较基准: {pct(change)}\n"
               f"时间: {now_str}")
    return ALERT_REVERSAL_UP, title, content


def alert_reversal_down(current, valley, bounce, change, now_str):
    title = f"⚠️ 积存金探底反弹 {pct(bounce)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"低点: {valley:.2f}元/克\n"
               f"反弹: {pct(bounce)}\n"
               f"较基准: {pct(change)}\n"
               f"时间: {now_str}")
    return ALERT_REVERSAL_DOWN, title, content


def alert_volatility(current, base, change, wmax, wmin, amp, now_str):
    title = f"🔄 积存金震荡盘整 波幅{amp*100:.2f}% 较基准{pct(change)}"
    content = (f"当前: {current:.2f}元/克\n"
               f"窗口最高: {wmax:.2f}元/克\n"
               f"窗口最低: {wmin:.2f}元/克\n"
               f"波幅: {pct(amp)}\n"
               f"较基准: {pct(change)}\n"
               f"时间: {now_str}")
    return ALERT_VOLATILITY, title, content


# ============ 核心监控逻辑 ============

def check_price(config):
    """
    企业级趋势状态机：每个 tick 按优先级链判断，最多触发一种告警。

    优先级（命中即停）：
      无趋势 → 突破上涨 → 突破下跌 → 震荡盘整（带冷却）
      上涨趋势 → 上涨回调（退出趋势） → 持续上涨里程碑
      下跌趋势 → 下跌反弹（退出趋势） → 持续下跌里程碑
    """
    now_str = datetime.now().strftime(TIME_FMT)

    current, _raw, err = get_price(config)
    if current is None:
        msg = err if err else "获取价格为空"
        send_bark(config, "❌ 积存金监控异常", f"原因: {msg}\n时间: {now_str}")
        return

    state = migrate_state(load_state())
    if state is None:
        state = build_state(base_price=current, trend=None,
                            trend_peak=current, trend_valley=current,
                            last_milestone=0,
                            price_window=[{"t": now_str, "p": current}])
        save_state(state)
        send_bark(config, "✅ 积存金监控启动",
                  f"基准价: {current:.2f}元/克\n时间: {now_str}")
        return

    # 追加到滚动窗口并裁剪
    window = state.get('price_window') or []
    window.append({"t": now_str, "p": current})
    window_size = config['volatility_window']
    if len(window) > window_size:
        window = window[-window_size:]
    state['price_window'] = window

    base = state['base_price']
    trend = state.get('trend')
    change = (current - base) / base if base else 0.0
    alert = None  # (type, title, content)

    breakout_th = config['breakout_threshold']
    reversal_th = config['reversal_threshold']
    step = config['milestone_step']

    if trend is None:
        # ---- 无趋势：判断突破或震荡 ----
        if change >= breakout_th:
            alert = alert_breakout_up(current, base, change, now_str)
            state['trend'] = 'up'
            state['trend_peak'] = current
            state['last_milestone'] = milestone_count(change, step)
        elif change <= -breakout_th:
            alert = alert_breakout_down(current, base, change, now_str)
            state['trend'] = 'down'
            state['trend_valley'] = current
            state['last_milestone'] = milestone_count(-change, step)
        else:
            # 震荡盘整告警：独立类型，仅在无趋势时触发，带冷却
            wmax, wmin, amp = compute_window_amplitude(window)
            if (amp >= config['volatility_amplitude']
                    and cooldown_passed(state.get('last_volatility_alert_time'),
                                        config['cooldown_minutes'])):
                alert = alert_volatility(current, base, change, wmax, wmin, amp, now_str)
                state['last_volatility_alert_time'] = now_str

    elif trend == 'up':
        # ---- 上涨趋势：先判反转，再判里程碑 ----
        peak = max(state.get('trend_peak', current), current)
        state['trend_peak'] = peak
        retrace = (peak - current) / peak if peak else 0.0
        if retrace >= reversal_th:
            alert = alert_reversal_up(current, peak, retrace, change, now_str)
            # 退出趋势，base 重置为当前价，保留窗口
            state = build_state(base_price=current, trend=None,
                                trend_peak=current, trend_valley=current,
                                last_milestone=0,
                                price_window=window,
                                last_volatility_alert_time=state.get('last_volatility_alert_time'))
        else:
            milestone = milestone_count(change, step)
            if milestone > state.get('last_milestone', 0):
                alert = alert_milestone_up(current, base, change, peak, now_str)
                state['last_milestone'] = milestone

    elif trend == 'down':
        # ---- 下跌趋势：先判反转，再判里程碑 ----
        valley = min(state.get('trend_valley', current), current)
        state['trend_valley'] = valley
        bounce = (current - valley) / valley if valley else 0.0
        if bounce >= reversal_th:
            alert = alert_reversal_down(current, valley, bounce, change, now_str)
            state = build_state(base_price=current, trend=None,
                                trend_peak=current, trend_valley=current,
                                last_milestone=0,
                                price_window=window,
                                last_volatility_alert_time=state.get('last_volatility_alert_time'))
        else:
            milestone = milestone_count(-change, step)
            if milestone > state.get('last_milestone', 0):
                alert = alert_milestone_down(current, base, change, valley, now_str)
                state['last_milestone'] = milestone

    if alert:
        send_bark(config, alert[1], alert[2])
        state['last_alert_time'] = now_str
        state['last_alert_type'] = alert[0]

    save_state(state)


def main():
    config = load_config()
    check_price(config)


if __name__ == "__main__":
    main()
