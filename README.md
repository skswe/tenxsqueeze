# Momentum Based Algotrading

This repository contains backtests and analysis for two distinct momentum-based
strategies: **"10xsqueeze"** and **"big3"**. The backtesting results in this
study are not profitable, however, the strategies can be further optimized and
customized to improve performance.

## 10xsqueeze Strategy Overview

The **10xsqueeze** strategy utilizes two key indicators,
**[SqueezePro](https://intercom.help/simpler-trading/en/articles/3186315-about-squeeze-pro)**
and
**[10X Bars](https://intercom.help/simpler-trading/en/articles/3210663-about-10x-bars)**,
to identify potential trading opportunities based on momentum shifts.

The core principle of the 10xsqueeze strategy revolves around identifying assets
experiencing low volatility periods followed by significant directional
movements. When there's no squeeze and momentum is building in a particular
direction, the strategy enters a trade in alignment with that direction.

### Indicators Used:

- **SqueezePro Indicator**: This indicator combines Bollinger Bands and Keltner
  Channels to gauge the squeeze status of the asset (how tight is it trading
  relative to a moving average). The tighter the Bollinger Bands, the higher the
  squeeze status.

- **10X Bars Indicator**: A combination of ADX (Average Directional Index) and
  DMI (Directional Movement Index) is used to determine the trend of the asset.
  It identifies bullish, bearish, and sideways trends based on specific
  conditions.

### Implementation

The strategy is implemented using the `backtrader` library in Python. The
backtests are conducted on historical cryptocurrency futures data. The backtests
conducted in this study cover a period of 4 months and result in a -4% return.
The backtest code is available in the `10xsqueeze_backtest.ipynb` notebook.

## Big3 Strategy Overview

The
**[Big3](https://intercom.help/simpler-trading/en/articles/6384452-about-big-3-signals)**
strategy uses SqueezePro and 10X Bars like the 10xsqueeze strategy, with the
addition of stacked EMA's. Unlike the 10xsqueeze strategy, the Big3 strategy
focuses on building positions during the squeeze phase (high or medium squeeze)
rather than during momentum phases.

### Indicators Used:

- **SqueezePro and 10X Bars**: Similar to the 10xsqueeze strategy, these
  indicators are employed to assess squeeze status and trend strength.

- **Stacked EMAs**: Exponential Moving Averages with a fibonacci sequence of
  periods are stacked positively or negatively to identify the trend direction.

### Implementation

The Big3 strategy is also implemented using the `backtrader` library in Python.
The backtests are conducted on S&P500 stock data. The backtests conducted in
this study cover a period of 3 months and result in a -1% return. The backtest
code is available in the `big3_backtest.ipynb` notebook. In addition to the
backtest, there is also a set of notebooks used to optimize the relationship
between how many consecutive times the signal fires and the size of the price
movement following the signal. This code is available in the notebooks prefixed
with `scan_analysis_`.
