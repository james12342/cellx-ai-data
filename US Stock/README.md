# US Stock Sector Radar

美股版板块资金雷达，用于观察当前活跃的美股板块和板块内龙头候选。

美股没有 A 股龙虎榜那种每日“机构专用席位”公开数据，所以这个版本使用更适合美股的信号：

- 板块 ETF 作为资金活跃代理
- 1 日、5 日、20 日涨幅
- 成交量放大
- 个股相对板块强度
- 个股成交额
- 可选 13F/机构跟踪 CSV 信号

## 安装

```powershell
cd "US Stock"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python .\us_stock_sector_radar.py
```

常用参数：

```powershell
python .\us_stock_sector_radar.py --top-sectors 10 --leaders-per-sector 3
python .\us_stock_sector_radar.py --period 6mo
```

结果会写入 `US Stock/reports/`：

- `us_sectors_*.csv`：板块热度排行
- `us_leaders_*.csv`：板块龙头候选
- `us_radar_*.md`：可读报告

脚本默认直接调用 Yahoo chart 日线接口；如果直连失败，会尝试退回 `yfinance`。

## 可选机构信号

如果你有 13F、whale tracker、ARK daily trades 或其他机构买入数据，可以整理成 CSV 后传入：

```powershell
python .\us_stock_sector_radar.py --institution-file .\institution_signals.csv
```

CSV 至少需要一列：

```csv
ticker,score,detail
NVDA,80,13F increase / whale accumulation
PLTR,65,ARK buy / 13F increase
```

`score` 越高，脚本越倾向把它排为龙头候选。

## 读法

- 先看 `Sector Heat Score` 靠前的板块。
- 再看该板块里 `Leader Score` 靠前的股票。
- `Relative 5D %` 表示个股 5 日涨幅是否强于板块 ETF。
- `Volume Spike` 表示最新成交量相对 20 日均量是否放大。

这个工具适合做 watchlist，不构成投资建议。

## 美股期权热门做多/做空

运行：

```powershell
python .\us_options_hot_radar.py
```

结果同样写入 `US Stock\reports\`：

- `us_options_summary_*.csv`：按标的汇总的做多/做空热度
- `us_options_hot_long_*.csv`：热门 Call 合约，作为做多兴趣代理
- `us_options_hot_short_*.csv`：热门 Put 合约，作为做空/对冲兴趣代理
- `us_options_radar_*.md`：可读报告

常用参数：

```powershell
python .\us_options_hot_radar.py --max-days 30
python .\us_options_hot_radar.py --tickers "NVDA,TSLA,AAPL,MSFT,AMD,PLTR"
```

注意：Call 成交活跃不一定都是买入看多，也可能是备兑、价差或卖方交易；Put 成交活跃也可能是保护性对冲。这里是市场热度雷达，不是方向的确定证据。

## 每天 6:20 AM 自动运行

安装 Windows 定时任务，每天早上 6:20 运行脚本，并把结果写入 `reports/`：

```powershell
.\setup_windows_task_run_only.ps1 -Time "06:20"
```

如果 PowerShell 执行策略阻止脚本，可以这样运行一次安装：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_windows_task_run_only.ps1 -Time "06:20"
```

任务日志会写入：

```text
US Stock\logs\daily_us_radar.log
```

如果以后要改回邮件发送版本，可以使用：

```powershell
.\setup_windows_task.ps1 -Time "06:20"
```
