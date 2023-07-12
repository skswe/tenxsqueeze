import csv
import datetime
import multiprocessing
import os
import sys
from copy import deepcopy

import backtrader as bt
import pandas as pd
import pyutil
import tqdm
from tabulate import tabulate

from .. import backtrader_indicators as bi
from ..BacktraderResult import BacktraderResult
from ..util import undo_backtrader_dt

lock = multiprocessing.Lock()


class BaseStrategy(BacktraderResult, bt.Strategy):
    params = (
        # params
        ("logging", True),
        ("progress_bar", False),
        ("log_file", "log.txt"),
        ("save_results", True),
        ("cache_logs", False),
    )

    def __init__(self):
        self.datafeed = self.datas[0]
        self.entry_order = None
        self.tp_order = None
        self.sl_order = None
        self.in_position = False
        self.entries = []
        self.exits = []
        self.trades = []

        if self.p.logging:
            if os.path.exists(self.p.log_file):
                os.remove(self.p.log_file)

        self.cerebro.p.tradehistory = self.p.logging

    def log_order(self, order, only_completed=False):
        if only_completed and order.status != order.Completed:
            return

        if order == self.entry_order:
            order_type = "ENTRY"
        elif order == self.tp_order:
            order_type = "TAKEPROFIT"
        elif order == self.sl_order:
            order_type = "STOPLOSS"
        else:
            order_type = "UNKNOWN"

        order_direction = (
            ("LONG" if order.isbuy() else "SHORT") if order_type == "ENTRY" else ("SHORT" if order.isbuy() else "LONG")
        )
        order_price = order.executed.price if order.status == order.Completed else order.created.price
        order_size = order.executed.size if order.status == order.Completed else order.created.size
        order_commission = order.executed.comm if order.status == order.Completed else 0.0
        order_status = order.getstatusname()
        order_exectype = order.getordername()

        order_log = (
            f">>> {order_direction} {order_type} ({order_exectype}) {order_status} {order_size} @ {order_price:.2f}"
        )
        if only_completed:
            order_log += f" (created @ {order.executed.price:.2f})"

        if order_commission > 0:
            order_log += f" (commission: {order_commission:.2f})"

        self.log(order_log)

    def notify_order(self, order):
        self.log_order(order)
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order == self.entry_order:
                self.entries.append(
                    {
                        "direction": "long" if order.isbuy() else "short",
                        "time": self.datafeed.datetime.datetime(),
                        "filled_price": order.executed.price,
                        "bar_len": len(self.datafeed),
                    }
                )
                self.in_position = True
                self.entry_order = None
            elif order in [self.tp_order, self.sl_order]:
                self.exits.append(
                    {
                        "direction": "short" if order.isbuy() else "long",
                        "time": self.datafeed.datetime.datetime(),
                        "filled_price": order.executed.price,
                        "type": "tp" if order == self.tp_order else "sl",
                    }
                )
                self.in_position = False
                if order == self.tp_order:
                    self.tp_order = None
                elif order == self.sl_order:
                    self.sl_order = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if order == self.entry_order:
                self.entry_order = None
            elif order == self.tp_order:
                self.tp_order = None
            elif order == self.sl_order:
                self.sl_order = None

    def notify_trade(self, trade):
        if trade.isclosed and self.cerebro.p.tradehistory:
            trade_dict = {
                "direction": "long" if trade.history[-2].event.order.isbuy() else "short",
                "entry_price": trade.history[-2].event.price,
                "exit_price": trade.history[-1].event.price,
                "size": trade.history[-1].event.size,
                "value": trade.value,
                "commission": trade.commission,
                "pnl": trade.pnl,
                "pnl_pct": (trade.pnl / (trade.price * abs(trade.history[-1].event.size))) * 100,
                "entry_time": bt.num2date(trade.history[-2].status.dt),
                "exit_time": bt.num2date(trade.history[-1].status.dt),
                "bar_duration": trade.barlen,
            }
            self.trades.append(trade_dict)
            self.log(trade_dict)

    def log(self, txt, dt=None):
        """Logging function for this strategy"""
        if not self.p.logging:
            return

        dt = dt or self.datafeed.datetime.datetime() - datetime.timedelta(minutes=5)
        dt_str = dt.strftime("%Y-%m-%d %H:%M")

        if isinstance(txt, dict):
            log_dict = {"Datetime": dt_str, **txt}
        else:
            log_dict = {"Datetime": dt_str, "Log": txt}

        log_list = [list(log_dict.values())]

        log_table = tabulate(log_list, headers=log_dict.keys(), tablefmt="rounded_outline")

        if self.params.log_file:
            with open(self.params.log_file, "a") as f:
                print(log_table, file=f)
        else:
            print(log_table)

    def start(self):
        if self.p.progress_bar:
            self.progress = tqdm.tqdm(total=len(self.datafeed._dataname))

    def prenext(self):
        if self.p.progress_bar:
            self.progress.update(1)

    def next(self):
        if self.p.progress_bar:
            self.progress.update(1)

    def stop(self):
        if self.p.progress_bar:
            del self.progress
