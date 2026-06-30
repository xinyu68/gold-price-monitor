---
name: jin10-mcp
description: 金十数据 MCP 财经数据服务 — 实时行情、K线、快讯、资讯、财经日历查询
triggers:
  - 黄金/白银/原油/外汇 行情报价
  - 积存金价格（招行/工行/民生/浙商）
  - 财经快讯/新闻搜索
  - 财经日历/数据日程
  - K线/走势数据
  - 任何涉及金融品种实时价格的查询
---

# 金十数据 MCP

## 概述

通过 MCP (Model Context Protocol) 接入金十数据，获取实时金融行情、财经快讯、深度资讯和财经日历。

**独立客户端**: `~/AppData/Local/hermes/scripts/jin10_client.py`
**配置文件**: 项目目录下的 `config.yaml`（或环境变量 `JIN10_TOKEN`）

## 使用方式

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py <command> [args]
```

---

## 支持的工具（8个）

### 1. get_quote — 实时行情报价

获取指定品种的实时行情（价格、成交量、涨跌幅等）。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py quote <code>
```

**返回字段**: `code`, `name`, `open`, `close`, `high`, `low`, `volume`, `ups_price`, `ups_percent`, `time`

**示例**:
```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py quote XAUUSD     # 现货黄金
python ~/AppData/Local/hermes/scripts/jin10_client.py quote ZHJCJ      # 招行积存金
python ~/AppData/Local/hermes/scripts/jin10_client.py quote USOIL      # WTI原油
python ~/AppData/Local/hermes/scripts/jin10_client.py quote USDCNH     # 美元/人民币
```

### 2. get_kline — K线数据

获取指定品种的分钟级K线数据。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py kline <code> [time] [count]
```

**参数**:
- `code`: 品种代码
- `time`: K线周期（如 `m30`, `h1`, `d1`），默认 `m30`
- `count`: 返回K线数量，默认 30

**返回字段**: 每根K线包含 `time`, `open`, `close`, `high`, `low`, `volume`

### 3. list_flash — 快讯列表

获取最新财经快讯，支持 cursor 分页。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py flash
```

**返回**: 最多 20 条快讯，含 `time` 和 `content`，支持 `next_cursor` 翻页。

### 4. search_flash — 搜索快讯

按关键词搜索快讯，最多返回 150 条，不支持翻页。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py flash <keyword>
```

**常用关键词**: `黄金`, `原油`, `美联储`, `日元`, `通胀`, `非农`, `日本央行`, `欧佩克`

### 5. list_news — 资讯列表

获取最新深度资讯文章，支持 cursor 分页。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py news
```

### 6. search_news — 搜索资讯

按关键词搜索深度资讯，支持 cursor 分页。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py news <keyword>
```

### 7. get_news — 资讯详情

根据文章 ID 获取完整文章内容。

**返回字段**: `id`, `title`, `introduction`, `time`, `url`, `content`

### 8. list_calendar — 财经日历

获取当前自然周（周一到周日）的财经日历数据。

```bash
python ~/AppData/Local/hermes/scripts/jin10_client.py calendar
```

**返回字段**: `pub_time`, `star`（重要程度1-3星）, `title`, `previous`（前值）, `consensus`（预期）, `actual`（实际）, `affect_txt`（影响说明）

---

## 支持的品种代码（97个）

### 积存金（5个）

| 代码 | 品种 |
|------|------|
| `ZHJCJ` | 招行积存金 |
| `ICBCJCJ` | 工行积存金 |
| `ICBCRYJCJ` | 工行如意积存金 |
| `CMBCJCJ` | 民生积存金 |
| `CZBJCJ` | 浙商积存金 |

### 现货贵金属（4个）

| 代码 | 品种 |
|------|------|
| `XAUUSD` | 现货黄金 |
| `XAGUSD` | 现货白银 |
| `XPTUSD` | 现货铂金 |
| `XPDUSD` | 现货钯金 |

### 大宗商品（5个）

| 代码 | 品种 |
|------|------|
| `USOIL` | WTI原油 |
| `UKOIL` | 布伦特原油 |
| `COPPER` | 现货铜 |
| `NGAS` | 天然气 |

### 外汇（9个）

| 代码 | 品种 |
|------|------|
| `EURUSD` | 欧元/美元 |
| `GBPUSD` | 英镑/美元 |
| `USDJPY` | 美元/日元 |
| `USDCNH` | 美元/人民币 |
| `USDCHF` | 美元/瑞郎 |
| `USDCAD` | 美元/加元 |
| `USDHKD` | 美元/港元 |
| `AUDUSD` | 澳元/美元 |
| `NZDUSD` | 纽元/美元 |

### 中国股指（5个）

| 代码 | 品种 |
|------|------|
| `000001` | 上证指数 |
| `399006` | 创业板指 |
| `000300` | 沪深300 |
| `399001` | 深证成指 |
| `899050` | 北证50 |

### 全球主要股指（10个）

| 代码 | 品种 |
|------|------|
| `HSI` | 恒生指数 |
| `DJI` | 道琼斯工业指数 |
| `SPX` | 标普500 |
| `N225` | 日经225 |
| `GDAXI` | 德国DAX30 |
| `FTSE` | 英国富时100 |
| `KS11` | 韩国KOSPI |
| `FCHI` | 法国CAC40 |
| `AXJO` | 澳大利亚ASX200 |
| `BVSP` | 巴西Bovespa |

### 工行账户产品（部分常用）

| 代码 | 品种 |
|------|------|
| `ICNYXAU` | 工行人民币账户黄金 |
| `IUSDXAU` | 工行美元账户黄金 |
| `ICNYXAG` | 工行人民币账户白银 |
| `IUSDXAG` | 工行美元账户白银 |
| `ICNYBRENT` | 工行人民币账户国际原油 |
| `ICNYWTI` | 工行人民币账户北美原油 |
| `IUSDGAS` | 工行美元账户天然气 |

### 暗盘参考价

| 代码 | 品种 |
|------|------|
| `PAXGUSD` | 暗金参考价 |
| `XAGXUSD` | 暗银参考价 |
| `USOILX` | 暗油参考价（WTI） |
| `UKOILX` | 暗油参考价（布伦特） |

---

## 常见使用场景

### 用户问"某个品种报价"
1. 根据品种名匹配代码（参考上方代码表）
2. 调用 `get_quote` 获取实时行情
3. 格式化展示价格、涨跌幅、高低点

### 用户问"某个主题的最新快讯"
1. 调用 `search_flash({ keyword })` 搜索关键词
2. 如果要浏览最新流，调用 `list_flash`，按 `next_cursor` 翻页

### 用户问"某个主题的深度文章"
1. 调用 `search_news({ keyword })` 搜索
2. 拿到 `id` 后调用 `get_news({ id })` 获取详情

### 用户问"财经日历/本周数据"
直接调用 `list_calendar`

### 用户问"某个品种最近走势"
1. 先确认品种代码
2. 调用 `get_kline` 获取K线数据
3. 分析趋势并给出解读

---

## Pitfalls

1. **响应结构嵌套在 `data.*` 下**：`jin10_client.py` 输出的 JSON 结构为 `{"data": {"close": "879.42", "code": "CZBJCJ", ...}, "status": 200}`，价格等字段在 `data` 对象内部，不是顶层字段。解析时必须用 `data.get("data", {}).get("close")` 而非 `data.get("close")`。否则会拿到 `None`。
2. **Windows 多 Python 版本**：`subprocess.run(["python", ...])` 可能调到错误的 Python 版本（如 3.14 而非 3.11），导致 `ModuleNotFoundError`。在 Hermes cron 会话中用 `sys.executable` 获取当前 Python 路径（推荐），或用完整路径。
3. **pyyaml 依赖**：`jin10_client.py` 依赖 `pyyaml`，需确保目标 Python 环境已安装 (`pip install pyyaml`)。
4. **快讯分页**: 使用 `cursor` 参数，响应含 `data.next_cursor` 和 `data.has_more`
5. **搜索限制**: `search_flash` 最多返回 150 条，不支持翻页
6. **品种代码查询**: 可通过 `resources/read` 访问 `quote://codes` 获取完整列表
