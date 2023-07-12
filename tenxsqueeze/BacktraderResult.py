from collections import defaultdict

import backtrader as bt
import plotly.graph_objects as go
import pyutil

from .plotting import add_spike_cursor, plot_bt_run_wrapper


def print_trade_analysis(analyzer: bt.analyzers.TradeAnalyzer):
    analysis = analyzer.get_analysis()
    stats = {
        "Total Trades": analysis["total"]["total"],
        "Trades Won": analysis["won"]["total"],
        "Trades Lost": analysis["lost"]["total"],
        "Win Percentage": analysis["won"]["total"] / analysis["total"]["total"] * 100,
        "Loss Percentage": analysis["lost"]["total"] / analysis["total"]["total"] * 100,
        "Average PnL": analysis["pnl"]["net"]["average"],
        "Gross PnL": analysis["pnl"]["gross"]["total"],
        "Net PnL": analysis["pnl"]["net"]["total"],
        "Largest Winning Trade": analysis["won"]["pnl"]["max"],
        "Largest Losing Trade": analysis["lost"]["pnl"]["max"],
        "Long Trades": analysis["long"]["total"],
        "Short Trades": analysis["short"]["total"],
        "Long Trades Won": analysis["long"]["won"],
        "Long Trades Lost": analysis["long"]["lost"],
        "Short Trades Won": analysis["short"]["won"],
        "Short Trades Lost": analysis["short"]["lost"],
        "Total Trades Duration": analysis["len"]["total"],
        "Average Trade Duration": analysis["len"]["average"],
        "Max Trade Duration": analysis["len"]["max"],
        "Min Trade Duration": analysis["len"]["min"],
        "Longest Winning Streak": analysis["streak"]["won"]["longest"],
        "Longest Losing Streak": analysis["streak"]["lost"]["longest"],
    }

    pyutil.print_dict_table(stats, headers=["Metric", "Value"], floatfmt=".2f")


def plot_pyfolio_analysis(analyzer: bt.analyzers.PyFolio):
    returns, positions, transactions, gross_lev = analyzer.get_pf_items()
    positions.index -= analyzer.strategy.p.frequency
    transactions.index -= analyzer.strategy.p.frequency
    gross_lev.index -= analyzer.strategy.p.frequency

    fig_returns = go.Figure()
    fig_returns.add_trace(go.Scatter(x=returns.index, y=returns.values, mode="lines", name="Returns"))
    fig_returns.update_layout(title="PyFolio Analyzer - Returns", xaxis_title="Date", yaxis_title="Returns")

    fig_positions = go.Figure()
    for column in positions.columns:
        fig_positions.add_trace(go.Scatter(x=positions.index, y=positions[column], mode="lines", name=column))
    fig_positions.update_layout(title="PyFolio Analyzer - Positions", xaxis_title="Date", yaxis_title="Position")

    fig_transactions = go.Figure(
        data=[
            go.Table(
                header=dict(values=["date"] + list(transactions.columns)),
                cells=dict(
                    values=[[x.strftime("%Y-%m-%d %H:%M:%S") for x in transactions.index]]
                    + [transactions[col].values.tolist() for col in transactions.columns]
                ),
            )
        ]
    )
    fig_transactions.update_layout(title="PyFolio Analyzer - Transactions")

    fig_gross_lev = go.Figure()
    fig_gross_lev.add_trace(go.Scatter(x=gross_lev.index, y=gross_lev.values, mode="lines", name="Gross Leverage"))
    fig_gross_lev.update_layout(
        title="PyFolio Analyzer - Gross Leverage", xaxis_title="Date", yaxis_title="Gross Leverage"
    )

    add_spike_cursor(fig_returns)
    add_spike_cursor(fig_positions)
    add_spike_cursor(fig_transactions)
    add_spike_cursor(fig_gross_lev)
    fig_returns.show()
    fig_positions.show()
    fig_transactions.show()
    fig_gross_lev.show()


def print_drawdown_analysis(analyzer: bt.analyzers.DrawDown):
    analysis = analyzer.get_analysis()
    stats = {
        "Length": analysis["len"],
        "Drawdown": analysis["drawdown"] * 100,
        "Moneydown": analysis["moneydown"],
        "Max Length": analysis["max"]["len"],
        "Max Drawdown": analysis["max"]["drawdown"] * 100,
        "Max Moneydown": analysis["max"]["moneydown"],
    }

    pyutil.print_dict_table(stats, headers=[], floatfmt=".2f")


def print_sharpe_ratio(analyzer: bt.analyzers.SharpeRatio):
    analysis = analyzer.get_analysis()
    stats = {
        "Sharpe Ratio": analysis["sharperatio"],
    }

    pyutil.print_dict_table(stats, headers=[], floatfmt=".2f")


def print_sqn(analyzer: bt.analyzers.SQN):
    analysis = analyzer.get_analysis()
    stats = {
        "SQN": analysis["sqn"],
    }

    pyutil.print_dict_table(stats, headers=[], floatfmt=".2f")


def print_vwr(analyzer: bt.analyzers.VWR):
    analysis = analyzer.get_analysis()
    stats = {
        "VWR": analysis["vwr"],
    }

    pyutil.print_dict_table(stats, headers=[], floatfmt=".2f")


class BacktraderResult(bt.Strategy):
    def get_analyzer(self, analyzer: bt.Analyzer):
        try:
            return list(filter(lambda x: isinstance(x, analyzer), self.analyzers))[0]
        except IndexError:
            pass

    def trade_analysis(self):
        ta = self.get_analyzer(bt.analyzers.TradeAnalyzer)
        if ta is not None:
            print_trade_analysis(ta)
        else:
            print("No trade analyzer found")

    def pyfolio_analysis(self):
        pa = self.get_analyzer(bt.analyzers.PyFolio)
        if pa is not None:
            plot_pyfolio_analysis(pa)
        else:
            print("No pyfolio analyzer found")

    def drawdown_analysis(self):
        dd = self.get_analyzer(bt.analyzers.DrawDown)
        if dd is not None:
            print_drawdown_analysis(dd)
        else:
            print("No drawdown analyzer found")

    def sharpe_analysis(self):
        sr = self.get_analyzer(bt.analyzers.SharpeRatio)
        if sr is not None:
            print_sharpe_ratio(sr)
        else:
            print("No Sharpe Ratio analyzer found")

    def sqn_analysis(self):
        sqn = self.get_analyzer(bt.analyzers.SQN)
        if sqn is not None:
            print_sqn(sqn)
        else:
            print("No SQN analyzer found")

    def vwr_analysis(self):
        vwr = self.get_analyzer(bt.analyzers.VWR)
        if vwr is not None:
            print_vwr(vwr)
        else:
            print("No VWR analyzer found")

    def compact_analysis(self):
        try:
            ta = self.get_analyzer(bt.analyzers.TradeAnalyzer).get_analysis()
            ta_stats = {
                "Total Trades": ta["total"]["total"],
                "Trades Won": ta["won"]["total"],
                "Trades Lost": ta["lost"]["total"],
                "Win Percentage": ta["won"]["total"] / ta["total"]["total"] * 100,
                "Loss Percentage": ta["lost"]["total"] / ta["total"]["total"] * 100,
                "Average PnL": ta["pnl"]["net"]["average"],
                "Gross PnL": ta["pnl"]["gross"]["total"],
                "Net PnL": ta["pnl"]["net"]["total"],
                "Largest Winning Trade": ta["won"]["pnl"]["max"],
                "Largest Losing Trade": ta["lost"]["pnl"]["max"],
                "Long Trades": ta["long"]["total"],
                "Short Trades": ta["short"]["total"],
                "Long Trades Won": ta["long"]["won"],
                "Long Trades Lost": ta["long"]["lost"],
                "Short Trades Won": ta["short"]["won"],
                "Short Trades Lost": ta["short"]["lost"],
                "Total Trades Duration": ta["len"]["total"],
                "Average Trade Duration": ta["len"]["average"],
                "Max Trade Duration": ta["len"]["max"],
                "Min Trade Duration": ta["len"]["min"],
                "Longest Winning Streak": ta["streak"]["won"]["longest"],
                "Longest Losing Streak": ta["streak"]["lost"]["longest"],
            }
        except:
            ta_stats = {}

        try:
            dd = self.get_analyzer(bt.analyzers.DrawDown).get_analysis()
            dd_stats = {
                "Length": dd["len"],
                "Drawdown": dd["drawdown"] * 100,
                "Moneydown": dd["moneydown"],
                "Max Length": dd["max"]["len"],
                "Max Drawdown": dd["max"]["drawdown"] * 100,
                "Max Moneydown": dd["max"]["moneydown"],
            }
        except:
            dd_stats = {}

        stats = {
            "End Value": self.broker.getvalue(),
            **ta_stats,
            **dd_stats,
        }

        return stats

    def plot(self, **kwargs):
        return plot_bt_run_wrapper(self, **kwargs)
