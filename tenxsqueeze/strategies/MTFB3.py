"""This module contains the Multi Time-frame Big 3 strategy class. It is an extension of the 10xsqueeze strategy
"""

import datetime
import os
from collections import defaultdict

import backtrader as bt
import numpy as np
from tabulate import tabulate

from .. import backtrader_indicators as bi

# List of timeframes to be used in the strategy
MTF_list = ["5m", "15m", "30m", "1h", "2h", "4h", "1d"]


def below_0(x):
    return x < 0


def above_0(x):
    return x > 0


class TickerStatus:
    Neutral = 0
    BuildLong = 1
    BuildShort = 2
    HoldLong = 3
    HoldShort = 4


class MTFB3(bt.Strategy):
    """The Multi Time-frame Big 3 strategy is a momentum based strategy which uses the Big 3 indicators on multiple timeframes
    
    This strategy uses SqueezePro and 10X Bars like the 10xsqueeze strategy, with the addition of stacked EMA's. The position
    is built during the squeeze phase (high squeeze or medium squeeze) rather than during the momentum phase. Additionally, the signal
    must align on multiple timeframes for a position to be built.
    
    This strategy can be run on multiple assets simultaneously.
    """
    strategy_name = "MTFB3_V1.0"

    params = (
        # params
        ("logging", True),
        ("log_file", "log.txt"),
    )

    def __init__(self):
        super().__init__()

        if self.p.logging:
            if os.path.exists(self.p.log_file):
                os.remove(self.p.log_file)

        self.order_info = []

        self.cerebro.p.tradehistory = self.p.logging

        n_timeframes = 1
        while hasattr(self, f"data{n_timeframes}") and getattr(getattr(self, f"data{n_timeframes}"), "replaying"):
            n_timeframes += 1

        self.timeframes = MTF_list[:n_timeframes]
        self.tickers = defaultdict(dict)
        self.signals = defaultdict(dict)
        self.ticker_status = defaultdict(int)
        self.ticker_position = defaultdict(int)
        self.entry_orders = defaultdict(list)
        self.sl_orders = defaultdict(lambda: None)
        self.tp_orders = defaultdict(lambda: None)

        for i in range(0, len(self.datas), n_timeframes):
            tickers = self.datas[i : i + n_timeframes]
            for ticker in tickers:
                ticker_name, timeframe = ticker._name.split("_")
                self.tickers[ticker_name][timeframe] = ticker
                self.signals[ticker_name][timeframe] = bi.Big3(ticker)

    def neutral_state_transition(self, ticker):
        """Changes ticker state to `build` if a signal is acquired during the current bar"""
        signal_5m = self.signals[ticker]["5m"]

        def signal_condition(test_fn, n_consecutive=6):
            return all(test_fn(signal_5m[x]) for x in range(0, -n_consecutive, -1))

        # State Transision 1: Signal acquired
        if signal_condition(above_0, n_consecutive=6):
            self.ticker_status[ticker] = TickerStatus.BuildLong
        elif signal_condition(below_0, n_consecutive=6):
            self.ticker_status[ticker] = TickerStatus.BuildShort

    def build_state_transition(self, ticker):
        """Changes ticker state to `neutral` or `hold` if a signal is lost during the current bar"""
        signal_5m = self.signals[ticker]["5m"]
        status = self.ticker_status[ticker]
        position = self.ticker_position[ticker]
        has_position = position != 0

        # State Transition 1: Signal lost + no position
        def signal_break_condition(test_fn, window=3):
            return test_fn(signal_5m[-window]) and all(signal_5m[x] == 0 for x in range(0, -window, -1))

        if (
            not has_position
            and status == TickerStatus.BuildLong
            and (signal_break_condition(above_0, window=3) or self.price_target_reached(ticker))
        ):
            self.ticker_status[ticker] = TickerStatus.Neutral
        elif (
            not has_position
            and status == TickerStatus.BuildShort
            and (signal_break_condition(below_0, window=3) or self.price_target_reached(ticker))
        ):
            self.ticker_status[ticker] = TickerStatus.Neutral

        # State Transition 2: Signal lost + has position
        elif has_position and status == TickerStatus.BuildLong and signal_break_condition(above_0, window=3):
            self.ticker_status[ticker] = TickerStatus.HoldLong
        elif has_position and status == TickerStatus.BuildShort and signal_break_condition(below_0, window=3):
            self.ticker_status[ticker] = TickerStatus.HoldShort

    def build_position(self, ticker):
        status = self.ticker_status[ticker]
        if status not in [TickerStatus.BuildLong, TickerStatus.BuildShort]:
            return
        data = self.tickers[ticker]["5m"]
        sig = self.signals[ticker]["5m"]
        order_fn = self.buy if status == TickerStatus.BuildLong else self.sell
        stop_fn = self.sell if status == TickerStatus.BuildLong else self.buy
        stop_price = sig.mkc_l[0] if status == TickerStatus.BuildLong else sig.mkc_u[0]
        target_price = sig.lkc_u[0] if status == TickerStatus.BuildLong else sig.lkc_l[0]

        if sig.in_kc[0]:
            sl_order = self.sl_orders[ticker]
            tp_order = self.tp_orders[ticker]
            if sl_order is None or tp_order is None:
                entry_order = order_fn(data, size=1, transmit=False)
                self.entry_orders[ticker].append(entry_order)
                self.sl_orders[ticker] = stop_fn(
                    data, size=1, exectype=bt.Order.Stop, price=stop_price, parent=entry_order, transmit=False
                )
                self.tp_orders[ticker] = stop_fn(
                    data, size=1, exectype=bt.Order.Limit, price=target_price, parent=entry_order
                )
            else:
                entry_order = order_fn(data, size=1)
                self.entry_orders[ticker].append(entry_order)
                sl_order.executed.remsize += 1 * np.sign(sl_order.executed.remsize)
                tp_order.executed.remsize += 1 * np.sign(tp_order.executed.remsize)
                # self.log(f"Added to position: {ticker} {sl_order.created.size} @ {sl_order.created.price:.2f}")

    def update_sl_tp_prices(self, ticker):
        status = self.ticker_status[ticker]
        data = self.tickers[ticker]["5m"]
        sig = self.signals[ticker]["5m"]
        sl_order = self.sl_orders[ticker]
        tp_order = self.tp_orders[ticker]
        if sl_order is not None and tp_order is not None:
            sl_order.created.price = sig.mkc_l[0] if status == TickerStatus.BuildLong else sig.mkc_u[0]
            tp_order.created.price = sig.lkc_u[0] if status == TickerStatus.BuildLong else sig.lkc_l[0]

    def price_target_reached(self, ticker):
        status = self.ticker_status[ticker]
        data = self.tickers[ticker]["5m"]
        sig = self.signals[ticker]["5m"]
        if status == TickerStatus.BuildLong:
            if data.high[0] >= sig.lkc_u[0]:  # TP
                return True
            if data.low[0] <= sig.mkc_l[0]:  # SL
                return True
        elif status == TickerStatus.BuildShort:
            if data.low[0] <= sig.lkc_l[0]:  # TP
                return True
            elif data.high[0] >= sig.mkc_u[0]:  # SL
                return True
        return False

    def next(self):
        for ticker in self.tickers.keys():
            status = self.ticker_status[ticker]
            if status == TickerStatus.Neutral:
                self.neutral_state_transition(ticker)
            elif status in [TickerStatus.BuildLong, TickerStatus.BuildShort]:
                self.build_state_transition(ticker)
                self.build_position(ticker)
                self.update_sl_tp_prices(ticker)
            elif status in [TickerStatus.HoldLong, TickerStatus.HoldShort]:
                self.update_sl_tp_prices(ticker)

        # self.log(
        #     f"{data.open[0]:.2f} {data.high[0]:.2f} {data.low[0]:.2f} {data.close[0]:.2f} || {sig.mkc_l[0]:.2f} <> {sig.mkc_u[0]:.2f} || {sig.lkc_l[0]:.2f} <> {sig.lkc_u[0]:.2f}"
        # )

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        self.log(
            f"Order notification: {order.getstatusname()} {order.getordername()} {order.executed.size} @ {order.executed.price}"
        )

        data = order.p.data
        ticker, timeframe = data._name.split("_")

        if order.status in [order.Completed]:
            if order == self.tp_orders[ticker]:
                kind = "TP"
                self.tp_orders[ticker] = None
                self.ticker_status[ticker] = TickerStatus.Neutral
                self.ticker_position[ticker] += order.executed.size if order.isbuy() else -order.executed.size
            elif order == self.sl_orders[ticker]:
                kind = "SL"
                self.sl_orders[ticker] = None
                self.ticker_status[ticker] = TickerStatus.Neutral
                self.ticker_position[ticker] += order.executed.size if order.isbuy() else -order.executed.size
            elif order in self.entry_orders[ticker]:
                kind = "Entry"
                self.ticker_position[ticker] += 1 if order.isbuy() else -1
            else:
                kind = "Unknown"
            pnl = (
                order.executed.pnl - sum([x.executed.comm for x in self.entry_orders[ticker]]) - order.executed.comm
                if kind != "Entry"
                else 0
            )
            pnl_pct = pnl / abs(order.executed.price * order.executed.size) * 100 if kind != "Entry" else 0
            self.order_info.append(
                {
                    "ticker": ticker,
                    "dt": data.datetime.datetime() - datetime.timedelta(minutes=5),
                    "filled_price": order.executed.price,
                    "size": order.executed.size,
                    "value": order.executed.price * order.executed.size,
                    "comm": order.executed.comm,
                    "pnl": pnl,
                    "pnl%": pnl_pct,
                    "len": len(data),
                    "kind": kind,
                }
            )
            if self.ticker_position[ticker] == 0:
                self.entry_orders[ticker] = []

    def log(self, txt, dt=None):
        """Logging function for this strategy"""
        if not self.p.logging:
            return

        dt = dt or self.data0.datetime.datetime() - datetime.timedelta(minutes=5)
        dt_str = dt.strftime("%Y-%m-%d %H:%M")

        if isinstance(txt, dict):
            log_dict = {"Datetime": dt_str, **txt}
        else:
            log_dict = {"Datetime": dt_str, "Log": txt}

        # Values and headers are swapped to make the lines easier to read
        log_table = tabulate(
            [list(log_dict.keys())],
            headers=[round(x, 2) if isinstance(x, float) else x for x in log_dict.values()],
            tablefmt="simple",
        )

        if self.params.log_file:
            with open(self.params.log_file, "a") as f:
                print(log_table, file=f)
        else:
            print(log_table)
