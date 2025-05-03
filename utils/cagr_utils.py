"""
CAGR（复合年化增长率）计算工具

本模块提供多种计算CAGR的方法，便于比较不同计算方式的结果差异。
"""

import pandas as pd
import numpy as np
from typing import Union, Sequence


def calculate_cagr_manually(returns: Union[pd.Series, Sequence[float]], 
                           start_date: str, 
                           end_date: str) -> float:
    """
    手动计算CAGR（复合年化增长率）
    
    公式：CAGR = (最终价值/初始价值)^(1/年数) - 1
    该方法基于实际日历时间（年数）计算
    
    参数:
        returns: 日收益率序列
        start_date: 开始日期，格式为'YYYYMMDD'
        end_date: 结束日期，格式为'YYYYMMDD'
    
    返回:
        cagr: 复合年化增长率
    """
    # 将输入转换为pandas Series
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # 计算累计收益率
    cumulative_return = (1 + returns).prod() - 1
    
    # 计算年数
    start_date = pd.to_datetime(start_date, format='%Y%m%d')
    end_date = pd.to_datetime(end_date, format='%Y%m%d')
    years = (end_date - start_date).days / 365.25
    
    # 计算CAGR
    cagr = (1 + cumulative_return) ** (1 / years) - 1
    
    return cagr


def calculate_cagr_trading_days(returns: Union[pd.Series, Sequence[float]], 
                               periods: int = 252) -> float:
    """
    使用交易日数计算CAGR
    
    该方法基于交易日天数计算，适用于股票、债券等金融市场
    
    参数:
        returns: 日收益率序列
        periods: 一年的交易日数量，默认为252（美国市场），中国市场约为244
                 如果设置为365，则假设全年每天都是交易日
    
    返回:
        cagr: 复合年化增长率
    """
    # 将输入转换为pandas Series
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # 计算总收益率
    total_return = (1 + returns).prod() - 1
    
    # 计算交易日数量
    trading_days = len(returns)
    
    # 计算CAGR
    cagr = ((1 + total_return) ** (periods / trading_days)) - 1
    
    return cagr


def calculate_cagr_geometric(returns: Union[pd.Series, Sequence[float]], 
                            periods: int = 252) -> float:
    """
    使用几何平均日收益率计算CAGR
    
    该方法先计算几何平均日收益率，然后年化到指定交易日数
    
    参数:
        returns: 日收益率序列
        periods: 一年的交易日数量，默认为252
    
    返回:
        cagr: 复合年化增长率
    """
    # 将输入转换为pandas Series
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    # 计算几何平均日收益率
    daily_returns_plus_1 = 1 + returns
    geometric_mean_return = daily_returns_plus_1.prod() ** (1 / len(daily_returns_plus_1)) - 1
    
    # 年化收益率
    cagr = (1 + geometric_mean_return) ** periods - 1
    
    return cagr


def get_quantstats_cagr(returns: Union[pd.Series, Sequence[float]], periods: int = 252) -> float:
    """
    使用quantstats库计算CAGR
    
    参数:
        returns: 日收益率序列
        periods: 一年的交易日数量，默认为252，lude.cc网站使用365
    
    返回:
        cagr: 复合年化增长率
    """
    try:
        import quantstats as qs
        return qs.stats.cagr(returns, periods=periods)
    except ImportError:
        raise ImportError("quantstats库未安装，请使用pip install quantstats安装")


def compare_cagr_methods(returns: Union[pd.Series, Sequence[float]], 
                        start_date: str = None, 
                        end_date: str = None,
                        trading_periods: int = 252,
                        calendar_periods: int = 365) -> dict:
    """
    比较不同CAGR计算方法的结果
    
    参数:
        returns: 日收益率序列
        start_date: 开始日期，格式为'YYYYMMDD'，仅用于手动计算方法
        end_date: 结束日期，格式为'YYYYMMDD'，仅用于手动计算方法
        trading_periods: 交易日年数，默认为252
        calendar_periods: 日历年数，默认为365
    
    返回:
        results: 包含各种方法计算结果的字典
    """
    # 将输入转换为pandas Series
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    results = {}
    
    # 使用quantstats库不同periods设置
    try:
        results['quantstats_252'] = get_quantstats_cagr(returns, periods=trading_periods)
        results['quantstats_365'] = get_quantstats_cagr(returns, periods=calendar_periods)
    except ImportError:
        results['quantstats_252'] = None
        results['quantstats_365'] = None
    
    # 交易日方法
    results['trading_days_252'] = calculate_cagr_trading_days(returns, periods=trading_periods)
    results['trading_days_365'] = calculate_cagr_trading_days(returns, periods=calendar_periods)
    
    # 几何平均法
    results['geometric_252'] = calculate_cagr_geometric(returns, periods=trading_periods)
    results['geometric_365'] = calculate_cagr_geometric(returns, periods=calendar_periods)
    
    # 手动计算法（需要日期）
    if start_date and end_date:
        results['manual'] = calculate_cagr_manually(returns, start_date, end_date)
    
    return results


def format_cagr_results(results: dict) -> str:
    """
    格式化CAGR计算结果为可读文本
    
    参数:
        results: 由compare_cagr_methods生成的结果字典
    
    返回:
        formatted_text: 格式化后的文本
    """
    lines = ["=== CAGR计算方法比较 ==="]
    
    # 添加quantstats结果
    if 'quantstats_252' in results and results['quantstats_252'] is not None:
        lines.append(f"QuantStats (periods=252): {results['quantstats_252']:.6f} ({results['quantstats_252']*100:.2f}%)")
    if 'quantstats_365' in results and results['quantstats_365'] is not None:
        lines.append(f"QuantStats (periods=365): {results['quantstats_365']:.6f} ({results['quantstats_365']*100:.2f}%)")
    
    # 添加交易日方法结果
    if 'trading_days_252' in results:
        lines.append(f"交易日方法 (periods=252): {results['trading_days_252']:.6f} ({results['trading_days_252']*100:.2f}%)")
    if 'trading_days_365' in results:
        lines.append(f"交易日方法 (periods=365): {results['trading_days_365']:.6f} ({results['trading_days_365']*100:.2f}%)")
    
    # 添加几何平均法结果
    if 'geometric_252' in results:
        lines.append(f"几何平均法 (periods=252): {results['geometric_252']:.6f} ({results['geometric_252']*100:.2f}%)")
    if 'geometric_365' in results:
        lines.append(f"几何平均法 (periods=365): {results['geometric_365']:.6f} ({results['geometric_365']*100:.2f}%)")
    
    # 添加手动计算法结果
    if 'manual' in results:
        lines.append(f"手动计算法 (日历年): {results['manual']:.6f} ({results['manual']*100:.2f}%)")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 简单测试案例
    test_returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01])
    test_start_date = "20250101"
    test_end_date = "20250105"
    
    test_results = compare_cagr_methods(test_returns, test_start_date, test_end_date)
    print(format_cagr_results(test_results))
