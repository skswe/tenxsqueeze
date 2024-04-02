"""This module contains an API for plotting backtest results
"""
import datetime
from typing import Tuple

import backtrader as bt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .util import undo_backtrader_dt


def add_trace(fig: go.Figure, trace: go.Scatter, row=1, col=1, **add_trace_kwargs):
    fig.add_trace(trace, row=row, col=col, **add_trace_kwargs)


def add_spike_cursor(fig: go.Figure, width=None, height=None, **kwargs):
    spike_settings = {
        "showspikes": True,
        "showline": True,
        "showgrid": True,
        "spikemode": "across",
        "spikesnap": "cursor",
        "spikethickness": 0.5,
        **kwargs,
    }

    fig.update_layout(
        {
            "width": width,
            "height": height,
            "showlegend": True,
            "hovermode": "x",
        }
    )

    fig.update_xaxes(spike_settings)
    fig.update_yaxes(spike_settings)


def plot_bollinger_bands(
    fig: go.Figure, dt: pd.Series, bb_upper: pd.Series, bb_lower: pd.Series, bb_basis: pd.Series = None
):
    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=bb_upper,
            name="bb_upper",
            line=dict(color="#2635ff"),
        ),
    )

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=bb_lower,
            name="bb_lower",
            line=dict(color="#2635ff"),
            fill="tonexty",
            fillcolor="rgba(70, 98, 255, 0.097)",
        ),
    )

    if bb_basis is not None:
        add_trace(
            fig,
            go.Scatter(
                x=dt,
                y=bb_basis,
                name="bb_basis",
                line=dict(color="#ff00d0"),
            ),
        )


def plot_keltner_channel(
    fig: go.Figure,
    dt: pd.Series,
    kc_upper: pd.Series,
    kc_lower: pd.Series,
    kc_basis: pd.Series = None,
    strength: str = "low",
):
    COLOR_MAP = {
        "low": {"outline": "#323232", "fill": "rgba(50, 50, 50, 0.05)"},
        "mid": {"outline": "#ff2d2d", "fill": "rgba(255, 35, 35, 0.05)"},
        "high": {"outline": "#ff6200", "fill": "rgba(255, 98, 0, 0.05)"},
    }

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=kc_upper,
            mode="lines",
            name=f"kc_{strength}_upper",
            line=dict(color=COLOR_MAP[strength]["outline"]),
        ),
    )

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=kc_lower,
            name=f"kc_{strength}_lower",
            line=dict(color=COLOR_MAP[strength]["outline"]),
            fill="tonexty",
            fillcolor=COLOR_MAP[strength]["fill"],
        ),
    )

    if kc_basis is not None:
        add_trace(
            fig,
            go.Scatter(
                x=dt,
                y=kc_basis,
                name=f"kc_{strength}_basis",
                line=dict(color="yellow"),
            ),
        )


def plot_squeeze_pro(
    fig: go.Figure, dt: pd.Series, squeeze_status: pd.Series, momentum: pd.Series, good_momentum: pd.Series = None
):
    SQUEEZE_COLORS = {
        0: "#0ed50e",
        1: "#1b1b1b",
        2: "#ff2b2b",
        3: "#ffac05",
    }

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=[0] * len(dt),
            name="squeeze_status",
            mode="markers",
            marker=dict(
                color=[
                    SQUEEZE_COLORS[int(level)] if not np.isnan(level) else "rgba(0, 0, 0, 0)"
                    for level in squeeze_status
                ]
            ),
            opacity=0.8,
            text=squeeze_status,
            hovertemplate="%{text}",
        ),
        secondary_y=True,
    )

    if good_momentum is not None:
        GOOD_MOMENTUM_OPACITY = {
            0: 0.12,
            1: 0.5,
        }
        opacity = [GOOD_MOMENTUM_OPACITY[int(level)] if not np.isnan(level) else 0 for level in good_momentum]
        color_opacity = [
            f"rgba{tuple(int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)) + (op,)}"
            if op > 0
            else "rgba(0, 0, 0, 0)"
            for color, op in zip(
                pd.concat([momentum, momentum.shift(1)], axis=1).apply(
                    lambda x: ("#0cbeff" if x[0] > 0 else "#ff3939")
                    if abs(x[0]) > abs(x[1])
                    else ("#0829ff" if x[0] > 0 else "#ffeb39"),
                    axis=1,
                ),
                opacity,
            )
        ]
    else:
        opacity = 0.8
        color_opacity = pd.concat([momentum, momentum.shift(1)], axis=1).apply(
            lambda x: ("#0cbeff" if x[0] > 0 else "#ff3939")
            if abs(x[0]) > abs(x[1])
            else ("#0829ff" if x[0] > 0 else "#ffeb39"),
            axis=1,
        )

    add_trace(
        fig,
        go.Bar(
            x=dt,
            y=momentum,
            name="momentum",
            marker=dict(color=color_opacity),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        {
            "yaxis2": {
                "tickformat": ".2f",
                "overlaying": "y",
                "side": "right",
                "range": [-1000, 1000],
            },
        }
    )


def plot_10xbars(
    fig: go.Figure,
    dt: pd.Series,
    ohlc: Tuple[pd.Series, pd.Series, pd.Series, pd.Series],
    d_up: pd.Series,
    d_down: pd.Series,
    sideways: pd.Series,
):
    open, high, low, close = ohlc
    for color in ["green", "red", "yellow"]:
        if color == "green":
            condition = ~sideways & d_up
        elif color == "red":
            condition = ~sideways & d_down
        else:
            condition = sideways

        add_trace(
            fig,
            go.Candlestick(
                x=dt[condition],
                open=open[condition],
                high=high[condition],
                low=low[condition],
                close=close[condition],
                increasing_fillcolor=color,
                decreasing_fillcolor=color,
                name=f"{color} bars",
                opacity=0.6,
            ),
        )


def plot_candlesticks(fig: go.Figure, dt: pd.Series, ohlc: Tuple[pd.Series, pd.Series, pd.Series, pd.Series]):
    open, high, low, close = ohlc
    add_trace(
        fig,
        go.Candlestick(
            x=dt,
            open=open,
            high=high,
            low=low,
            close=close,
            name="Candlesticks",
            opacity=0.6,
        ),
    )


def plot_entries_exits(fig: go.Figure, entries: pd.DataFrame, exits: pd.DataFrame, trades: pd.DataFrame = None):
    entry_colors = {"long": "#51ff51", "short": "#ff5555"}
    entry_symbols = {"long": "triangle-up", "short": "triangle-down"}
    exit_colors = {"long": "#16b5ff", "short": "#d437ff"}
    exit_symbols = {"long": "triangle-down", "short": "triangle-up"}

    add_trace(
        fig,
        go.Scatter(
            x=entries.time,
            y=entries.filled_price,
            mode="markers",
            marker=dict(
                color=[entry_colors[dir] for dir in entries.direction],
                symbol=[entry_symbols[dir] for dir in entries.direction],
                size=12,
                line=dict(width=1),
            ),
            name="Entries",
        ),
    )

    exit_details_params = {
        "text": exits.round(2).type,
        "hovertemplate": "%{y}<br>%{text}",
    }

    if trades is not None:
        exit_details_params["text"] = (
            exit_details_params["text"]
            + "<br>"
            + trades.round(2).apply(lambda x: f"%: {x['pnl_pct']}<br>$: {x['pnl']}", axis=1)
        )

    add_trace(
        fig,
        go.Scatter(
            x=exits.time,
            y=exits.filled_price,
            mode="markers",
            marker=dict(
                color=[exit_colors[dir] for dir in exits.direction],
                symbol=[exit_symbols[dir] for dir in exits.direction],
                size=12,
                line=dict(width=1),
            ),
            name="Exits",
            **exit_details_params,
        ),
    )


def plot_atr_cross(fig: go.Figure, dt: pd.Series, atr_cross: pd.Series):
    COLORS = {
        1: "#0ed50e",
        0: "rgba(0, 0, 0, 0)",
    }

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=[-50] * len(dt),
            name="atr_cross",
            yaxis="y2",
            mode="markers",
            marker=dict(
                symbol="pentagon",
                color=[COLORS[x] if not np.isnan(x) else "rgba(0, 0, 0, 0)" for x in atr_cross],
            ),
            opacity=0.8,
            text=atr_cross,
            hovertemplate="%{text}",
        ),
        secondary_y=True,
    )


def plot_atr(fig: go.Figure, dt: pd.Series, atr: pd.Series):
    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=atr,
            name="atr",
            mode="lines",
            marker=dict(color="#ff2b2b"),
            opacity=0.8,
        ),
        secondary_y=True,
    )

def plot_cum_pnl(fig: go.Figure, dt: pd.Series, cum_pnl: pd.Series):
    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=cum_pnl,
            name="cum_pnl",
            mode="lines",
            marker=dict(color="#ff2b2b"),
            opacity=0.8,
        ),
        row=2,
        col=1,
    )

    add_trace(
        fig,
        go.Scatter(
            x=dt,
            y=[cum_pnl[cum_pnl.notna()].iloc[0]] * len(dt),
            name="zero",
            mode="lines",
            fill="tonexty",
        ),
        row=2,
        col=1,
    )


def plot_bt_run(
    dt: np.array,
    open: np.array,
    high: np.array,
    low: np.array,
    close: np.array,
    bb_upper: np.array = None,
    bb_lower: np.array = None,
    bb_basis: np.array = None,
    kc_upper_low: np.array = None,
    kc_upper_mid: np.array = None,
    kc_upper_high: np.array = None,
    kc_lower_low: np.array = None,
    kc_lower_mid: np.array = None,
    kc_lower_high: np.array = None,
    kc_basis: np.array = None,
    squeeze_status: np.array = None,
    momentum: np.array = None,
    d_up: np.array = None,
    d_down: np.array = None,
    sideways: np.array = None,
    good_momentum: np.array = None,
    atr_cross: np.array = None,
    atr: np.array = None,
    entries: list = None,
    exits: list = None,
    trades: list = None,
    cum_pnl: np.array = None,
    n: int = 0,
    freq: datetime.timedelta = datetime.timedelta(minutes=5),
    width: int = None,
    height: int = None,
):
    N_ROWS = 2
    fig = make_subplots(
        rows=N_ROWS,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
    )

    dt = pd.Series(dt)[-n:]
    open = pd.Series(open)[-n:]
    high = pd.Series(high)[-n:]
    low = pd.Series(low)[-n:]
    close = pd.Series(close)[-n:]

    if bb_upper is not None and bb_lower is not None and bb_basis is not None:
        bb_upper = pd.Series(bb_upper)[-n:]
        bb_lower = pd.Series(bb_lower)[-n:]
        bb_basis = pd.Series(bb_basis)[-n:]
        plot_bollinger_bands(fig, dt, bb_upper, bb_lower, bb_basis)

    if kc_upper_low is not None and kc_lower_low is not None:
        kc_upper_low = pd.Series(kc_upper_low)[-n:]
        kc_lower_low = pd.Series(kc_lower_low)[-n:]
        plot_keltner_channel(fig, dt, kc_upper_low, kc_lower_low, None, "low")

    if kc_upper_mid is not None and kc_lower_mid is not None:
        kc_upper_mid = pd.Series(kc_upper_mid)[-n:]
        kc_lower_mid = pd.Series(kc_lower_mid)[-n:]
        plot_keltner_channel(fig, dt, kc_upper_mid, kc_lower_mid, None, "mid")

    if kc_upper_high is not None and kc_lower_high is not None:
        kc_upper_high = pd.Series(kc_upper_high)[-n:]
        kc_lower_high = pd.Series(kc_lower_high)[-n:]
        plot_keltner_channel(fig, dt, kc_upper_high, kc_lower_high, None, "high")

    if kc_basis is not None:
        kc_basis = pd.Series(kc_basis)[-n:]
        if bb_basis is not None and (kc_basis != bb_basis).any():
            add_trace(
                fig,
                go.Scatter(
                    x=dt,
                    y=kc_basis,
                    name=f"kc_basis",
                    line=dict(color="yellow"),
                ),
            )

    if squeeze_status is not None and momentum is not None:
        squeeze_status = pd.Series(squeeze_status)[-n:]
        momentum = pd.Series(momentum)[-n:]
        if good_momentum is not None:
            good_momentum = pd.Series(good_momentum)[-n:]
        else:
            good_momentum = None
        plot_squeeze_pro(fig, dt, squeeze_status, momentum, good_momentum=good_momentum)

    if d_up is not None and d_down is not None and sideways is not None:
        d_up = pd.Series(d_up).astype(bool)[-n:]
        d_down = pd.Series(d_down).astype(bool)[-n:]
        sideways = pd.Series(sideways).fillna(False).astype(bool)[-n:]
        plot_10xbars(fig, dt, (open, high, low, close), d_up, d_down, sideways)
    else:
        plot_candlesticks(fig, dt, (open, high, low, close))

    if entries is not None and exits is not None:
        entries = (
            pd.DataFrame(entries).pipe(lambda df: df[df.time >= dt.min()])
            if len(entries) > 0
            else pd.DataFrame(columns=["direction", "time", "filled_price", "bar_len"])
        )
        exits = (
            pd.DataFrame(exits).pipe(lambda df: df[df.time >= dt.min()])
            if len(exits) > 0
            else pd.DataFrame(columns=["direction", "time", "filled_price", "type"])
        )
        entries = entries.assign(time=entries.time - freq)
        exits = exits.assign(time=exits.time - freq)

        if trades is not None:
            trades = (
                pd.DataFrame(trades).pipe(lambda df: df[df.entry_time >= dt.min()])
                if len(trades) > 0
                else pd.DataFrame(
                    columns=[
                        "direction",
                        "entry_price",
                        "exit_price",
                        "size",
                        "value",
                        "commission",
                        "pnl",
                        "pnl_pct",
                        "entry_time",
                        "exit_time",
                        "bar_duration",
                    ]
                )
            )
            trades = trades.assign(entry_time=trades.entry_time - freq)
            trades = trades.assign(exit_time=trades.exit_time - freq)

        plot_entries_exits(fig, entries, exits, trades)

    if atr_cross is not None:
        atr_cross = pd.Series(atr_cross)[-n:]
        plot_atr_cross(fig, dt, atr_cross)

    if atr is not None:
        atr = pd.Series(atr)[-n:]
        plot_atr(fig, dt, atr)

    if cum_pnl is not None:
        cum_pnl = pd.Series(cum_pnl)[-n:]
        plot_cum_pnl(fig, dt, cum_pnl)

    for row in range(1, N_ROWS + 1):
        fig.update_yaxes({"tickformat": ".1f"}, row=row, col=1)
        fig.update_xaxes({"rangeslider_visible": False}, row=row, col=1)

    add_spike_cursor(fig, width=width, height=height)
    fig.show()


def plot_bt_run_wrapper(
    res,
    n: int = 0,
    show_bollinger_bands: bool = True,
    show_keltner_channels: bool = True,
    show_squeeze_pro: bool = True,
    show_10xbars: bool = True,
    show_good_momentum: bool = True,
    show_atr_cross: bool = True,
    show_atr: bool = True,
    show_entries_exits: bool = True,
    show_cum_pnl: bool = True,
    width: int = None,
    height: int = None,
):
    dt = undo_backtrader_dt(pd.Series(pd.to_datetime([bt.num2date(x) for x in res.datetime.array])))
    open = res.data.open.array
    high = res.data.high.array
    low = res.data.low.array
    close = res.data.close.array

    if show_bollinger_bands:
        bb_upper = res.sp.bb_upper.array
        bb_lower = res.sp.bb_lower.array
        bb_basis = res.sp.bb_basis.array
    else:
        bb_upper = bb_lower = bb_basis = None

    if show_keltner_channels:
        kc_upper_low = res.sp.kc_upper_low.array
        kc_lower_low = res.sp.kc_lower_low.array
        kc_upper_mid = res.sp.kc_upper_mid.array
        kc_lower_mid = res.sp.kc_lower_mid.array
        kc_upper_high = res.sp.kc_upper_high.array
        kc_lower_high = res.sp.kc_lower_high.array
        kc_basis = res.sp.kc_basis.array
    else:
        kc_upper_low = kc_lower_low = kc_upper_mid = kc_lower_mid = kc_upper_high = kc_lower_high = kc_basis = None

    if show_squeeze_pro:
        squeeze_status = res.sp.squeeze_status.array
        momentum = res.sp.momentum.array
    else:
        squeeze_status = momentum = None

    if show_10xbars:
        d_up = res.tenx.d_up.array
        d_down = res.tenx.d_down.array
        sideways = res.tenx.sideways.array
    else:
        d_up = d_down = sideways = None

    if show_good_momentum:
        good_momentum = res.good_momentum.array
    else:
        good_momentum = None

    if show_atr_cross:
        atr_cross = res.atr_cross.array
    else:
        atr_cross = None

    if show_atr:
        atr = res.atr.array
    else:
        atr = None

    if show_entries_exits:
        entries = res.entries
        exits = res.exits
        trades = res.trades
    else:
        entries = exits = trades = None

    if show_cum_pnl:
        cum_pnl = res.observers.value.array
    else:
        cum_pnl = None

    plot_bt_run(
        dt,
        open,
        high,
        low,
        close,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        bb_basis=bb_basis,
        kc_upper_low=kc_upper_low,
        kc_upper_mid=kc_upper_mid,
        kc_upper_high=kc_upper_high,
        kc_lower_low=kc_lower_low,
        kc_lower_mid=kc_lower_mid,
        kc_lower_high=kc_lower_high,
        kc_basis=kc_basis,
        squeeze_status=squeeze_status,
        momentum=momentum,
        d_up=d_up,
        d_down=d_down,
        sideways=sideways,
        good_momentum=good_momentum,
        atr_cross=atr_cross,
        atr=atr,
        entries=entries,
        exits=exits,
        trades=trades,
        cum_pnl=cum_pnl,
        n=n,
        freq=res.p.frequency,
        width=width,
        height=height,
    )
