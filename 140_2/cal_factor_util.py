# import pandas as pd
import ta

# df = pd.read_parquet('cb_data.pq')
# index = pd.read_parquet('index.pq')


def simple_momentum(data, period=1):
    """
    简单动量
    :param data:
    :param period:
    :return:
    """
    return data.pct_change(periods=period)

def rsi(data, period=1):
    """RSI相对强弱指标"""
    return ta.momentum.RSIIndicator(data['close'], window=period).rsi()

def stochastic_oscillator(data, k_period=14, d_period=3):
    """
    随机振荡指标
    :param data:
    :param k_period:
    :param d_period:
    :return:
    """
    stoch = ta.momentum.StochasticOscillator(data['high'], data['low'], data['close'], window=k_period, smooth_window=d_period)
    return stoch.stoch(), stoch.stoch_signal()

def macd(data, fast_period=12, slow_period=26, signal_period=9):
    """
    MACD指标
    :param data:
    :param fast_period:
    :param slow_period:
    :param signal_period:
    :return:
    """
    macd_indicator = ta.trend.MACD(data['close'], window_slow=slow_period, window_fast=fast_period, window_sign=signal_period)
    return macd_indicator.macd(), macd_indicator.macd_signal(), macd_indicator.macd_diff()

def adx(data, period=14):
    """
    平均趋向指数
    :param data:
    :param period:
    :return:
    """
    return ta.trend.ADXIndicator(data['high'], data['low'], data['close'], window=period).adx()

def momentum(data, period=12):
    """
    动量指标
    :param data:
    :param period:
    :return:
    """
    return data.diff(periods=period)

def velocity(data, period=5):
    """
    速度指标
    :param data:
    :param period:
    :return:
    """
    return data.diff(periods=period) / period

def pvt(data):
    """
    价格和成交量趋势指标
    :param data:
    :return:
    """
    return (data['vol'] * ((data['close'] - data['close'].shift(1)) / data['close'].shift(1))).cumsum()

def volatility_breakout(data, period=20):
    """
    波动率突破指标
    :param data:
    :param period:
    :return:
    """
    high_low = data['high'] - data['low']
    return high_low.rolling(window=period).mean()

def trend_strength(data, short_window=12, long_window=26):
    """
    趋势强度指标
    :param data:
    :param short_window:
    :param long_window:
    :return:
    """
    short_ma = data['close'].rolling(window=short_window).mean()
    long_ma = data['close'].rolling(window=long_window).mean()
    return short_ma - long_ma

def dema(data, period=21):
    """
    双指数移动平均线
    :param data:
    :param period:
    :return:
    """
    ema1 = ta.trend.ema_indicator(data['close'], window=period)
    ema2 = ta.trend.ema_indicator(ema1, window=period)
    return 2 * ema1 - ema2
#
# df['pc1'] = simple_momentum(df['close'], period=1)
# df['pc3'] = simple_momentum(df['close'], period=3)
# df['pc5'] = simple_momentum(df['close'], period=5)
# df['pc7'] = simple_momentum(df['close'], period=7)
#
# df['rsi1'] = rsi(df, period=1)
# df['rsi3'] = rsi(df, period=3)
# df['rsi5'] = rsi(df, period=5)
# df['rsi7'] = rsi(df, period=7)
#
# df['stoch1'], df['stoch_signal1'] = stochastic_oscillator(df, k_period=3, d_period=1)
# df['stoch2'], df['stoch_signal2'] = stochastic_oscillator(df, k_period=7, d_period=2)
# df['stoch3'], df['stoch_signal3'] = stochastic_oscillator(df, k_period=14, d_period=3)
#
# df['macd'], df['macd_signal'], df['macd_diff'] = macd(df, fast_period=12, slow_period=26, signal_period=9)
#
# df['adx7'] = adx(df, period=7)
# df['adx14'] = adx(df, period=14)
#
# df['momentum3'] = momentum(df['close'], period=3)
# df['momentum6'] = momentum(df['close'], period=6)
# df['momentum12'] = momentum(df['close'], period=12)
#
# df['velocity3'] = velocity(df['close'], period=3)
# df['velocity5'] = velocity(df['close'], period=5)
# df['velocity7'] = velocity(df['close'], period=7)
#
# df['pvt'] = pvt(df)
#
# df['volatility_stk5'] = volatility_breakout(df, period=5)
# df['volatility_stk10'] = volatility_breakout(df, period=10)
# df['volatility_stk20'] = volatility_breakout(df, period=20)
#
# df['trend_strength'] = trend_strength(df, short_window=12, long_window=26)
#
# df['dema5'] = dema(df, period=5)
# df['dema21'] = dema(df, period=21)
#
#
#
#
# print(df.head())
# print(df.columns)