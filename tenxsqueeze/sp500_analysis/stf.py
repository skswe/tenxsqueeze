"""This module provides the driver functions to run single time frame analysis on the S&P500 data.

The analysis determines how long the signal needs to be present before favourable price movements occur.
"""

import numpy as np
import pandas as pd

from .common import add_signal, agg_ohlcv, get_tail, price_movement


def get_consecutive_groups(sig: pd.Series, n_consecutive: int = 2):
    """Gets a list of groups, where each group is a consecutive firing of the signal for n_consecutive bars. Note: strong (+-2) and weak (+-1) signals are treated as the same.
    If the signal is repeated after the group, only the first instance will be captured.
    """
    pos_groups = [
        sig.loc[group.index[1:]]
        for group in (sig > 0).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    neg_groups = [
        sig.loc[group.index[1:]]
        for group in (sig < 0).rolling(n_consecutive + 1)
        if group.iloc[1:].sum() == n_consecutive and group.iloc[0] == 0
    ]
    return pos_groups + neg_groups


def get_partial_groups(sig: pd.Series, q: int = 5, n: int = 2):
    """Returns a list of groups of length q where at least n bars have a signal in the same direction.
    If the signal is repeated after the group, only the first instance will be captured.
    """
    pos_groups = [
        sig.loc[group.index[1:]]
        for group in (sig > 0).rolling(q + 1)
        if group.iloc[1:].sum() == n and group.iloc[0] == 0 and group.iloc[-1] == 1
    ]
    neg_groups = [
        sig.loc[group.index[1:]]
        for group in (sig < 0).rolling(q + 1)
        if group.iloc[1:].sum() == n and group.iloc[0] == 0 and group.iloc[-1] == 1
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

        for tf, feed in zip(
            ["5m", "15m", "30m", "60m"],
            [data_5m, data_15m, data_30m, data_60m],
        ):
            for N in N_range:
                signal_groups = get_consecutive_groups(feed.big3, N)
                for group in signal_groups:
                    price_dir = np.sign(group.iloc[0])
                    for T in T_range:
                        tail = get_tail(feed, group, T)
                        if len(tail) < T:
                            continue
                        results.append(
                            {
                                "ticker": ticker,
                                "tf": tf,
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


def analyze_ticker_partial(dict_item, NQ_range, T_range):
    """For each timeframe, get all groups of N signals in Q bars. For each group, get the price movement over the next T bars."""
    try:
        ticker, data_5m = dict_item
        data_15m = add_signal(agg_ohlcv(data_5m, "15min"))
        data_30m = add_signal(agg_ohlcv(data_5m, "30min"))
        data_60m = add_signal(agg_ohlcv(data_5m, "60min"))
        data_5m = add_signal(data_5m)

        results = []

        for tf, feed in zip(
            ["5m", "15m", "30m", "60m"],
            [data_5m, data_15m, data_30m, data_60m],
        ):
            for N, Q in NQ_range:
                signal_groups = get_partial_groups(feed.big3, Q, N)
                for group in signal_groups:
                    price_dir = np.sign(group.sum())
                    for T in T_range:
                        tail = get_tail(feed, group, T)
                        if len(tail) < T:
                            continue
                        results.append(
                            {
                                "ticker": ticker,
                                "tf": tf,
                                "N": N,
                                "Q": Q,
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
