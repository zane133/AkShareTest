# AkShare 本地脚本集

本仓库是在 [AkShare](https://github.com/akfamily/akshare) 之上写的两个小工具：A 股条件筛选，以及对固定股票池的近 30 个交易日走势与涨跌幅对比图。

## 环境要求

- Python 3.10+（推荐 3.11）
- 依赖：

```bash
pip install akshare pandas matplotlib
```

## 脚本说明

### `screen_a_share.py`

从东财拉取全 A 实时行情（PE、总市值），与业绩报表中的 **ROE** 合并，按条件筛选：

- 市盈率（动态）**低于 20 倍**
- **ROE 大于 15%**
- **总市值大于 100 亿元**

按总市值降序取前 **20** 只，并在终端打印结果。

运行：

```bash
python screen_a_share.py
```

部分网络下东财 `*.push2.eastmoney.com` 的 clist 接口会 `RemoteDisconnected`。脚本已内置将 clist 请求改写到 **`push2delay.eastmoney.com`** 的逻辑；也可通过环境变量覆盖或关闭：

| 变量 | 含义 |
|------|------|
| `AKSHARE_EM_CLIST_HOST` | 自定义 clist 主机名，例如 `push2delay.eastmoney.com` |
| 设为 `0` / `false` / `no` | 关闭改写，使用 AkShare 默认行为 |

### `plot_top20_30d_returns.py`

对脚本内 **`TOP20` 常量**维护的股票池（可按 `screen_a_share.py` 最新结果自行改代码同步）：

- 取**最近 30 个交易日**的前复权收盘价
- 计算窗口内**涨跌幅（%）**
- 生成对比图：**归一化走势（首日=100）** + **涨跌幅横向条形图**

行情优先使用 **`stock_zh_a_hist_tx`（腾讯前复权）**；失败时再尝试东财 **`stock_zh_a_hist`**。

运行：

```bash
python plot_top20_30d_returns.py
```

输出图片默认路径：

`top20_30d_comparison.png`（与脚本同目录）

若终端中文乱码，可在 PowerShell 中：

```powershell
$env:PYTHONIOENCODING = "utf-8"
python screen_a_share.py
```

## Cursor 技能

目录 `.cursor/skills/akshare-eastmoney-push2/` 下有 **AkShare / 东财 push2 排错** 相关说明，可在 Cursor 里作为技能引用。

## 免责声明

数据来源于第三方网站接口，仅供学习与研究；接口与字段可能变更，筛选与回测结果**不构成投资建议**。

## 其他

- `example.txt`：外部教程链接备忘
- https://mp.weixin.qq.com/s/E8jYJVFT8lH2k0uVLMj73A   // 例子教程
