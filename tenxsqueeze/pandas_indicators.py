"""This module contains the 10xsqueeze indicators implemented as pandas functions
"""

import numpy as np
import pandas as pd
import talib as ta


def true_range(feed: pd.DataFrame):
    """True Range - The largest price difference seen in the last period"""
    high_low = feed.high - feed.low
    high_prev = (feed.high - feed.close.shift(1)).abs()
    low_prev = (feed.low - feed.close.shift(1)).abs()

    return pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)


def rma(feed: pd.Series, length=20):
    """Running Moving Average"""
    return feed.ewm(alpha=1 / length, adjust=False).mean()


def squeeze_pro_indicator(
    feed: pd.DataFrame,
    bb_length=20,
    kc_length=20,
    mom_length=20,
    atr_length=10,
    bb_mult=2,
    kc_mult={"high": 1, "mid": 1.5, "low": 2},
):
    """SqueezePro by SimplerTrading - https://intercom.help/simpler-trading/en/articles/3186315-about-squeeze-pro

    This indicator is a combination of Bollinger Bands and Keltner Channels to determine the squeeze status of the asset.
    The tighter the bollinger bands, the higher the squeeze status.
    """
    bb_upper, bb_basis, bb_lower = ta.BBANDS(
        feed.close, timeperiod=bb_length, nbdevup=bb_mult, nbdevdn=bb_mult, matype=0
    )
    devkc = rma(ta.TRANGE(feed.high, feed.low, feed.close), atr_length)

    kc_basis = ta.SMA(feed.close, timeperiod=kc_length)

    kc_upper = {
        "high": kc_basis + kc_mult["high"] * devkc,
        "mid": kc_basis + kc_mult["mid"] * devkc,
        "low": kc_basis + kc_mult["low"] * devkc,
    }

    kc_lower = {
        "high": kc_basis - kc_mult["high"] * devkc,
        "mid": kc_basis - kc_mult["mid"] * devkc,
        "low": kc_basis - kc_mult["low"] * devkc,
    }

    squeeze_status = {
        "no_squeeze": (bb_lower < kc_lower["low"]) | (bb_upper > kc_upper["low"]),
        "low_squeeze": (bb_lower >= kc_lower["low"]) | (bb_upper <= kc_upper["low"]),
        "mid_squeeze": (bb_lower >= kc_lower["mid"]) | (bb_upper <= kc_upper["mid"]),
        "high_squeeze": (bb_lower >= kc_lower["high"]) | (bb_upper <= kc_upper["high"]),
    }

    squeeze_status = pd.DataFrame(squeeze_status).loc[:, ::-1].idxmax(axis=1)

    # momentum
    highest_high = feed.high.rolling(mom_length).max()
    lowest_low = feed.low.rolling(mom_length).min()
    sma_close = ta.SMA(feed.close, timeperiod=mom_length)

    avg_price = ((highest_high + lowest_low) / 2 + sma_close) / 2

    mom = ta.LINEARREG(feed.close - avg_price, timeperiod=mom_length)

    return kc_lower, kc_upper, bb_lower, bb_upper, bb_basis, squeeze_status, mom


def directional_movement(feed, dir_length=14):
    """Directional Movement Index (DMI) - Measures the strength of the trend of the asset"""
    up = feed.high.diff()
    down = -feed.low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=up.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=down.index)
    trur = rma(true_range(feed), dir_length)
    plus = (100 * rma(plus_dm, dir_length) / trur).bfill()
    minus = (100 * rma(minus_dm, dir_length) / trur).bfill()
    sum = plus + minus
    adx = 100 * rma(pd.Series(plus - minus).abs() / (np.where(sum == 0, 1, sum)), dir_length)

    return adx, plus, minus


def p_stacked_ema(feed, lengths=[5, 8, 21, 34, 55, 89]):
    """Positvely stacked Exponential Moving Averages - Fires True when the EMAs are stacked in increasing order"""

    emas = [ta.EMA(feed.close, timeperiod=length) for length in lengths]
    p_stacked = np.all([emas[i] > emas[i + 1] for i in range(len(emas) - 1)], axis=0)
    return pd.Series(p_stacked, index=feed.index)


def n_stacked_ema(feed, lengths=[5, 8, 21, 34, 55, 89]):
    """Negatively stacked Exponential Moving Averages - Fires True when the EMAs are stacked in decreasing order"""

    emas = [ta.EMA(feed.close, timeperiod=length) for length in lengths]
    n_stacked = np.all([emas[i] < emas[i + 1] for i in range(len(emas) - 1)], axis=0)
    return pd.Series(n_stacked, index=feed.index)


def big3(feed):
    """Big3 by SimplerTrading - https://intercom.help/simpler-trading/en/articles/6384452-about-big-3-signals

    This indicator is a combination of SqueezePro, Directional Movement Index and Stacked EMAs to determine the signal of the asset.
    If the asset is in a bullish trend and the squeeze status is high, it is considered a strong buy signal.
    If the asset is in a bullish trend and the squeeze status is medium, it is considered a weak buy signal.
    If the asset is in a bearish trend and the squeeze status is high, it is considered a strong sell signal.
    If the asset is in a bearish trend and the squeeze status is medium, it is considered a weak sell signal.
    """
    kc_lower, kc_upper, bb_lower, bb_upper, bb_basis, squeeze_status, mom = squeeze_pro_indicator(feed)
    adx, plus_di, minus_di = directional_movement(feed)
    p_stack = p_stacked_ema(feed)
    n_stack = n_stacked_ema(feed)

    bullish_trend = (adx > 20) & (plus_di > minus_di) & p_stack
    bearish_trend = (adx > 20) & (plus_di < minus_di) & n_stack
    in_kc = (feed.close >= kc_lower["high"]) & (feed.close <= kc_upper["high"])

    signal = pd.Series(np.zeros(len(feed)), index=feed.index)

    # Bullish signals
    bullish_conditions = bullish_trend & in_kc
    signal.loc[bullish_conditions & (squeeze_status == "high_squeeze")] = 2
    signal.loc[bullish_conditions & (squeeze_status == "mid_squeeze")] = 1

    # Bearish signals
    bearish_conditions = bearish_trend & in_kc
    signal.loc[bearish_conditions & (squeeze_status == "high_squeeze")] = -2
    signal.loc[bearish_conditions & (squeeze_status == "mid_squeeze")] = -1

    return signal
