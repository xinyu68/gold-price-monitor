# Gold Price Monitor — MCP + AI Agent 金价智能监控

基于 **MCP 协议 + AI Agent 编排 + Bark 推送** 的金价智能监控方案。

> 传统金价监控用 REST API + cron + 邮件；这个项目用 **MCP 原生设计**，让 AI Agent 能直接查询金融数据、推理趋势、触发通知——更智能、可组合、可扩展。

## 让 Hermes Agent 搭建

把下面这段话复制给 Hermes Agent：

```
帮我搭建金价监控，参考 https://github.com/xinyu68/gold-price-monitor
```

Hermes 会自动克隆项目、安装依赖、配置定时任务，过程中会问你要所需的 Token。

**前置条件**：

| 需要准备 | 获取方式 |
|---------|----------|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| 金十数据 Token | [mcp.jin10.com/app](https://mcp.jin10.com/app/) 免费注册获取 |
| Bark Key（iOS 用户） | iPhone 安装 [Bark](https://bark.day.app)，打开即显示 |

---

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
| 推送层 | [Bark](https://bark.day.app) | iOS 推送通知（需代理访问） |
| 协议 | MCP Streamable HTTP | AI Agent 原生数据接口 |

## 监控策略

采用**趋势状态机**，避免频繁刷通知：

```
无趋势 ──→ 涨幅 ≥ 1% ──→ 上涨趋势（通知启动）
  ↑                           │
  │                           ├── 创新高 + 跨越里程碑 → 通知
  │                           ├── 创新高 + 未跨越里程碑 → 静默
  │                           └── 回撤 ≥ 1% → 通知回调，重置
  │
  └──→ 跌幅 ≥ 1% ──→ 下跌趋势（通知启动）
                          ├── 创新低 + 跨越里程碑 → 通知
                          ├── 创新低 + 未跨越里程碑 → 静默
                          └── 反弹 ≥ 1% → 通知反弹，重置
```

### 里程碑推送示例

假设基准价 880 元/克：

```
基准价: 880 元/克

10:00  885.0  → 涨 0.57%  → 未到 1%，不通知
10:10  889.0  → 涨 1.02%  → 跨越 1%，通知"进入上涨趋势" 📈
10:20  893.0  → 涨 1.48%  → 没到 2%，静默
10:30  897.0  → 涨 1.93%  → 没到 2%，静默
10:40  898.5  → 涨 2.10%  → 跨越 2%，通知"持续上涨 +2.1%" 📈
10:50  900.0  → 涨 2.27%  → 没到 3%，静默
11:00  907.0  → 涨 3.07%  → 跨越 3%，通知"持续上涨 +3.1%" 📈
11:10  903.0  → 涨 2.61%  → 回撤 0.44%，未到 1%，静默
11:20  896.0  → 涨 1.82%  → 从高点 907 回撤 1.21%，通知"上涨回调 -1.2%" ⚠️
```

里程碑是整数百分比的"台阶"（1%、2%、3%...），只有价格**跨过新台阶**才通知，减少通知噪音。

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
用 `schedule: "*/4 * * * *"`（cron 表达式），不要用 `schedule: "4m"`（一次性延迟）。

**Q: Bark 推送收不到？**
测试直连：`curl https://api.day.app/{你的Key}/test/test`

**Q: 金十数据获取失败？**
测试连接：`python scripts/jin10_client.py quote XAUUSD`

**Q: 不用 Hermes，能用系统定时任务吗？**
可以。脚本不依赖 Hermes，`crontab -e` 或 Windows 任务计划程序都行。

## License

MIT
