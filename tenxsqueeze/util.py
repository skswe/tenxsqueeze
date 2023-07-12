import pandas as pd


def fix_dt_for_backtrader(df):
    if isinstance(df, pd.DataFrame):
        return df.assign(open_time=df.open_time + df.open_time.diff().median())
    elif isinstance(df, pd.Series):
        return df + df.diff().median()
    else:
        raise TypeError("df must be a pandas DataFrame or Series")


def undo_backtrader_dt(df):
    if isinstance(df, pd.DataFrame):
        return df.assign(open_time=df.open_time - df.open_time.diff().median())
    elif isinstance(df, pd.Series):
        return df - df.diff().median()
    else:
        raise TypeError("df must be a pandas DataFrame or Series")
