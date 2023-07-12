import csv
import gc
import itertools
import multiprocessing
import os
from copy import deepcopy

import backtrader as bt
import pandas as pd
import pyutil
from backtrader import indicator, linebuffer, observers
from backtrader.strategy import SignalStrategy, Strategy
from backtrader.utils import tzparse
from backtrader.utils.py3 import integer_types, map
from backtrader.writer import WriterFile
from tqdm import tqdm

from .strategies.BaseStrategy import BaseStrategy
from .util import undo_backtrader_dt

filelock = multiprocessing.Lock()
listlock = multiprocessing.Lock()


class OptReturn(object):
    def __init__(self, params, **kwargs):
        self.p = self.params = params
        for k, v in kwargs.items():
            setattr(self, k, v)


class ProgressCerebro(bt.Cerebro):
    @staticmethod
    def get_id_keys(strategy: BaseStrategy):
        keys = deepcopy(strategy.params._getkwargs())
        del keys["logging"]
        del keys["progress_bar"]
        del keys["log_file"]
        del keys["save_results"]
        del keys["cache_logs"]
        keys["frequency"] = str(keys["frequency"])
        return keys

    def get_result_path(self, strategy: BaseStrategy):
        root = os.path.join(os.getenv("ACTIVE_DEV_PATH", "/home/stefano/dev/active"), "10xsqueeze", "results")
        directory_keys = {
            "strategy": strategy.strategy_name if hasattr(strategy, "strategy_name") else strategy.__name__,
            "start": undo_backtrader_dt(self.datas[0]._dataname.reset_index()).open_time.iloc[0],
            "end": self.datas[0]._dataname.reset_index().open_time.iloc[-1],
        }

        directory_path = root
        for key, value in directory_keys.items():
            directory_path = os.path.join(directory_path, f"{key}_{value}")

        return directory_path

    def get_latest_results_file(self, strategy: BaseStrategy):
        result_path = self.get_result_path(strategy)
        # Assumes that the files are named results_1.csv, results_2.csv, etc.
        existing_files = {k: int(k.split("_")[1].rstrip(".csv")) if "_" in k else 0 for k in os.listdir(result_path)}

        # Filepath is set to the largest number, or results.csv if no files exist
        file_path = (
            os.path.join(result_path, max(existing_files, key=existing_files.get))
            if len(existing_files) > 0
            else os.path.join(result_path, "results.csv")
        )

        return file_path, existing_files

    def pre_strategy(self, strategy: BaseStrategy):
        if strategy.params.save_results:
            result_path = self.get_result_path(strategy)
            keys = self.get_id_keys(strategy)
            os.makedirs(result_path, exist_ok=True)
            existing_files = {
                k: int(k.split("_")[1].rstrip(".csv")) if "_" in k else 0 for k in os.listdir(result_path)
            }
            for file in existing_files:
                df = pd.read_csv(os.path.join(result_path, file))
                df_keys_only = df[[col for col in df.columns if not col[0].isupper()]]
                this_run_keys = pd.Series(keys)
                keys_match = df_keys_only.apply(lambda row: this_run_keys.equals(row), axis=1)
                if keys_match.any():
                    if strategy.params.cache_logs:
                        print(f"Skipping {strategy.strategy_name} with {keys} as it already exists")

                    matching_row = df.loc[keys_match].iloc[0]
                    return matching_row

        return False

    def post_strategy(self, strategy: BaseStrategy):
        if strategy.params.save_results:
            result_path = self.get_result_path(strategy)
            keys = self.get_id_keys(strategy)
            metrics = strategy.compact_analysis()

            with filelock:
                os.makedirs(result_path, exist_ok=True)

                file_path, existing_files = self.get_latest_results_file(strategy)

                # Check if a new file needs to be created
                new_file = len(existing_files) == 0

                # Check if the file already exists
                if os.path.exists(file_path):
                    header = pd.read_csv(file_path, nrows=1).columns.tolist()
                    # Check if the header matches the expected keys and metrics
                    if header != list(keys.keys()) + list(metrics.keys()):
                        # Create a new file name if the header doesn't match
                        file_path = pyutil.unique_file_name(file_path)
                        new_file = True

                # Open the file in append mode
                with open(file_path, "a", newline="") as f:
                    writer = csv.writer(f)

                    # Write the header if it's a new file
                    if new_file:
                        writer.writerow(list(keys.keys()) + list(metrics.keys()))

                    # Write the values to the file
                    writer.writerow(list(keys.values()) + list(metrics.values()))

    def run(self, **kwargs):
        """The core method to perform backtesting. Any ``kwargs`` passed to it
        will affect the value of the standard parameters ``Cerebro`` was
        instantiated with.

        If ``cerebro`` has not datas the method will immediately bail out.

        It has different return values:

          - For No Optimization: a list contanining instances of the Strategy
            classes added with ``addstrategy``

          - For Optimization: a list of lists which contain instances of the
            Strategy classes added with ``addstrategy``
        """
        self._event_stop = False  # Stop is requested

        if not self.datas:
            return []  # nothing can be run

        pkeys = self.params._getkeys()
        for key, val in kwargs.items():
            if key in pkeys:
                setattr(self.params, key, val)

        # Manage activate/deactivate object cache
        linebuffer.LineActions.cleancache()  # clean cache
        indicator.Indicator.cleancache()  # clean cache

        linebuffer.LineActions.usecache(self.p.objcache)
        indicator.Indicator.usecache(self.p.objcache)

        self._dorunonce = self.p.runonce
        self._dopreload = self.p.preload
        self._exactbars = int(self.p.exactbars)

        if self._exactbars:
            self._dorunonce = False  # something is saving memory, no runonce
            self._dopreload = self._dopreload and self._exactbars < 1

        self._doreplay = self._doreplay or any(x.replaying for x in self.datas)
        if self._doreplay:
            # preloading is not supported with replay. full timeframe bars
            # are constructed in realtime
            self._dopreload = False

        if self._dolive or self.p.live:
            # in this case both preload and runonce must be off
            self._dorunonce = False
            self._dopreload = False

        self.runwriters = list()

        # Add the system default writer if requested
        if self.p.writer is True:
            wr = WriterFile()
            self.runwriters.append(wr)

        # Instantiate any other writers
        for wrcls, wrargs, wrkwargs in self.writers:
            wr = wrcls(*wrargs, **wrkwargs)
            self.runwriters.append(wr)

        # Write down if any writer wants the full csv output
        self.writers_csv = any(map(lambda x: x.p.csv, self.runwriters))

        self.runstrats = list()

        if self.signals:  # allow processing of signals
            signalst, sargs, skwargs = self._signal_strat
            if signalst is None:
                # Try to see if the 1st regular strategy is a signal strategy
                try:
                    signalst, sargs, skwargs = self.strats.pop(0)
                except IndexError:
                    pass  # Nothing there
                else:
                    if not isinstance(signalst, SignalStrategy):
                        # no signal ... reinsert at the beginning
                        self.strats.insert(0, (signalst, sargs, skwargs))
                        signalst = None  # flag as not presetn

            if signalst is None:  # recheck
                # Still None, create a default one
                signalst, sargs, skwargs = SignalStrategy, tuple(), dict()

            # Add the signal strategy
            self.addstrategy(
                signalst,
                _accumulate=self._signal_accumulate,
                _concurrent=self._signal_concurrent,
                signals=self.signals,
                *sargs,
                **skwargs,
            )

        if not self.strats:  # Datas are present, add a strategy
            self.addstrategy(Strategy)

        print("First strategy params")
        print(
            pyutil.format_dict(
                {
                    "dopreload": self._dopreload,
                    "dorunonce": self._dorunonce,
                    "dooptimize": self._dooptimize,
                    **list(deepcopy(self.strats[0]))[0][2],
                }
            )
        )

        iterstrats = itertools.product(*self.strats)
        if not self._dooptimize or self.p.maxcpus == 1:
            # If no optimmization is wished ... or 1 core is to be used
            # let's skip process "spawning"
            for iterstrat in iterstrats:
                runstrat = self.runstrategies(iterstrat)
                self.runstrats.append(runstrat)
                if self._dooptimize:
                    for cb in self.optcbs:
                        cb(runstrat)  # callback receives finished strategy
        else:
            if self.p.optdatas and self._dopreload and self._dorunonce:
                for data in self.datas:
                    data.reset()
                    if self._exactbars < 1:  # datas can be full length
                        data.extend(size=self.params.lookahead)
                    data._start()
                    if self._dopreload:
                        data.preload()

            pool = multiprocessing.Pool(self.p.maxcpus or None)
            total_cached = 0
            progress = tqdm(total=len(list(deepcopy(iterstrats))))
            cached_strats = []
            for r in pool.imap(self, iterstrats):
                if isinstance(r[0], pd.Series):
                    with listlock:
                        cached_strats.append(r[0])
                    total_cached += 1
                    progress.set_postfix(cached=total_cached)
                else:
                    for cb in self.optcbs:
                        cb(r)  # callback receives finished strategy
                    del r
                    gc.collect()

                progress.update(1)

            pool.close()

            if self.p.optdatas and self._dopreload and self._dorunonce:
                for data in self.datas:
                    data.stop()

            return cached_strats

        if not self._dooptimize:
            # avoid a list of list for regular cases
            return self.runstrats[0]

        return self.runstrats

    def runstrategies(self, iterstrat, predata=False):
        """
        Internal method invoked by ``run``` to run a set of strategies
        """
        # print(f"I am process {multiprocessing.current_process().name} and my length is {len(iterstrat)}\n")
        self._init_stcount()

        self.runningstrats = runstrats = list()
        for store in self.stores:
            store.start()

        if self.p.cheat_on_open and self.p.broker_coo:
            # try to activate in broker
            if hasattr(self._broker, "set_coo"):
                self._broker.set_coo(True)

        if self._fhistory is not None:
            self._broker.set_fund_history(self._fhistory)

        for orders, onotify in self._ohistory:
            self._broker.add_order_history(orders, onotify)

        self._broker.start()

        for feed in self.feeds:
            feed.start()

        if self.writers_csv:
            wheaders = list()
            for data in self.datas:
                if data.csv:
                    wheaders.extend(data.getwriterheaders())

            for writer in self.runwriters:
                if writer.p.csv:
                    writer.addheaders(wheaders)

        # self._plotfillers = [list() for d in self.datas]
        # self._plotfillers2 = [list() for d in self.datas]

        if not predata:
            for data in self.datas:
                data.reset()
                if self._exactbars < 1:  # datas can be full length
                    data.extend(size=self.params.lookahead)
                data._start()
                if self._dopreload:
                    data.preload()

        cached_strats = []
        for stratcls, sargs, skwargs in iterstrat:
            sargs = self.datas + list(sargs)
            try:
                strat = stratcls(*sargs, **skwargs)
                cached_row = self.pre_strategy(strat)
                if cached_row is not False:
                    cached_strats.append(cached_row)
                    continue

            except bt.errors.StrategySkipError:
                continue  # do not add strategy to the mix

            if self.p.oldsync:
                strat._oldsync = True  # tell strategy to use old clock update
            if self.p.tradehistory:
                strat.set_tradehistory()
            runstrats.append(strat)

        tz = self.p.tz
        if isinstance(tz, integer_types):
            tz = self.datas[tz]._tz
        else:
            tz = tzparse(tz)

        if runstrats:
            # loop separated for clarity
            defaultsizer = self.sizers.get(None, (None, None, None))
            for idx, strat in enumerate(runstrats):
                if self.p.stdstats:
                    strat._addobserver(False, observers.Broker)
                    if self.p.oldbuysell:
                        strat._addobserver(True, observers.BuySell)
                    else:
                        strat._addobserver(True, observers.BuySell, barplot=True)

                    if self.p.oldtrades or len(self.datas) == 1:
                        strat._addobserver(False, observers.Trades)
                    else:
                        strat._addobserver(False, observers.DataTrades)

                for multi, obscls, obsargs, obskwargs in self.observers:
                    strat._addobserver(multi, obscls, *obsargs, **obskwargs)

                for indcls, indargs, indkwargs in self.indicators:
                    strat._addindicator(indcls, *indargs, **indkwargs)

                for ancls, anargs, ankwargs in self.analyzers:
                    strat._addanalyzer(ancls, *anargs, **ankwargs)

                sizer, sargs, skwargs = self.sizers.get(idx, defaultsizer)
                if sizer is not None:
                    strat._addsizer(sizer, *sargs, **skwargs)

                strat._settz(tz)
                strat._start()

                for writer in self.runwriters:
                    if writer.p.csv:
                        writer.addheaders(strat.getwriterheaders())

            if not predata:
                for strat in runstrats:
                    strat.qbuffer(self._exactbars, replaying=self._doreplay)

            for writer in self.runwriters:
                writer.start()

            # Prepare timers
            self._timers = []
            self._timerscheat = []
            for timer in self._pretimers:
                # preprocess tzdata if needed
                timer.start(self.datas[0])

                if timer.params.cheat:
                    self._timerscheat.append(timer)
                else:
                    self._timers.append(timer)

            if self._dopreload and self._dorunonce:
                if self.p.oldsync:
                    self._runonce_old(runstrats)
                else:
                    self._runonce(runstrats)
            else:
                if self.p.oldsync:
                    self._runnext_old(runstrats)
                else:
                    self._runnext(runstrats)

            for strat in runstrats:
                strat._stop()
                self.post_strategy(strat)

        self._broker.stop()

        if not predata:
            for data in self.datas:
                data.stop()

        for feed in self.feeds:
            feed.stop()

        for store in self.stores:
            store.stop()

        self.stop_writers(runstrats)

        if self._dooptimize and self.p.optreturn:
            # Results can be optimized
            results = list()
            for strat in runstrats:
                for a in strat.analyzers:
                    a.strategy = None
                    a._parent = None
                    for attrname in dir(a):
                        if attrname.startswith("data"):
                            setattr(a, attrname, None)

                oreturn = OptReturn(strat.params, analyzers=strat.analyzers, strategycls=type(strat))
                results.append(oreturn)

            return results

        return runstrats + cached_strats
