"""This module provides common functionality used for both the single time frame and multi time frame analysis of the S&P500 data."""

import multiprocessing
from functools import partial

import numpy as np
import pandas as pd
from tqdm import tqdm

from ..pandas_indicators import big3


def agg_ohlcv(feed: pd.DataFrame, freq: str):
    """Aggregate ohlcv candlesticks into a larger timeframe"""
    if freq == "60min":
        # shift the feed +30m and then -30m to align candlesticks with the hour
        return (
            feed.shift(freq="30min")
            .groupby(pd.Grouper(freq=freq))
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
            .shift(freq="-30min")
        )
    else:
        return (
            feed.groupby(pd.Grouper(freq=freq))
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
        )


def add_signal(feed: pd.DataFrame):  #
    """Compute big3 signal for a ohlcv feed"""
    return feed.assign(big3=big3(feed))


def get_tail(feed: pd.DataFrame, group: pd.DataFrame, t: int):
    """Get t bars after the last bar in the group."""
    return feed[feed.index > group.index[-1]].head(t)


def price_movement(feed: pd.DataFrame, profit_dir: int):
    """Get the peak and trough price movement as a percent over the feed"""
    p_open = feed.open.iloc[0]
    p_close = feed.close.iloc[-1]
    p_max = feed.high.max()
    p_min = feed.low.min()
    return {
        "min": 100 * ((p_min - p_open) / p_open if profit_dir == 1 else (p_open - p_max) / p_open),
        "max": 100 * ((p_max - p_open) / p_open if profit_dir == 1 else (p_open - p_min) / p_open),
        "final": 100 * (p_close - p_open) / p_open * profit_dir,
    }


def launch_mp_job(tickers: dict, function, **kwargs):
    num_processes = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(num_processes)

    pool_func = partial(function, **kwargs)

    results = list(tqdm(pool.imap(pool_func, list(tickers.items())), total=len(tickers)))
    pool.close()
    pool.join()

    ret = [item for sublist in results for item in sublist]

    return ret
