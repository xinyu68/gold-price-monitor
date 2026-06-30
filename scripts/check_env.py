"""
环境检查脚本 — 验证金价推送工具所需的一切是否就绪

运行：python scripts/check_env.py
"""
import sys
import os
import json
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, '..')
CONFIG_FILE = os.path.join(PROJECT_DIR, 'config.yaml')
JIN10_CLIENT = os.path.join(SCRIPT_DIR, 'jin10_client.py')

PASS = "\033[32m[✓]\033[0m"
FAIL = "\033[31m[✗]\033[0m"
WARN = "\033[33m[!]\033[0m"


def check_python():
    """检查 Python 版本"""
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v.major >= 3 and v.minor >= 11:
        print(f"{PASS} Python {ver}")
        return True
    else:
        print(f"{FAIL} Python {ver}（需要 3.11+）")
        print(f"   下载：https://www.python.org/downloads/")
        return False


def check_pyyaml():
    """检查 pyyaml 是否安装"""
    try:
        import yaml
        print(f"{PASS} pyyaml 已安装")
        return True
    except ImportError:
        print(f"{FAIL} pyyaml 未安装")
        print(f"   修复：pip install pyyaml")
        return False


def check_config():
    """检查 config.yaml 是否存在且配置正确"""
    if not os.path.isfile(CONFIG_FILE):
        print(f"{FAIL} config.yaml 不存在")
        print(f"   修复：copy config_template.yaml config.yaml，然后填入 Token")
        return False

    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"{FAIL} config.yaml 解析失败：{e}")
        return False

    errors = []

    # 检查 jin10 token
    jin10 = config.get('jin10', {})
    token = jin10.get('token', '')
    if not token or token.startswith('sk-你的'):
        errors.append("jin10.token 未配置（需要填入金十数据 MCP Token）")
    else:
        print(f"{PASS} 金十数据 Token 已配置（长度: {len(token)}）")

    # 检查 bark key
    bark = config.get('bark', {})
    bark_key = bark.get('key', '')
    if not bark_key or bark_key.startswith('你的'):
        errors.append("bark.key 未配置（需要填入 Bark 推送 Key）")
    else:
        print(f"{PASS} Bark Key 已配置（长度: {len(bark_key)}）")

    # 检查品种代码
    monitor = config.get('monitor', {})
    code = monitor.get('quote_code', '')
    if code:
        print(f"{PASS} 品种代码：{code}")
    else:
        print(f"{WARN} 未配置品种代码，将使用默认值 CZBJCJ")

    if errors:
        for e in errors:
            print(f"{FAIL} {e}")
        return False

    return True


def check_jin10_connection():
    """测试金十数据 MCP 连接"""
    try:
        result = subprocess.run(
            [sys.executable, JIN10_CLIENT, 'quote', 'CZBJCJ'],
            capture_output=True, text=True, timeout=30,
            cwd=PROJECT_DIR
        )
        if result.returncode != 0:
            print(f"{FAIL} 金十数据连接失败：{result.stderr.strip()}")
            return False

        data = json.loads(result.stdout)
        inner = data.get('data', data)
        price = inner.get('close') or inner.get('last') or inner.get('price')
        name = inner.get('name', 'CZBJCJ')

        if price:
            print(f"{PASS} 金十数据连接成功（{name}: {price} 元/克）")
            return True
        else:
            print(f"{FAIL} 金十数据返回数据异常：{json.dumps(data, ensure_ascii=False)[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"{FAIL} 金十数据连接超时（30秒）")
        return False
    except FileNotFoundError:
        print(f"{FAIL} jin10_client.py 不存在：{JIN10_CLIENT}")
        return False
    except json.JSONDecodeError:
        print(f"{FAIL} 金十数据返回数据解析失败")
        return False
    except Exception as e:
        print(f"{FAIL} 金十数据连接异常：{e}")
        return False


def check_bark():
    """测试 Bark 推送"""
    try:
        import yaml
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        bark_key = config.get('bark', {}).get('key', '')
        if not bark_key or bark_key.startswith('你的'):
            print(f"{WARN} 跳过 Bark 测试（未配置 Key）")
            return False

        from urllib.request import urlopen, Request, ProxyHandler, build_opener
        from urllib.parse import quote

        title = quote("测试推送")
        content = quote("环境检查通过")
        url = f"https://api.day.app/{bark_key}/{title}/{content}"
        req = Request(url, method='GET')
        req.add_header('User-Agent', 'Mozilla/5.0')

        try:
            resp = urlopen(req, timeout=10)
            print(f"{PASS} Bark 推送测试成功（直连）")
            return True
        except Exception:
            # 尝试代理
            proxy = config.get('proxy', {})
            if proxy.get('enabled'):
                proxy_handler = ProxyHandler({
                    'http': proxy.get('address', ''),
                    'https': proxy.get('address', '')
                })
                opener = build_opener(proxy_handler)
                resp = opener.open(req, timeout=15)
                print(f"{PASS} Bark 推送测试成功（通过代理）")
                return True
            else:
                print(f"{FAIL} Bark 推送失败（直连不通，未配置代理）")
                return False

    except Exception as e:
        print(f"{FAIL} Bark 测试异常：{e}")
        return False


def main():
    print("=" * 50)
    print("金价推送工具 — 环境检查")
    print("=" * 50)
    print()

    results = []

    print("--- 基础环境 ---")
    results.append(("Python", check_python()))
    results.append(("pyyaml", check_pyyaml()))
    print()

    print("--- 配置文件 ---")
    config_ok = check_config()
    results.append(("config.yaml", config_ok))
    print()

    if config_ok:
        print("--- 网络连通性 ---")
        results.append(("金十数据 MCP", check_jin10_connection()))
        results.append(("Bark 推送", check_bark()))
        print()

    # 总结
    print("=" * 50)
    all_pass = all(ok for _, ok in results)
    failed = [name for name, ok in results if not ok]

    if all_pass:
        print(f"{PASS} 全部通过！可以运行 gold_monitor.py 了")
        print()
        print("下一步：")
        print("  1. 运行 python scripts/gold_monitor.py 测试一次")
        print("  2. 在 Hermes 中创建定时任务")
    else:
        print(f"{FAIL} 有 {len(failed)} 项未通过：{', '.join(failed)}")
        print()
        print("请根据上方提示修复后重新运行检查。")

    print()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
