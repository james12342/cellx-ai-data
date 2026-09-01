# A股板块资金雷达

这个小工具用于观察 A 股里“资金流入较强的板块”和“疑似龙头股”，并叠加龙虎榜机构专用席位的最新净买入线索。

它适合做盘后/盘中观察，不构成投资建议。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
python .\a_stock_sector_radar.py
```

常用参数：

```powershell
python .\a_stock_sector_radar.py --top-sectors 15 --leaders-per-sector 3 --lookback-days 10
python .\a_stock_sector_radar.py --industry-only
python .\a_stock_sector_radar.py --date 20260515
```

## 输出

结果会写入 `reports/`：

- `sectors_*.csv`：板块热度排行
- `leaders_*.csv`：每个高热度板块的龙头候选
- `institutions_*.csv`：最近窗口内龙虎榜机构席位净买入
- `radar_*.md`：方便阅读的汇总报告

## 评分口径

脚本会优先使用东方财富资金流接口；如果该接口临时返回 502、空数据或 AKShare 解析失败，会自动切换到同花顺/新浪的行业资金与成分股数据。fallback 模式下，5 日/10 日资金连续性会暂时置为 0，龙头候选会优先使用行业领涨股和可取得的个股资金数据。

板块热度分综合：

- 今日主力净流入
- 5 日主力净流入
- 10 日主力净流入
- 今日板块涨跌幅
- 资金连续性

龙头候选分综合：

- 个股主力净流入
- 个股涨跌幅
- 成交额
- 换手率
- 龙虎榜机构净买入

## 注意

“机构最新买入”使用的是公开龙虎榜里的机构专用席位数据，只覆盖上榜个股，不代表全部机构真实交易。北向资金盘中实时净买入数据已经不再像以前那样完整披露，因此这里不把北向实时资金作为核心信号。

## 排错

如果运行时看到类似下面的错误：

```text
Data fetch failed. The public Eastmoney/AKShare endpoint may be throttled...
```

通常是东方财富公开接口临时返回空数据、502，或 AKShare 尚未适配上游页面变化。可以稍后重试，或先升级 AKShare：

```powershell
pip install -U akshare
```
