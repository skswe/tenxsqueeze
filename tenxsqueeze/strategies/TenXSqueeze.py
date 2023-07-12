import datetime
import os

import backtrader as bt
import numpy as np

from .. import backtrader_indicators as bi
from .BaseStrategy import BaseStrategy


class TenXSqueeze(BaseStrategy):
    params = (
        ("squeeze_pro_length", 20),
        ("atr_length", 10),
        ("adx_length", 14),
        ("tp_trail_percent", 0.4),
        ("sl_trail_percent", 0.7),
        ("percent_is_atr", True),
        ("tp_atr_multiplier", 2.3),
        ("max_trade_duration", 9),
        ("use_good_momentum", True),
        ("frequency", datetime.timedelta(minutes=5)),
    )

    strategy_name = "TenXSqueeze_V1.0"

    def __init__(self):
        super().__init__()

        self.sp = bi.SqueezePro(
            bb_length=self.p.squeeze_pro_length,
            kc_length=self.p.squeeze_pro_length,
            mom_length=self.p.squeeze_pro_length,
            atr_length=self.p.atr_length,
        )
        self.tenx = bi.TenXBars(
            dir_length=self.p.adx_length,
        )

        self.good_momentum = bi.MomentumReversal(period=self.p.squeeze_pro_length)

        self.atr = bt.ind.AverageTrueRange(period=self.p.atr_length, movav=bi.RMA)

        self.position_line = bi.Position()

        self.upper_atr = self.position_line.price + self.p.tp_atr_multiplier * self.atr
        self.lower_atr = self.position_line.price - self.p.tp_atr_multiplier * self.atr
        self.atr_cross = bt.Or(
            bt.And(self.datafeed.close >= self.upper_atr, self.position_line.size > 0),
            bt.And(self.datafeed.close <= self.lower_atr, self.position_line.size < 0),
        )

        self.cerebro.p.tradehistory = self.p.logging

    def trail_order(self, method, percent, **kwargs):
        return method(
            exectype=bt.Order.StopTrail,
            **({"trailamount": percent * self.atr} if self.p.percent_is_atr else {"trailpercent": percent}),
            **kwargs,
        )

    def log_datas(self):
        log_values = {
            "#": len(self.datafeed),
            "O": f"{self.datafeed.open[0]} ({self.datafeed.tick_open})",
            "H": f"{self.datafeed.high[0]} ({self.datafeed.tick_high})",
            "L": f"{self.datafeed.low[0]} ({self.datafeed.tick_low})",
            "C": f"{self.datafeed.close[0]} ({self.datafeed.tick_close})",
            "ATR": self.atr[0],
            "uATR": self.upper_atr[0],
            "lATR": self.lower_atr[0],
            "SZ": self.position_line.price[0],
            "ATRx": self.atr_cross[0],
            # "bb_basis": self.sp.bb_basis[0],
            # "kc_basis": self.sp.kc_basis[0],
            # "bb_upper": self.sp.bb_upper[0],
            # "kc_upper_low": self.sp.kc_upper_low[0],
            # "kc_upper_mid": self.sp.kc_upper_mid[0],
            # "kc_upper_high": self.sp.kc_upper_high[0],
            # "bb_lower": self.sp.bb_lower[0],
            # "kc_lower_low": self.sp.kc_lower_low[0],
            # "kc_lower_mid": self.sp.kc_lower_mid[0],
            # "kc_lower_high": self.sp.kc_lower_high[0],
            "squeeze_status": bi.SqueezePro.squeeze_status_map[self.sp.squeeze_status[0]],
            "momentum": self.sp.momentum[0],
            # "adx": self.tenx.adx[0],
            "d_up": self.tenx.d_up[0],
            "d_down": self.tenx.d_down[0],
            "sideways": self.tenx.sideways[0],
            "good_momentum": self.good_momentum[0],
        }
        self.log(log_values)

    def notify_order(self, order):
        if order in [self.tp_order, self.sl_order] and order.status in [order.Completed]:
            # Reset the good_momentum indicator when a trade is closed
            self.good_momentum.force_off()

        super().notify_order(order)

    def next(self):
        self.log_datas()

        if self.entry_order or self.tp_order:
            # Order is pending
            return

        if not self.position:
            # Not in the market
            if self.sp.squeeze_status[0] == 0 and (not self.p.use_good_momentum or self.good_momentum[0] == 1):
                # Squeeze fired and momentum has reset
                if self.tenx.d_up[0] and self.sp.momentum[0] > 0 and self.sp.momentum[0] > self.sp.momentum[-1]:
                    self.log("Enter long")
                    self.entry_order = self.buy(transmit=False)
                    self.sl_order = self.trail_order(self.sell, self.p.sl_trail_percent, parent=self.entry_order)
                elif self.tenx.d_down[0] and self.sp.momentum[0] < 0 and self.sp.momentum[0] < self.sp.momentum[-1]:
                    self.log("Enter short")
                    self.entry_order = self.sell(transmit=False)
                    self.sl_order = self.trail_order(self.buy, self.p.sl_trail_percent, parent=self.entry_order)

        else:
            # In the market
            if (self.datafeed.close[0] >= self.upper_atr[0] and self.position_line.size > 0) or (
                self.datafeed.close[0] <= self.lower_atr[0] and self.position_line.size < 0
            ):
                self.log("TP exit triggered")
                self.tp_order = self.trail_order(self.close, self.p.tp_trail_percent, oco=self.sl_order)

            if (len(self) - self.entries[-1]["bar_len"]) >= self.p.max_trade_duration and not self.tp_order:
                self.log("Duration SL triggered")
                self.cancel(self.sl_order)
                self.sl_order = self.close()

        super().next()
