import pandas as pd
import talib as ta

def true_range(feed: pd.DataFrame):
    high_low = (feed.high - feed.low)
    high_prev = (feed.high - feed.close.shift(1)).abs()
    low_prev = (feed.low - feed.close.shift(1)).abs()
    
    return pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)

def rma(feed: pd.Series, length=20):
    return feed.ewm(alpha=1/length, adjust=False).mean()

def squeeze_pro_indicator(feed: pd.DataFrame, bb_length=20, kc_length=20, mom_length=20, atr_length=10, bb_mult=2, kc_mult={"high": 1, "mid": 1.5, "low": 2}):  
    bb_upper, bb_basis, bb_lower = ta.BBANDS(feed.close, timeperiod=bb_length, nbdevup=bb_mult, nbdevdn=bb_mult, matype=0)
    devkc = rma(ta.TRANGE(feed.high, feed.low, feed.close), atr_length)
    
    kc_basis = ta.SMA(feed.close, timeperiod=kc_length)
    
    kc_upper = {
        "high": kc_basis + kc_mult["high"] * devkc,
        "mid": kc_basis + kc_mult["mid"] * devkc,
        "low": kc_basis + kc_mult["low"] * devkc
    }
    
    kc_lower = {
        "high": kc_basis - kc_mult["high"] * devkc,
        "mid": kc_basis - kc_mult["mid"] * devkc,
        "low": kc_basis - kc_mult["low"] * devkc
    }
    
    squeeze_status = {
        "no_squeeze": (bb_lower < kc_lower["low"]) | (bb_upper > kc_upper["low"]),
        "low_squeeze": (bb_lower >= kc_lower["low"]) | (bb_upper <= kc_upper["low"]),
        "mid_squeeze": (bb_lower >= kc_lower["mid"]) | (bb_upper <= kc_upper["mid"]),
        "high_squeeze": (bb_lower >= kc_lower["high"]) | (bb_upper <= kc_upper["high"])
    }
    
    squeeze_status = pd.DataFrame(squeeze_status).loc[:, ::-1].idxmax(axis=1)
    
    # momentum
    highest_high = feed.high.rolling(mom_length).max()
    lowest_low = feed.low.rolling(mom_length).min()
    sma_close = ta.SMA(feed.close, timeperiod=mom_length)

    avg_price = ((highest_high + lowest_low) / 2 + sma_close) / 2

    mom = ta.LINEARREG(feed.close - avg_price, timeperiod=mom_length)
    
    return kc_lower, kc_upper, bb_lower, bb_upper, bb_basis, squeeze_status, mom

    