"""
金价监控脚本 — 双极追踪策略 + Bark 推送

核心逻辑：
  - 追踪上次推送以来的最高价(peak)和最低价(valley)
  - 价格从基准突破阈值 → 趋势通知
  - 价格从极值反转超过阈值 → 反转通知
  - 高低点波动超过阈值 → 波动通知（解决涨跌各不到阈值但总波动大的问题）
  - 每次通知后重置基准为当前价格，重新开始追踪

配合 cron job 使用：
  schedule: "*/5 * * * *"
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
# ==============================


def load_config():
    """从 config.yaml 加载配置"""
    defaults = {
        'python_exe': sys.executable,
        'bark_key': '',
        'quote_code': 'CZBJCJ',
        'threshold': 0.01,
        'proxy': '',
    }

    if not os.path.isfile(CONFIG_FILE):
        print(f"[警告] 未找到 {CONFIG_FILE}，使用默认配置", file=sys.stderr)
        return defaults

    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        monitor = config.get('monitor', {})
        bark = config.get('bark', {})
        proxy_cfg = config.get('proxy', {})

        # 兼容新旧配置字段
        threshold = monitor.get('threshold', None)
        if threshold is None:
            threshold = monitor.get('trend_threshold', defaults['threshold'])

        return {
            'python_exe': sys.executable,
            'bark_key': bark.get('key', defaults['bark_key']),
            'quote_code': monitor.get('quote_code', defaults['quote_code']),
            'threshold': threshold,
            'proxy': proxy_cfg.get('address', '') if proxy_cfg.get('enabled') else '',
        }
    except Exception as e:
        print(f"[警告] 读取配置失败: {e}，使用默认配置", file=sys.stderr)
        return defaults


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
        with open(PRICE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_state(data):
    """保存监控状态"""
    with open(PRICE_FILE, 'w') as f:
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


def make_state(base_price, peak, valley, time_str):
    """构造状态字典"""
    return {
        'base_price': base_price,
        'peak': peak,
        'valley': valley,
        'time': time_str
    }


def pct_str(value):
    """格式化百分比，带正负号"""
    return f"{'+' if value >= 0 else ''}{value*100:.2f}%"


def check_price(config):
    """
    核心监控逻辑 — 双极追踪

    追踪上次推送以来的最高价(peak)和最低价(valley)，三种通知条件：
    1. 趋势突破：价格从基准价涨/跌超过阈值
    2. 反转信号：价格从极值反转超过阈值（趋势方向回调）
    3. 高波动区间：peak-valley 波动超过 2× 阈值

    每次通知后重置基准为当前价格。
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 获取当前价格
    current_price, raw_data, err = get_price(config)
    if current_price is None:
        msg = err if err else "获取价格为空"
        send_bark(config, "❌ 积存金监控异常", f"原因: {msg}\n时间: {now}")
        return

    # 加载或初始化状态
    state = load_state()
    if state is None or state.get('base_price') is None:
        new_state = make_state(current_price, current_price, current_price, now)
        save_state(new_state)
        send_bark(config, "✅ 积存金监控启动",
                  f"基准价: {current_price}元/克\n时间: {now}")
        return

    base = state['base_price']
    peak = state.get('peak', base)
    valley = state.get('valley', base)
    threshold = config['threshold']

    # 更新极值
    peak = max(peak, current_price)
    valley = min(valley, current_price)

    change_pct = (current_price - base) / base         # 相对基准涨跌幅
    peak_retrace = (peak - current_price) / peak        # 从最高点回撤幅度
    valley_bounce = (current_price - valley) / valley   # 从最低点反弹幅度
    volatility = (peak - valley) / valley               # 区间波动幅度

    title = None
    content = None

    # ---- 条件1：高波动区间（区间波幅 ≥ 阈值，但净值变化小）----
    if volatility >= threshold and abs(change_pct) < threshold:
        title = f"🔄 积存金剧烈波动 ±{volatility*100:.1f}%"
        content = (f"当前: {current_price}元/克\n"
                   f"最高: {peak}元/克\n"
                   f"最低: {valley}元/克\n"
                   f"波幅: ±{volatility*100:.2f}%\n"
                   f"基准: {base}元/克\n"
                   f"时间: {now}")

    # ---- 条件2：反转信号（从极值反转超过阈值）----
    # 上涨后回撤：peak 曾高出基准 ≥ 阈值，且从 peak 回撤 ≥ 阈值
    elif (peak >= base * (1 + threshold)
          and peak_retrace >= threshold):
        title = f"⚠️ 积存金冲高回落 {pct_str(-peak_retrace)}"
        content = (f"当前: {current_price}元/克\n"
                   f"高点: {peak}元/克\n"
                   f"回撤: {pct_str(-peak_retrace)}\n"
                   f"仍较基准: {pct_str(change_pct)}\n"
                   f"时间: {now}")

    # 下跌后反弹：valley 曾低于基准 ≥ 阈值，且从 valley 反弹 ≥ 阈值
    elif (valley <= base * (1 - threshold)
          and valley_bounce >= threshold):
        title = f"⚠️ 积存金探底反弹 {pct_str(valley_bounce)}"
        content = (f"当前: {current_price}元/克\n"
                   f"低点: {valley}元/克\n"
                   f"反弹: {pct_str(valley_bounce)}\n"
                   f"仍较基准: {pct_str(change_pct)}\n"
                   f"时间: {now}")

    # ---- 条件3：趋势突破（净涨/跌幅超过阈值，兜底）----
    elif change_pct >= threshold:
        title = f"📈 积存金上涨 {pct_str(change_pct)}"
        content = (f"当前: {current_price}元/克\n"
                   f"基准: {base}元/克（上次推送价）\n"
                   f"涨幅: {pct_str(change_pct)}\n"
                   f"时间: {now}")

    elif change_pct <= -threshold:
        title = f"📉 积存金下跌 {pct_str(change_pct)}"
        content = (f"当前: {current_price}元/克\n"
                   f"基准: {base}元/克（上次推送价）\n"
                   f"跌幅: {pct_str(change_pct)}\n"
                   f"时间: {now}")

    # ---- 有通知则发送并重置状态 ----
    if title and content:
        send_bark(config, title, content)
        # 重置：基准设为当前价格，极值也归位
        new_state = make_state(current_price, current_price, current_price, now)
        save_state(new_state)
    else:
        # 无通知，只更新极值和价格
        new_state = make_state(base, peak, valley, now)
        save_state(new_state)


def main():
    config = load_config()
    check_price(config)


if __name__ == "__main__":
    main()
