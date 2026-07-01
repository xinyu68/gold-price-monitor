"""
金价监控脚本 — 趋势策略 + Bark 推送

功能：
  - 每次执行获取最新金价（通过 jin10_client.py）
  - 趋势状态机：识别趋势启动/延续/回调/反弹
  - 里程碑通知：趋势每推进 1% 推送一次
  - Bark 推送：先直连，失败再用代理

配合 cron job 使用：
  schedule: "*/10 * * * *"
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
        'trend_threshold': 0.01,
        'retrace_threshold': 0.01,
        'milestone_step': 0.01,
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

        return {
            'python_exe': sys.executable,
            'bark_key': bark.get('key', defaults['bark_key']),
            'quote_code': monitor.get('quote_code', defaults['quote_code']),
            'trend_threshold': monitor.get('trend_threshold', defaults['trend_threshold']),
            'retrace_threshold': monitor.get('retrace_threshold', defaults['retrace_threshold']),
            'milestone_step': monitor.get('milestone_step', defaults['milestone_step']),
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
        # 注意：字段嵌套在 data.* 下
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


def load_trend_data():
    """读取趋势状态数据"""
    try:
        with open(PRICE_FILE, 'r') as f:
            data = json.load(f)
            return {
                'price': data.get('price'),
                'base_price': data.get('base_price'),
                'trend_direction': data.get('trend_direction'),
                'trend_peak': data.get('trend_peak'),
                'trend_valley': data.get('trend_valley'),
                'last_milestone': data.get('last_milestone', 0),
                'time': data.get('time')
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_trend_data(data):
    """保存趋势状态数据"""
    with open(PRICE_FILE, 'w') as f:
        json.dump(data, f)


def send_bark(config, title, content):
    """通过 Bark 推送消息（有代理走代理，否则直连）"""
    bark_key = config.get('bark_key', '')
    if not bark_key:
        print("[Bark] 未配置 bark.key，跳过推送", file=sys.stderr)
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
        print(f"[Bark推送失败] {e}", file=sys.stderr)
        return False


def check_milestone(base_price, current_price, direction, last_milestone, milestone_step):
    """检查是否跨越新的里程碑"""
    if direction == 'up':
        change_pct = (current_price - base_price) / base_price
    else:
        change_pct = (base_price - current_price) / base_price

    current_milestone = int(change_pct / milestone_step) * milestone_step

    if current_milestone > last_milestone and current_milestone >= milestone_step:
        return current_milestone, change_pct
    return None, change_pct


def main():
    config = load_config()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 获取当前价格
    current_price, raw_data, err = get_price(config)

    if current_price is None:
        msg = err if err else "获取价格为空"
        send_bark(config, "❌ 积存金监控异常", f"原因: {msg}\n时间: {now}")
        print(f"[异常] {msg}")
        sys.exit(1)

    # 读取趋势数据
    trend_data = load_trend_data()

    if trend_data is None or trend_data.get('base_price') is None:
        # 首次运行，初始化
        new_data = {
            'price': current_price,
            'base_price': current_price,
            'trend_direction': None,
            'trend_peak': current_price,
            'trend_valley': current_price,
            'last_milestone': 0,
            'time': now
        }
        save_trend_data(new_data)
        send_bark(config, "✅ 积存金监控初始化",
                   f"首次启动，基准价: {current_price}元/克\n时间: {now}")
        print(f"[初始化] 基准价: {current_price}元/克")
        sys.exit(0)

    base_price = trend_data['base_price']
    trend_direction = trend_data['trend_direction']
    trend_peak = trend_data.get('trend_peak', base_price)
    trend_valley = trend_data.get('trend_valley', base_price)
    last_milestone = trend_data.get('last_milestone', 0)

    trend_threshold = config['trend_threshold']
    retrace_threshold = config['retrace_threshold']
    milestone_step = config['milestone_step']

    change_pct = (current_price - base_price) / base_price

    # 情况1：没有趋势，检查是否启动新趋势
    if trend_direction is None:
        if abs(change_pct) >= trend_threshold:
            milestone = int(abs(change_pct) / milestone_step) * milestone_step

            if change_pct > 0:
                new_data = {
                    'price': current_price, 'base_price': base_price,
                    'trend_direction': 'up', 'trend_peak': current_price,
                    'trend_valley': base_price, 'last_milestone': milestone,
                    'time': now
                }
                title = "📈积存金进入上涨趋势"
            else:
                new_data = {
                    'price': current_price, 'base_price': base_price,
                    'trend_direction': 'down', 'trend_peak': base_price,
                    'trend_valley': current_price, 'last_milestone': milestone,
                    'time': now
                }
                title = "📉积存金进入下跌趋势"

            content = (f"当前累计{'上涨' if change_pct > 0 else '下跌'}："
                       f"{'+' if change_pct > 0 else '-'}{abs(change_pct)*100:.2f}%\n"
                       f"当前: {current_price}元/克\n"
                       f"基准: {base_price}元/克\n"
                       f"时间: {now}")
            send_bark(config, title, content)
            save_trend_data(new_data)
            print(f"[通知] {title}")
        else:
            trend_data['price'] = current_price
            trend_data['time'] = now
            save_trend_data(trend_data)
            print(f"[正常] 当前: {current_price}元/克, 变动: {change_pct*100:+.2f}%")

    # 情况2：上涨趋势中
    elif trend_direction == 'up':
        if current_price > trend_peak:
            new_milestone, total_change = check_milestone(
                base_price, current_price, 'up', last_milestone, milestone_step)

            if new_milestone:
                title = f"📈积存金持续上涨 +{total_change*100:.1f}%"
                content = (f"当前: {current_price}元/克\n"
                           f"基准: {base_price}元/克\n"
                           f"累计: {total_change*100:+.2f}%\n"
                           f"时间: {now}")
                send_bark(config, title, content)
                trend_data['last_milestone'] = new_milestone
                print(f"[里程碑] 上涨 {new_milestone*100:.0f}%")

            trend_data['price'] = current_price
            trend_data['trend_peak'] = current_price
            trend_data['time'] = now
            save_trend_data(trend_data)
            print(f"[趋势延续] 上涨趋势创新高: {current_price}元/克")
        else:
            retrace_pct = (trend_peak - current_price) / trend_peak
            if retrace_pct >= retrace_threshold:
                new_data = {
                    'price': current_price, 'base_price': current_price,
                    'trend_direction': None, 'trend_peak': current_price,
                    'trend_valley': current_price, 'last_milestone': 0,
                    'time': now
                }
                title = f"⚠️积存金上涨回调 -{retrace_pct*100:.1f}%"
                content = (f"当前: {current_price}元/克\n"
                           f"高点: {trend_peak}元/克\n"
                           f"回撤: -{retrace_pct*100:.2f}%\n"
                           f"时间: {now}")
                send_bark(config, title, content)
                save_trend_data(new_data)
                print(f"[通知] {title}")
            else:
                trend_data['price'] = current_price
                trend_data['time'] = now
                save_trend_data(trend_data)
                print(f"[小幅回调] 当前: {current_price}元/克, 回撤: -{retrace_pct*100:.2f}%")

    # 情况3：下跌趋势中
    elif trend_direction == 'down':
        if current_price < trend_valley:
            new_milestone, total_change = check_milestone(
                base_price, current_price, 'down', last_milestone, milestone_step)

            if new_milestone:
                title = f"📉积存金持续下跌 -{total_change*100:.1f}%"
                content = (f"当前: {current_price}元/克\n"
                           f"基准: {base_price}元/克\n"
                           f"累计: -{total_change*100:.2f}%\n"
                           f"时间: {now}")
                send_bark(config, title, content)
                trend_data['last_milestone'] = new_milestone
                print(f"[里程碑] 下跌 {new_milestone*100:.0f}%")

            trend_data['price'] = current_price
            trend_data['trend_valley'] = current_price
            trend_data['time'] = now
            save_trend_data(trend_data)
            print(f"[趋势延续] 下跌趋势创新低: {current_price}元/克")
        else:
            bounce_pct = (current_price - trend_valley) / trend_valley
            if bounce_pct >= retrace_threshold:
                new_data = {
                    'price': current_price, 'base_price': current_price,
                    'trend_direction': None, 'trend_peak': current_price,
                    'trend_valley': current_price, 'last_milestone': 0,
                    'time': now
                }
                title = f"⚠️积存金下跌反弹 +{bounce_pct*100:.1f}%"
                content = (f"当前: {current_price}元/克\n"
                           f"低点: {trend_valley}元/克\n"
                           f"反弹: +{bounce_pct*100:.2f}%\n"
                           f"时间: {now}")
                send_bark(config, title, content)
                save_trend_data(new_data)
                print(f"[通知] {title}")
            else:
                trend_data['price'] = current_price
                trend_data['time'] = now
                save_trend_data(trend_data)
                print(f"[小幅反弹] 当前: {current_price}元/克, 反弹: +{bounce_pct*100:.2f}%")


if __name__ == "__main__":
    main()
