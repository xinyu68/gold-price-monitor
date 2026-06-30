# Gold Price Monitor — MCP + AI Agent 金价智能监控

基于 **MCP 协议 + AI Agent 编排 + Bark 推送** 的金价智能监控方案。

> 传统金价监控用 REST API + cron + 邮件；这个项目用 **MCP 原生设计**，让 AI Agent 能直接查询金融数据、推理趋势、触发通知——更智能、可组合、可扩展。

## 为什么做这个

金价监控脚本 GitHub 上很多，但大多是传统模式：

```
传统：  [REST API] → [Python 脚本] → [系统 Cron] → [邮件/Telegram]
本项目：[MCP 数据源] → [AI Agent 编排] → [Bark 推送] → [iPhone]
```

**MCP 原生**意味着：
- 金融数据对 AI Agent **可查询、可推理、可组合**
- 不是写死的脚本，Agent 可以根据上下文决定查什么、怎么通知
- 天然兼容所有支持 MCP 的 AI 框架（Hermes、Claude、Cursor 等）

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent (Cron Job)                                │
│                                                         │
│  gold_monitor.py                                        │
│    ├── jin10_client.py ──→ MCP Streamable HTTP          │
│    │                        └── 金十数据 API            │
│    ├── 趋势状态机（启动/延续/回调/反弹）                │
│    └── 触发条件 ──→ Bark 推送 ──→ iPhone                │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

| 组件 | 技术 | 作用 |
|------|------|------|
| 数据源 | [金十数据 MCP](https://mcp.jin10.com/app/) | 实时金价、K线、快讯、财经日历 |
| 编排层 | [Hermes Agent](https://hermes-agent.nousresearch.com) | 定时任务、AI 推理、错误处理 |
| 推送层 | [Bark](https://bark.day.app) | iOS 推送通知（国内直连） |
| 协议 | MCP Streamable HTTP | AI Agent 原生数据接口 |

## 监控策略

采用**趋势状态机**，避免频繁刷通知：

```
无趋势 ──→ 涨幅 ≥ 1% ──→ 上涨趋势
  ↑                           │
  │                           ├── 创新高：继续观察（不通知）
  │                           └── 回撤 ≥ 1%：通知回调，重置
  └──→ 跌幅 ≥ 1% ──→ 下跌趋势
                          ├── 创新低：继续观察（不通知）
                          └── 反弹 ≥ 1%：通知反弹，重置
```

## 推送效果

```
📈积存金进入上涨趋势
当前累计上涨：+1.02%
当前: 887.50元/克
基准: 878.60元/克
时间: 2026-06-30 15:30:00
```

```
❌ 积存金监控异常
原因: jin10_client执行失败
时间: 2026-06-30 19:00:00
```

## 从零搭建（7 步）

### 前置条件

| # | 需要准备 | 说明 | 获取方式 |
|---|---------|------|----------|
| 1 | **Hermes Agent** | AI Agent 框架 | [安装文档](https://hermes-agent.nousresearch.com/docs) |
| 2 | **Python 3.11+** | 运行脚本 | [python.org](https://www.python.org/downloads/) |
| 3 | **金十数据 Token** | 格式 `sk-xxx` | [mcp.jin10.com/app](https://mcp.jin10.com/app/) |
| 4 | **Bark Key** | iOS 推送 | App Store 安装 Bark |

### Step 1: 准备环境

```bash
python --version          # 确认 3.11+
pip install pyyaml
```

### Step 2: 获取 Token

- **金十数据**：访问 [mcp.jin10.com/app](https://mcp.jin10.com/app/)，注册后获取 MCP Token（`sk-xxx`）
- **Bark**：iPhone 安装 Bark，打开即显示 Key

### Step 3: 配置

```bash
cp config_template.yaml config.yaml   # Windows: copy
```

编辑 `config.yaml`，填入 Token：

```yaml
jin10:
  url: "https://mcp.jin10.com/mcp"
  token: "sk-你的Token"

bark:
  key: "你的BarkKey"

monitor:
  quote_code: "CZBJCJ"       # 浙商积存金（人民币/克）
  trend_threshold: 0.01      # 趋势阈值 1%
```

**常用品种代码**：`CZBJCJ`（浙商积存金）、`ICBCRYJCJ`（工行如意积存金）、`XAUUSD`（现货黄金/美元）

### Step 4: 安装到 Hermes

```bash
python install.py
```

自动复制脚本 + skill 到 Hermes 目录。

### Step 5: 验证环境

```bash
python scripts/check_env.py
```

预期输出：Python ✓、依赖 ✓、Token ✓、金十连接 ✓、Bark ✓

### Step 6: 手动测试

```bash
python scripts/gold_monitor.py
```

首次运行初始化基准价，iPhone 应收到 Bark 通知。

### Step 7: 创建定时任务

在 Hermes 对话中：

```
创建定时任务：
- name: 金价监控
- schedule: "*/10 * * * *"
- script: gold_monitor.py
- no_agent: true
- deliver: local
```

## MCP 可用工具

本项目通过独立 Python MCP 客户端（`jin10_client.py`）调用金十数据，不依赖 Hermes 的 MCP 配置：

| 工具 | 命令 |
|------|------|
| 实时行情 | `python jin10_client.py quote XAUUSD` |
| K线数据 | `python jin10_client.py kline XAUUSD` |
| 最新快讯 | `python jin10_client.py flash` |
| 搜索快讯 | `python jin10_client.py flash 黄金` |
| 财经日历 | `python jin10_client.py calendar` |

## 项目结构

```
gold-price-monitor/
├── README.md
├── install.py                # 一键安装到 Hermes
├── config_template.yaml      # 配置模板
├── requirements.txt
├── .gitignore
├── skill/
│   └── SKILL.md              # 金十数据 MCP skill
└── scripts/
    ├── jin10_client.py       # 独立 MCP 客户端
    ├── gold_monitor.py       # 趋势监控 + Bark 推送
    └── check_env.py          # 环境检查
```

## 常见问题

**Q: 定时任务只执行一次就消失了？**
用 `schedule: "*/10 * * * *"`（cron 表达式），不要用 `schedule: "10m"`（一次性延迟）。

**Q: Bark 推送收不到？**
测试直连：`curl https://api.day.app/{你的Key}/test/test`

**Q: 金十数据获取失败？**
测试连接：`python scripts/jin10_client.py quote XAUUSD`

**Q: 不用 Hermes，能用系统定时任务吗？**
可以。脚本不依赖 Hermes，`crontab -e` 或 Windows 任务计划程序都行。

## License

MIT
