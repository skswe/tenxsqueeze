import pyutil

from .driver import Driver

if __name__ == "__main__":
    driver = Driver(
        exchange="binance",
        symbol="BTC",
        start_date=(2022, 1, 20),
        end_date=(2023, 6, 20),
        granular_interval="interval_5m",
        indicator_interval="interval_1h",
    )

    res = driver.run(
        logging=False,
        progress_bar=False,
        log_file="log.txt",
        save_results=True,
        squeeze_pro_length=20,
        atr_length=10,
        adx_length=14,
        tp_trail_percent=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3],
        sl_trail_percent=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3],
        percent_is_atr=True,
        tp_atr_multiplier=2,
        max_trade_duration=[9, 14, 29, 24],
        use_good_momentum=True,
        run=True,
        cache_logs=False,
    )
