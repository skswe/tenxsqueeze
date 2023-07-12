import datetime

import backtrader as bt
import cryptomart as cm
import pandas as pd
import tenxsqueeze as txs
from dotenv import load_dotenv
from pyutil import cached

from .ProgressCerebro import ProgressCerebro

load_dotenv()

mapping = {
    "interval_1m": datetime.timedelta(minutes=1),
    "interval_3m": datetime.timedelta(minutes=3),
    "interval_5m": datetime.timedelta(minutes=5),
    "interval_15m": datetime.timedelta(minutes=15),
    "interval_30m": datetime.timedelta(minutes=30),
    "interval_1h": datetime.timedelta(hours=1),
    "interval_2h": datetime.timedelta(hours=2),
    "interval_4h": datetime.timedelta(hours=4),
    "interval_6h": datetime.timedelta(hours=6),
    "interval_8h": datetime.timedelta(hours=8),
    "interval_12h": datetime.timedelta(hours=12),
    "interval_1d": datetime.timedelta(days=1),
    "interval_3d": datetime.timedelta(days=3),
}


class Driver:
    def __init__(
        self,
        exchange="binance",
        symbol="BTC",
        start_date=(2022, 1, 20),
        end_date=(2022, 6, 20),
        granular_interval="interval_5m",
        indicator_interval="interval_1h",
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.granular_interval = granular_interval
        self.indicator_interval = indicator_interval

        self.cm_client = cm.Client(quiet=True, instrument_cache_kwargs={"refresh": False})
        # ind_data = self.cm_client.ohlcv(
        #     exchange, symbol, "perpetual", starttime=start_date, endtime=end_date, interval=indicator_interval
        # )
        self.gran_data = self.cm_client.ohlcv(
            exchange, symbol, "perpetual", starttime=start_date, endtime=end_date, interval=granular_interval
        )

        self.granular_timeframe = {
            "s": bt.TimeFrame.Seconds,
            "m": bt.TimeFrame.Minutes,
            "d": bt.TimeFrame.Days,
        }[granular_interval[-1]]

        self.granular_label = granular_interval.split("_")[1]
        self.granular_compression = int(self.granular_label[:-1])

        granular_timedelta = {
            "s": datetime.timedelta(seconds=1),
            "m": datetime.timedelta(minutes=1),
            "h": datetime.timedelta(hours=1),
            "d": datetime.timedelta(days=1),
        }[granular_interval[-1]]

        indicator_timedelta = mapping[indicator_interval]

        self.replay_compression = int(indicator_timedelta / granular_timedelta)
        self.frequency = self.granular_compression * granular_timedelta

    def run(
        self,
        logging=False,
        progress_bar=False,
        log_file="log.txt",
        save_results=True,
        squeeze_pro_length: int = 20,
        atr_length: int = 10,
        adx_length: int = 14,
        tp_trail_percent: float = 0.4,
        sl_trail_percent: float = 0.7,
        percent_is_atr: bool = True,
        tp_atr_multiplier: float = 2.3,
        max_trade_duration: int = 9,
        use_good_momentum: bool = True,
        run: bool = True,
        cache_logs: bool = False,
    ):
        cerebro = ProgressCerebro()

        granular = bt.feeds.PandasData(
            dataname=txs.util.fix_dt_for_backtrader(self.gran_data).set_index("open_time"),
            name=f"{self.exchange}_{self.symbol}_{self.granular_label})",
            timeframe=self.granular_timeframe,
            compression=self.granular_compression,
        )

        cerebro.replaydata(granular, timeframe=self.granular_timeframe, compression=self.replay_compression)

        strategy_params = dict(
            logging=logging,
            progress_bar=progress_bar,
            log_file=log_file,
            save_results=save_results,
            squeeze_pro_length=squeeze_pro_length,
            atr_length=atr_length,
            adx_length=adx_length,
            tp_trail_percent=tp_trail_percent,
            sl_trail_percent=sl_trail_percent,
            percent_is_atr=percent_is_atr,
            tp_atr_multiplier=tp_atr_multiplier,
            max_trade_duration=max_trade_duration,
            use_good_momentum=use_good_momentum,
            frequency=self.frequency,
            cache_logs=cache_logs,
        )

        if any(isinstance(x, list) for x in strategy_params.values()):
            # Multi-run, use multiple cores to run in parallel
            cerebro.optstrategy(
                txs.TenXSqueeze,
                **strategy_params,
            )
        else:
            # Single run, use single core
            cerebro.addstrategy(
                txs.TenXSqueeze,
                **strategy_params,
            )


        cerebro.addanalyzer(bt.analyzers.PyFolio, _name="pyfolio")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
        cerebro.addanalyzer(bt.analyzers.VWR, _name="vwr")
        cerebro.addobserver(bt.observers.Value, _name="value")

        cerebro.broker.setcash(100000.0)
        cerebro.broker.setcommission(commission=0.0006)

        if not run:
            return cerebro

        ret = cerebro.run(stdstats=False, optreturn=False, maxcpus=14)
        return pd.concat(ret, axis=1).T if len(ret) > 0 and isinstance(ret[0], pd.Series) else (ret[0] if len(ret) > 0 else ret)

    def load_results(self, path=None):
        return pd.read_csv(path)
