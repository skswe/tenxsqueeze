"""This module provides the driver functions to run multi time frame analysis on the S&P500 data.

The analysis determines how long the signal needs to be present before favourable price movements occur.
"""

import numpy as np
import pandas as pd

from .common import add_signal, agg_ohlcv, get_tail, price_movement


def get_consecutive_groups(feeds: list, n_consecutive: int = 2):
    """Gets a list of groups, where each group is a consecutive firing of the signal across all timeframes for n_consecutive bars.
    Note: strong (+-2) and weak (+-1) signals are treated as the same.
    If the signal is repeated after the group, only the first instance will be captured.
    """
    merged_sig = pd.concat(feeds, axis=1).ffill().big3
    pos_groups = [
        merged_sig.loc[group.index[1:]]
        for group in (merged_sig > 0).all(axis=1).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    neg_groups = [
        merged_sig.loc[group.index[1:]]
        for group in (merged_sig < 0).all(axis=1).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    return pos_groups + neg_groups


def get_partial_groups(feeds: list, n_consecutive: int = 2, thresh: float = 0.5):
    """Gets a list of groups, where each group is a consecutive firing of the signal across all timeframes for n_consecutive bars.
    Note: strong (+-2) and weak (+-1) signals are treated as the same.
    If the signal is repeated after the group, only the first instance will be captured.
    """
    merged_sig = pd.concat(feeds, axis=1).ffill().big3
    pos_groups = [
        merged_sig.loc[group.index[1:]]
        for group in ((merged_sig > 0).sum(axis=1) / len(feeds) > thresh).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    neg_groups = [
        merged_sig.loc[group.index[1:]]
        for group in ((merged_sig < 0).sum(axis=1) / len(feeds) > thresh).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    return pos_groups + neg_groups


def analyze_ticker_consecutive(dict_item, N_range, T_range):
    """For each timeframe, get all groups of N consecutive signals. For each group, get the price movement over the next T bars."""
    try:
        ticker, data_5m = dict_item
        data_15m = add_signal(agg_ohlcv(data_5m, "15min"))
        data_30m = add_signal(agg_ohlcv(data_5m, "30min"))
        data_60m = add_signal(agg_ohlcv(data_5m, "60min"))
        data_5m = add_signal(data_5m)

        results = []

        DATAS = [data_5m, data_15m, data_30m, data_60m]

        for n_timeframes in [2, 3, 4]:
            feeds = DATAS[:n_timeframes]
            feed_5m = feeds[0]
            for N in N_range:
                signal_groups = get_consecutive_groups(feeds, N)
                for group in signal_groups:
                    price_dir = np.sign(group.iloc[0, 0])
                    for T in T_range:
                        tail = get_tail(feed_5m, group, T)
                        if len(tail) < T:
                            continue
                        results.append(
                            {
                                "ticker": ticker,
                                "n_tf": n_timeframes,
                                "N": N,
                                "T": T,
                                **price_movement(tail, price_dir),
                                "start": group.index[0],
                                "end": tail.index[-1],
                                "dir": price_dir,
                            }
                        )
        return results

    except Exception as e:
        # print(f"Error on {ticker}")
        # print(e)
        return []


def analyze_ticker_partial(dict_item, N_range, thresh_range, T_range):
    """For each timeframe, get all groups of N consecutive signals. For each group, get the price movement over the next T bars."""
    try:
        ticker, data_5m = dict_item
        data_15m = add_signal(agg_ohlcv(data_5m, "15min"))
        data_30m = add_signal(agg_ohlcv(data_5m, "30min"))
        data_60m = add_signal(agg_ohlcv(data_5m, "60min"))
        data_5m = add_signal(data_5m)

        results = []

        DATAS = [data_5m, data_15m, data_30m, data_60m]

        for n_timeframes in [2, 3, 4]:
            feeds = DATAS[:n_timeframes]
            feed_5m = feeds[0]
            for N in N_range:
                for thresh in thresh_range:
                    signal_groups = get_partial_groups(feeds, N, thresh)
                    for group in signal_groups:
                        price_dir = np.sign(group.iloc[0, 0])
                        for T in T_range:
                            tail = get_tail(feed_5m, group, T)
                            if len(tail) < T:
                                continue
                            results.append(
                                {
                                    "ticker": ticker,
                                    "n_tf": n_timeframes,
                                    "N": N,
                                    "thresh": thresh,
                                    "T": T,
                                    **price_movement(tail, price_dir),
                                    "start": group.index[0],
                                    "end": tail.index[-1],
                                    "dir": price_dir,
                                }
                            )
        return results

    except Exception as e:
        # print(f"Error on {ticker}")
        # print(e)
        return []
