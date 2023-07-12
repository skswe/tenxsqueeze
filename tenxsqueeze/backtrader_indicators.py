import backtrader as bt


class RMA(bt.Indicator):
    lines = ("rma",)
    params = (
        # params
        ("period", 20),
    )

    plotinfo = dict(plot=False)

    def __init__(self):
        self.lines.rma = bt.ind.ExponentialSmoothing(self.data, period=self.p.period, alpha=1.0 / self.p.period)


class SqueezePro(bt.Indicator):
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
        self.lines.bb_upper = bb.top
        self.lines.bb_basis = bb.mid
        self.lines.bb_lower = bb.bot

        devkc = bt.ind.AverageTrueRange(period=self.p.atr_length, movav=RMA)
        self.lines.kc_basis = bt.ind.SMA(period=self.p.kc_length)

        self.lines.kc_upper_low = self.lines.kc_basis + self.p.kc_mult_low * devkc
        self.lines.kc_upper_mid = self.lines.kc_basis + self.p.kc_mult_mid * devkc
        self.lines.kc_upper_high = self.lines.kc_basis + self.p.kc_mult_high * devkc

        self.lines.kc_lower_low = self.lines.kc_basis - self.p.kc_mult_low * devkc
        self.lines.kc_lower_mid = self.lines.kc_basis - self.p.kc_mult_mid * devkc
        self.lines.kc_lower_high = self.lines.kc_basis - self.p.kc_mult_high * devkc

        self.lines.squeeze_status = bt.If(
            bt.Or(
                (self.lines.bb_lower >= self.lines.kc_lower_high), (self.lines.bb_upper <= self.lines.kc_upper_high)
            ),
            3,
            bt.If(
                bt.Or(
                    (self.lines.bb_lower >= self.lines.kc_lower_mid), (self.lines.bb_upper <= self.lines.kc_upper_mid)
                ),
                2,
                bt.If(
                    bt.Or(
                        (self.lines.bb_lower >= self.lines.kc_lower_low),
                        (self.lines.bb_upper <= self.lines.kc_upper_low),
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
        self.lines.momentum = bt.talib.LINEARREG(self.data.close - avg_price, timeperiod=self.p.mom_length)


class TenXBars(bt.Indicator):
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

        self.lines.adx = dm.adx
        self.lines.plus = dm.plusDI
        self.lines.minus = dm.minusDI

        self.lines.d_up = bt.And(self.lines.plus > self.lines.minus, self.lines.adx > self.p.adx_thresh)
        self.lines.d_down = bt.And(self.lines.minus > self.lines.plus, self.lines.adx > self.p.adx_thresh)
        self.lines.sideways = self.lines.adx < self.p.adx_thresh


class MomentumReversal(bt.Indicator):
    lines = ("good_momentum",)

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
        self.momentum = bt.talib.LINEARREG(self.data.close - avg_price, timeperiod=self.p.period)

    def next(self):
        current_val = abs(self.momentum[0])
        prev_val = abs(self.momentum[-1])
        prev_prev_val = abs(self.momentum[-2])
        
        if self._force_off:
            self.lines.good_momentum[0] = 0
            if (self.momentum[-self.p.cooldown] * self.momentum[-1-self.p.cooldown]) <= 0 and len(self) > self._bar_ref:
                self._owner.log("Good momentum is being reset")
                self._force_off = False
                self.lines.good_momentum[0] = 1
            return

        # If data crosses zero, it turns True again
        if (self.momentum[-self.p.cooldown] * self.momentum[-1-self.p.cooldown]) <= 0:
            self.lines.good_momentum[0] = 1
        # If absolute magnitude of data decreases for two consecutive bars
        elif current_val < prev_val and prev_val < prev_prev_val:
            self.lines.good_momentum[0] = 0
        else:
            self.lines.good_momentum[0] = self.lines.good_momentum[-1]

    def force_off(self):
        # Force indicator back to 0
        self._owner.log("Forcing good momentum to 0")
        self._force_off = True
        self._bar_ref = len(self)
        self.lines.good_momentum[0] = 0


class Position(bt.Indicator):
    lines = ("size", "price")

    def next(self):
        if self._owner.position:
            self.lines.size[0] = self._owner.position.size
            self.lines.price[0] = self._owner.position.price
        else:
            self.lines.size[0] = bt.NAN
            self.lines.price[0] = bt.NAN
