# 金价推送工具

基于 [Hermes Agent](https://hermes-agent.nousresearch.com) + [金十数据 MCP](https://mcp.jin10.com/app/) + [Bark](https://bark.day.app) 的金价实时监控与推送方案。

每 10 分钟自动查询金价，识别涨跌趋势，通过 Bark 推送通知到 iPhone。

## 架构总览

```
┌──────────────────────────────────────────────────────┐
│  Hermes Cron Job (*/10 * * * *)                      │
│                                                      │
│  gold_monitor.py                                     │
│    ├── 调用 jin10_client.py 获取实时金价              │
│    ├── 读取 gold_last_price.json（趋势状态）          │
│    ├── 趋势判断：启动/延续/回调/反弹                  │
│    └── 触发条件 → Bark 推送到 iPhone                  │
│                                                      │
│  jin10_client.py                                     │
│    └── MCP Streamable HTTP → 金十数据 API            │
└──────────────────────────────────────────────────────┘
```

**重要说明**：本项目的金十数据接入是**独立的 Python MCP 客户端**（`jin10_client.py`），不依赖 Hermes 的 MCP 配置。你只需要一个 Token 字符串，写入 `config.yaml` 即可。

---

## 前置条件

在开始之前，请确保你已经准备好以下内容：

| # | 需要准备 | 说明 | 获取方式 |
|---|---------|------|----------|
| 1 | **Hermes Agent** | 已安装并能正常运行 | [安装文档](https://hermes-agent.nousresearch.com/docs) |
| 2 | **Python 3.11+** | 运行监控脚本 | [python.org](https://www.python.org/downloads/) |
| 3 | **金十数据 MCP Token** | 获取实时金价，格式 `sk-xxx` | [金十数据](https://www.jin10.com) 注册后在开发者页面获取 |
| 4 | **Bark 推送 Key** | 推送通知到 iPhone | App Store 安装 Bark，打开即显示 Key |

> **只有 iPhone 需要 Bark**。Android 用户可以替换为其他推送服务（PushDeer、Server酱等），只需修改 `gold_monitor.py` 中的 `send_bark` 函数。

---

## 从零搭建指南（7 步）

### 第一步：准备 Python 环境

本项目需要 Python 3.11+。检查是否已安装：

```bash
python --version
```

如果提示找不到命令，去 [python.org](https://www.python.org/downloads/) 下载安装，安装时**勾选 "Add Python to PATH"**。

安装依赖：

```bash
pip install pyyaml
```

### 第二步：获取两个 Token

#### 2.1 金十数据 MCP Token

金十数据提供 MCP 财经数据服务，需要一个 Bearer Token 才能调用。

获取方式：
1. 访问 [金十数据](https://www.jin10.com) 注册/登录账号
2. 进入个人中心或开发者页面，获取 MCP 服务的 API Token
3. Token 格式为 `sk-xxxxxxxxxxxxxxxx`（以 `sk-` 开头的字符串）

> 如果找不到 Token 获取入口，可以访问 [mcp.jin10.com/app](https://mcp.jin10.com/app/) 获取。

#### 2.2 Bark 推送 Key

Bark 是 iOS 上的推送通知 App，用于接收金价提醒。

获取方式：
1. 在 iPhone 的 App Store 搜索安装 **Bark**
2. 打开 Bark App，首页会显示你的推送 Key（一串字母数字）
3. 复制这个 Key

> **网络说明**：Bark 的服务器 `api.day.app` 在中国大陆可直连，不需要科学上网。

### 第三步：配置

进入项目目录，复制配置模板并填入你的 Token：

```bash
# Windows
copy config_template.yaml config.yaml

# macOS / Linux
cp config_template.yaml config.yaml
```

编辑 `config.yaml`，填入你在第二步获取的 Token：

```yaml
jin10:
  url: "https://mcp.jin10.com/mcp"
  token: "sk-你的金十数据Token"     # ← 替换这里

bark:
  key: "你的Bark推送Key"            # ← 替换这里

monitor:
  quote_code: "CZBJCJ"              # 品种代码，见下方表格
  trend_threshold: 0.01             # 趋势启动阈值（1%）
  retrace_threshold: 0.01           # 回调/反弹阈值（1%）
  milestone_step: 0.01              # 里程碑步长（1%）

proxy:
  enabled: false                    # 通常不需要改
  address: "http://127.0.0.1:7897"
```

**常用品种代码**：

| 代码 | 品种 | 计价 |
|------|------|------|
| `CZBJCJ` | 浙商积存金 | 人民币/克 |
| `ICBCRYJCJ` | 工行如意积存金 | 人民币/克 |
| `ZHJCJ` | 招行积存金 | 人民币/克 |
| `XAUUSD` | 现货黄金 | 美元/盎司 |
| `XAGUSD` | 现货白银 | 美元/盎司 |
| `USOIL` | WTI 原油 | 美元/桶 |

### 第四步：安装到 Hermes

运行一键安装脚本，将 MCP 客户端和 skill 安装到 Hermes：

```bash
python install.py
```

这会自动完成：
- 复制 `jin10_client.py` 到 Hermes 的 scripts 目录
- 复制 `gold_monitor.py` 到 Hermes 的 scripts 目录
- 安装 `jin10-mcp` skill 到 Hermes 的 skills 目录（之后在 Hermes 中可以直接问"黄金多少钱"）

安装后你可以验证 skill 是否生效：在 Hermes 对话中问 **"黄金现在什么价"**，Hermes 应该会自动调用金十数据获取报价。

### 第五步：验证环境

运行检查脚本，自动验证 Python、依赖、配置、网络连通性：

```bash
python scripts/check_env.py
```

预期输出：
```
[✓] Python 3.11.15
[✓] pyyaml 已安装
[✓] config.yaml 已配置（Token 长度: 32）
[✓] 金十数据 MCP 连接成功（CZBJCJ: 879.42 元/克）
[✓] Bark 推送测试成功
[✓] 全部通过！可以运行 gold_monitor.py 了
```

如果某一步失败，脚本会给出修复建议。

### 第六步：手动运行一次

```bash
python scripts/gold_monitor.py
```

首次运行会：
1. 获取当前金价
2. 初始化基准价（保存到 `scripts/gold_last_price.json`）
3. 通过 Bark 推送一条"监控初始化"消息

看到 iPhone 收到通知，说明一切正常。

### 第七步：创建定时任务

在 Hermes Agent 的对话中发送以下命令（直接复制粘贴）：

```
创建定时任务：
- name: 金价监控
- schedule: "*/10 * * * *"
- script: gold_monitor.py
- no_agent: true
- deliver: local
```

Hermes 会返回一个 `job_id`，之后每 10 分钟自动执行。

验证任务已创建：

```
列出所有定时任务
```

你应该能看到 `金价监控` 任务，状态为 `scheduled`，下次执行时间在 10 分钟内。

---

## 项目结构

```
gold-price-monitor/
├── README.md                    # 本文档
├── install.py                   # 一键安装到 Hermes（脚本 + skill）
├── config_template.yaml         # 配置模板（不含真实 Token）
├── requirements.txt             # Python 依赖
├── .gitignore                   # Git 忽略规则（config.yaml 不会被提交）
├── skill/
│   └── SKILL.md                 # 金十数据 MCP skill（安装后 Hermes 可直接查金价）
└── scripts/
    ├── jin10_client.py          # 金十数据 MCP 客户端（独立实现，不依赖 Hermes MCP）
    ├── gold_monitor.py          # 金价监控 + Bark 推送脚本
    └── check_env.py             # 环境检查脚本
```

## 推送效果

### 趋势启动
```
📈积存金进入上涨趋势
当前累计上涨：+1.02%
当前: 887.50元/克
基准: 878.60元/克
时间: 2026-06-30 15:30:00
```

### 里程碑通知
```
📈积存金持续上涨 +2.1%
当前: 897.00元/克
基准: 878.60元/克
累计: +2.10%
时间: 2026-06-30 17:00:00
```

### 回调通知
```
⚠️积存金上涨回调 -1.2%
当前: 886.00元/克
高点: 897.00元/克
回撤: -1.23%
时间: 2026-06-30 18:30:00
```

### 异常告警
```
❌ 积存金监控异常
原因: jin10_client执行失败
时间: 2026-06-30 19:00:00
```

## 监控策略

采用**趋势状态机**策略，避免频繁通知：

```
无趋势 ──→ 涨幅 ≥ 1% ──→ 上涨趋势
  ↑                           │
  │                           ├── 创新高：继续观察（不通知）
  │                           └── 回撤 ≥ 1%：通知回调，重置
  │
  └──→ 跌幅 ≥ 1% ──→ 下跌趋势
                          │
                          ├── 创新低：继续观察（不通知）
                          └── 反弹 ≥ 1%：通知反弹，重置
```

- **趋势启动**：涨/跌幅首次超过阈值 → 推送通知
- **趋势延续**：持续创新高/新低 → 每跨越一个里程碑通知一次
- **趋势结束**：回调/反弹超过阈值 → 推送通知，重置基准价

## MCP 技术细节

本项目通过 MCP (Model Context Protocol) Streamable HTTP 协议接入金十数据。

### 协议流程

```
Client                          Server (mcp.jin10.com)
  |--- initialize ------------>  |
  |<-- Mcp-Session-Id + caps    |
  |--- notifications/initialized->|
  |--- tools/call (get_quote) -->|
  |<-- structuredContent --------|
```

关键点：
1. `initialize` 响应包含 `Mcp-Session-Id` 头，后续请求必须携带
2. 响应格式为 SSE（`text/event-stream`），需解析 `data:` 行
3. 请求头必须包含 `Accept: application/json, text/event-stream`
4. 数据优先从 `result.structuredContent` 读取

### 可用工具

| 工具 | 功能 | 示例 |
|------|------|------|
| `get_quote` | 实时行情 | `python jin10_client.py quote XAUUSD` |
| `get_kline` | K线数据 | `python jin10_client.py kline XAUUSD` |
| `list_flash` | 最新快讯 | `python jin10_client.py flash` |
| `search_flash` | 搜索快讯 | `python jin10_client.py flash 黄金` |
| `list_news` | 资讯列表 | `python jin10_client.py news` |
| `search_news` | 搜索资讯 | `python jin10_client.py news 美联储` |
| `get_news` | 资讯详情 | `python jin10_client.py news_detail <id>` |
| `list_calendar` | 财经日历 | `python jin10_client.py calendar` |

## 常见问题

### Q: 定时任务只执行一次就消失了？

你用了 `schedule: "10m"`（一次性延迟），应改用 `schedule: "*/10 * * * *"`（cron 表达式）。

### Q: Bark 推送收不到？

1. 确认 Bark App 已安装且通知权限已开启
2. 测试直连：`curl https://api.day.app/{你的Key}/test/test`
3. 如果直连不通，检查是否需要在 `config.yaml` 中开启代理

### Q: 金十数据获取价格失败？

1. 检查 `config.yaml` 中的 Token 是否正确（以 `sk-` 开头）
2. 测试连接：`python scripts/jin10_client.py quote XAUUSD`
3. 如果返回 401，Token 可能过期，需重新获取

### Q: Windows 上 Python 路径问题？

`gold_monitor.py` 使用 `sys.executable` 自动获取当前 Python 路径，通常不需要手动配置。如果仍有问题，检查 `python --version` 是否返回 3.11+。

### Q: 不用 Hermes，能用系统定时任务吗？

可以。脚本本身不依赖 Hermes，只要能定时执行 `python scripts/gold_monitor.py` 即可。

**Windows 任务计划程序**：
1. 打开"任务计划程序"（Win+R 输入 `taskschd.msc`）
2. 创建基本任务 → 设置每 10 分钟触发
3. 操作选"启动程序"，填入 Python 路径和脚本路径

**Linux/macOS crontab**：
```bash
crontab -e
# 添加：
*/10 * * * * cd /path/to/gold-price-monitor && python scripts/gold_monitor.py
```

## License

MIT
