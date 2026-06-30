"""
金十数据 MCP 客户端 — 封装所有工具调用

用法:
    python jin10_client.py quote XAUUSD
    python jin10_client.py kline XAUUSD [time] [count]
    python jin10_client.py flash [keyword]
    python jin10_client.py news [keyword]
    python jin10_client.py news_detail <id>
    python jin10_client.py calendar
    python jin10_client.py codes

配置:
    自动读取脚本同目录下 ../config.yaml 中的 jin10 配置
    或通过环境变量 JIN10_TOKEN 指定 Token
"""
import json
import sys
import os
import http.client
from urllib.parse import urlparse

def find_config():
    """查找配置文件：优先当前目录，其次脚本所在目录的上级"""
    candidates = [
        os.path.join(os.getcwd(), 'config.yaml'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yaml'),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

def load_config():
    """加载金十数据配置，支持环境变量覆盖"""
    token = os.environ.get('JIN10_TOKEN')
    url = os.environ.get('JIN10_URL', 'https://mcp.jin10.com/mcp')

    if token:
        return url, f'Bearer {token}'

    config_path = find_config()
    if config_path:
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            jin10 = config.get('jin10', {})
            url = jin10.get('url', url)
            token = jin10.get('token', '')
            if token:
                return url, f'Bearer {token}' if not token.startswith('Bearer') else token
        except ImportError:
            pass  # pyyaml 未安装，跳过
        except Exception:
            pass

    print("错误：未找到金十数据 Token。请：", file=sys.stderr)
    print("  1. 创建 config.yaml 并配置 jin10.token", file=sys.stderr)
    print("  2. 或设置环境变量 JIN10_TOKEN", file=sys.stderr)
    sys.exit(1)


class MCPClient:
    """MCP Streamable HTTP 客户端"""

    def __init__(self, url, auth):
        self.parsed = urlparse(url)
        self.path = self.parsed.path
        self.auth = auth
        self.session_id = None
        self.call_id = 0
        self._initialized = False

    def _request(self, payload):
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": self.auth
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        conn = http.client.HTTPSConnection(self.parsed.hostname, timeout=20)
        conn.request("POST", self.path, body=data, headers=headers)
        resp = conn.getresponse()
        sid = resp.getheader("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        raw = resp.read().decode()
        status = resp.status
        conn.close()

        # 解析 SSE 格式
        for line in raw.split('\n'):
            if line.startswith('data: '):
                return json.loads(line[6:])
        if raw.strip():
            return json.loads(raw)
        return {"_status": status}

    def _ensure_init(self):
        """确保已完成 MCP 握手（initialize → notifications/initialized）"""
        if self._initialized:
            return
        self._request({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "jin10-client", "version": "1.0.0"}
            }
        })
        self._request({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def call_tool(self, name, arguments=None):
        self._ensure_init()
        self.call_id += 1
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        r = self._request({
            "jsonrpc": "2.0", "id": self.call_id,
            "method": "tools/call", "params": params
        })
        sc = r.get('result', {}).get('structuredContent', {})
        content = r.get('result', {}).get('content', [])
        return sc if sc else content

    def read_resource(self, uri):
        self._ensure_init()
        self.call_id += 1
        r = self._request({
            "jsonrpc": "2.0", "id": self.call_id,
            "method": "resources/read", "params": {"uri": uri}
        })
        return r.get('result', {})


def main():
    url, auth = load_config()
    client = MCPClient(url, auth)

    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "quote":
        code = sys.argv[2] if len(sys.argv) > 2 else "XAUUSD"
        result = client.call_tool("get_quote", {"code": code})
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "kline":
        code = sys.argv[2] if len(sys.argv) > 2 else "XAUUSD"
        args = {"code": code}
        if len(sys.argv) > 3: args["time"] = sys.argv[3]
        if len(sys.argv) > 4: args["count"] = int(sys.argv[4])
        result = client.call_tool("get_kline", args)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "flash":
        keyword = sys.argv[2] if len(sys.argv) > 2 else None
        if keyword:
            result = client.call_tool("search_flash", {"keyword": keyword})
        else:
            result = client.call_tool("list_flash", {})
        items = result.get('data', {}).get('items', [])
        for item in items[:20]:
            print(f"[{item.get('time', '')}] {item.get('content', '')[:150]}")

    elif cmd == "news":
        keyword = sys.argv[2] if len(sys.argv) > 2 else None
        if keyword:
            result = client.call_tool("search_news", {"keyword": keyword})
        else:
            result = client.call_tool("list_news", {})
        items = result.get('data', {}).get('items', [])
        for item in items[:20]:
            print(f"[{item.get('time', '')}] {item.get('title', '')}")

    elif cmd == "news_detail":
        news_id = sys.argv[2]
        result = client.call_tool("get_news", {"id": news_id})
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "calendar":
        result = client.call_tool("list_calendar", {})
        events = result.get('data', [])
        for ev in events[:30]:
            star = "⭐" * ev.get('star', 0)
            actual = ev.get('actual', '')
            flag = "✅" if actual else "⏳"
            print(f"{flag} {ev.get('pub_time', '')} {star} {ev.get('title', '')} | "
                  f"前:{ev.get('previous', '')} 预:{ev.get('consensus', '')} 实:{actual}")

    elif cmd == "codes":
        result = client.read_resource("quote://codes")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
