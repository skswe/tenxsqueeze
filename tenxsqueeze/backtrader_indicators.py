"""This module contains the 10xsqueeze indicators implemented as backtrader bt.Indicator classes
"""

import backtrader as bt


class RMA(bt.Indicator):
    """Running Moving Average"""

    lines = ("rma",)
    params = (
        # params
        ("period", 20),
    )

    plotinfo = dict(plot=False)

    def __init__(self):
        self.l.rma = bt.ind.ExponentialSmoothing(self.data, period=self.p.period, alpha=1.0 / self.p.period)


class SqueezePro(bt.Indicator):
    """SqueezePro by SimplerTrading - https://intercom.help/simpler-trading/en/articles/3186315-about-squeeze-pro

    This indicator is a combination of Bollinger Bands and Keltner Channels to determine the squeeze status of the asset.
    The tighter the bollinger bands, the higher the squeeze status.
    """

    lines = (
        "bb_upper",
        "bb_basis",
        "bb_lower",
        "kc_upper_low",
        "kc_lower_low",
        "kc_upper_mid",
        "kc_upper_mid",
        "kc_lower_high",
        "kc_lower_high",
        "kc_basis",
        "squeeze_status",
        "momentum",
    )

    params = (
        ("bb_length", 20),
        ("kc_length", 20),
        ("mom_length", 20),
        ("atr_length", 10),
        ("bb_mult", 2),
        ("kc_mult_low", 2),
        ("kc_mult_mid", 1.5),
        ("kc_mult_high", 1),
    )

    plotinfo = dict(plot=False)

    squeeze_status_map = {
        0: "no squeeze",
        1: "low squeeze",
        2: "mid squeeze",
        3: "high squeeze",
    }

    def __init__(self):
        bb = bt.ind.BollingerBands(self.data.close, period=self.p.bb_length, devfactor=self.p.bb_mult)
        self.l.bb_upper = bb.top
        self.l.bb_basis = bb.mid
        self.l.bb_lower = bb.bot

        devkc = bt.ind.AverageTrueRange(period=self.p.atr_length, movav=RMA)
        self.l.kc_basis = bt.ind.SMA(period=self.p.kc_length)

        self.l.kc_upper_low = self.l.kc_basis + self.p.kc_mult_low * devkc
        self.l.kc_upper_mid = self.l.kc_basis + self.p.kc_mult_mid * devkc
        self.l.kc_upper_high = self.l.kc_basis + self.p.kc_mult_high * devkc

        self.l.kc_lower_low = self.l.kc_basis - self.p.kc_mult_low * devkc
        self.l.kc_lower_mid = self.l.kc_basis - self.p.kc_mult_mid * devkc
        self.l.kc_lower_high = self.l.kc_basis - self.p.kc_mult_high * devkc

        self.l.squeeze_status = bt.If(
            bt.Or((self.l.bb_lower >= self.l.kc_lower_high), (self.l.bb_upper <= self.l.kc_upper_high)),
            3,
            bt.If(
                bt.Or((self.l.bb_lower >= self.l.kc_lower_mid), (self.l.bb_upper <= self.l.kc_upper_mid)),
                2,
                bt.If(
                    bt.Or(
                        (self.l.bb_lower >= self.l.kc_lower_low),
                        (self.l.bb_upper <= self.l.kc_upper_low),
                    ),
                    1,
                    0,
                ),
            ),
        )

        highest_high = bt.ind.Highest(self.data.high, period=self.p.mom_length)
        lowest_low = bt.ind.Lowest(self.data.low, period=self.p.mom_length)
        sma_close = bt.ind.SMA(self.data.close, period=self.p.mom_length)
        avg_price = ((highest_high + lowest_low) / 2 + sma_close) / 2
        self.l.momentum = bt.talib.LINEARREG(self.data.close - avg_price, timeperiod=self.p.mom_length)


class TenXBars(bt.Indicator):
    """10X Bars by SimplerTrading - https://intercom.help/simpler-trading/en/articles/3210663-about-10x-bars

    This indicator is a combination of ADX and DMI to determine the trend of the asset.
    When d_up is True and ADX is greater than a threshold, it is considered a bullish trend.
    When d_down is True and ADX is greater than a threshold, it is considered a bearish trend.
    When ADX is less than the threshold, it is considered a sideways trend.
    """

    lines = ("adx", "plus", "minus", "d_up", "d_down", "sideways")
    params = (
        ("dir_length", 14),
        ("adx_thresh", 20),
        ("vol_length", 20),
        ("vol_trigger", 50),
    )

    plotinfo = dict(plot=False)

    def __init__(self):
        dm = bt.ind.DirectionalMovementIndex(period=self.p.dir_length, movav=RMA)

        self.l.adx = dm.adx
        self.l.plus = dm.plusDI
        self.l.minus = dm.minusDI

        self.l.d_up = bt.And(self.l.plus > self.l.minus, self.l.adx > self.p.adx_thresh)
        self.l.d_down = bt.And(self.l.minus > self.l.plus, self.l.adx > self.p.adx_thresh)
        self.l.sideways = self.l.adx < self.p.adx_thresh


class MomentumReversal(bt.Indicator):
    """Indicator which determines if the momentum is good or bad based on the rate of change of the momentum
    
    The indicator is true when the momentum crosses 0 and stays true until the momentum decreases for two consecutive bars.
    """

    lines = ("good_momentum", "momentum")

    params = (
        ("period", 20),
        ("cooldown", 1),
    )

    plotinfo = dict(plot=False)

    def __init__(self):
        self._force_off = False
        self._bar_ref = -1
        self.addminperiod(self.params.period)
        highest_high = bt.ind.Highest(self.data.high, period=self.p.period)
        lowest_low = bt.ind.Lowest(self.data.low, period=self.p.period)
        sma_close = bt.ind.SMA(self.data.close, period=self.p.period)
        avg_price = ((highest_high + lowest_low) / 2 + sma_close) / 2
        self.l.momentum = bt.talib.LINEARREG(self.data.close - avg_price, timeperiod=self.p.period)

    def next(self):
        current_val = abs(self.l.momentum[0])
        prev_val = abs(self.l.momentum[-1])
        prev_prev_val = abs(self.l.momentum[-2])

        if self._force_off:
            self.l.good_momentum[0] = 0
            if (self.l.momentum[-self.p.cooldown] * self.l.momentum[-1 - self.p.cooldown]) <= 0 and len(
                self
            ) > self._bar_ref:
                self._owner.log("Good momentum is being reset")
                self._force_off = False
                self.l.good_momentum[0] = 1
            return

        # If data crosses zero, it turns True again
        if (self.l.momentum[-self.p.cooldown] * self.l.momentum[-1 - self.p.cooldown]) <= 0:
            self.l.good_momentum[0] = 1
        # If absolute magnitude of data decreases for two consecutive bars
        elif current_val < prev_val and prev_val < prev_prev_val:
            self.l.good_momentum[0] = 0
        else:
            self.l.good_momentum[0] = self.l.good_momentum[-1]

    def force_off(self):
        # Force indicator back to 0
        self._owner.log("Forcing good momentum to 0")
        self._force_off = True
        self._bar_ref = len(self)
        self.l.good_momentum[0] = 0


class Position(bt.Indicator):
    """Indicator to track the current position size and price"""

    lines = ("size", "price")

    def next(self):
        if self._owner.position:
            self.l.size[0] = self._owner.position.size
            self.l.price[0] = self._owner.position.price
        else:
            self.l.size[0] = bt.NAN
            self.l.price[0] = bt.NAN


class PStackedEMA(bt.Indicator):
    """Positvely stacked Exponential Moving Averages - Fires True when the EMAs are stacked in increasing order"""

    lines = ("signal",)

    params = (
        ("ema1_length", 5),
        ("ema2_length", 8),
        ("ema3_length", 21),
        ("ema4_length", 34),
        ("ema5_length", 55),
        ("ema6_length", 89),
    )

    def __init__(self):
        ema1 = bt.ind.ExponentialMovingAverage(period=self.p.ema1_length)
        ema2 = bt.ind.ExponentialMovingAverage(period=self.p.ema2_length)
        ema3 = bt.ind.ExponentialMovingAverage(period=self.p.ema3_length)
        ema4 = bt.ind.ExponentialMovingAverage(period=self.p.ema4_length)
        ema5 = bt.ind.ExponentialMovingAverage(period=self.p.ema5_length)
        ema6 = bt.ind.ExponentialMovingAverage(period=self.p.ema6_length)
        self.l.signal = bt.And(ema1 > ema2, ema2 > ema3, ema3 > ema4, ema4 > ema5, ema5 > ema6)


class NStackedEMA(bt.Indicator):
    """Negatively stacked Exponential Moving Averages - Fires True when the EMAs are stacked in decreasing order"""

    lines = ("signal",)

    params = (
        ("ema1_length", 5),
        ("ema2_length", 8),
        ("ema3_length", 21),
        ("ema4_length", 34),
        ("ema5_length", 55),
        ("ema6_length", 89),
    )

    def __init__(self):
        ema1 = bt.ind.ExponentialMovingAverage(period=self.p.ema1_length)
        ema2 = bt.ind.ExponentialMovingAverage(period=self.p.ema2_length)
        ema3 = bt.ind.ExponentialMovingAverage(period=self.p.ema3_length)
        ema4 = bt.ind.ExponentialMovingAverage(period=self.p.ema4_length)
        ema5 = bt.ind.ExponentialMovingAverage(period=self.p.ema5_length)
        ema6 = bt.ind.ExponentialMovingAverage(period=self.p.ema6_length)
        self.l.signal = bt.And(ema1 < ema2, ema2 < ema3, ema3 < ema4, ema4 < ema5, ema5 < ema6)


class WithinKC(bt.Indicator):
    """Indicator to check if the current price is within the Keltner Channels"""

    lines = ("signal", "kc_basis", "kc_upper", "kc_lower")

    params = (
        ("atr_length", 10),
        ("kc_length", 20),
        ("kc_mult", 1),
    )

    def __init__(self):
        devkc = bt.ind.AverageTrueRange(period=self.p.atr_length, movav=RMA)
        self.l.kc_basis = bt.ind.SMA(period=self.p.kc_length)
        self.l.kc_lower = self.l.kc_basis - self.p.kc_mult * devkc
        self.l.kc_upper = self.l.kc_basis + self.p.kc_mult * devkc

        self.l.signal = bt.And(self.data.close >= self.l.kc_lower, self.data.close <= self.l.kc_upper)


class Big3(bt.Indicator):
    """Big3 by SimplerTrading - https://intercom.help/simpler-trading/en/articles/6384452-about-big-3-signals

    This indicator is a combination of SqueezePro, Directional Movement Index and Stacked EMAs to determine the signal of the asset.
    If the asset is in a bullish trend and the squeeze status is high, it is considered a strong buy signal.
    If the asset is in a bullish trend and the squeeze status is medium, it is considered a weak buy signal.
    If the asset is in a bearish trend and the squeeze status is high, it is considered a strong sell signal.
    If the asset is in a bearish trend and the squeeze status is medium, it is considered a weak sell signal.
    """

    lines = ("signal", "squeeze_status", "bullish_trend", "bearish_trend", "in_kc", "lkc_u", "lkc_l", "mkc_u", "mkc_l")

    def __init__(self):
        sp = SqueezePro()
        dm = bt.ind.DirectionalMovementIndex(period=14, movav=RMA)
        p_stack_ema = PStackedEMA()
        n_stack_ema = NStackedEMA()
        self.l.squeeze_status = sp.l.squeeze_status
        self.l.lkc_u = sp.l.kc_upper_low
        self.l.lkc_l = sp.l.kc_lower_low
        self.l.mkc_u = sp.l.kc_upper_mid
        self.l.mkc_l = sp.l.kc_lower_mid
        self.l.bullish_trend = bt.And(dm.l.adx > 20, dm.l.plusDI > dm.l.minusDI, p_stack_ema)
        self.l.bearish_trend = bt.And(dm.l.adx > 20, dm.l.plusDI < dm.l.minusDI, n_stack_ema)
        self.l.in_kc = bt.And(self.data.close >= sp.l.kc_lower_high, self.data.close <= sp.l.kc_upper_high)

    def next(self):
        if self.l.bullish_trend[0]:
            if self.l.squeeze_status[0] == 3:
                self.l.signal[0] = 2
            elif self.l.squeeze_status[0] == 2:
                self.l.signal[0] = 1
            else:
                self.l.signal[0] = 0
        elif self.l.bearish_trend[0]:
            if self.l.squeeze_status[0] == 3:
                self.l.signal[0] = -2
            elif self.l.squeeze_status[0] == 2:
                self.l.signal[0] = -1
            else:
                self.l.signal[0] = 0
        else:
            self.l.signal[0] = 0
