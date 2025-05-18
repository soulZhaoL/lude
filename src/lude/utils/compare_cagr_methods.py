"""
CAGR计算方法比较工具

该脚本用于对比不同方法计算的CAGR结果，帮助确定最准确的计算方式
并解释为什么lude.cc使用quantstats期望periods=365与手动实现的CAGR计算结果相近
"""

import pandas as pd
import os
import sys
import numpy as np

# 导入自定义CAGR计算函数
from lude.utils.cagr_utils import (
    compare_cagr_methods,
    format_cagr_results
)
from lude.config.paths import PROJECT_ROOT


def analyze_quantstats_cagr_implementation():
    """
    分析quantstats库CAGR计算的内部实现
    """
    try:
        import inspect
        import quantstats as qs
        
        # 获取quantstats.stats.cagr函数的源代码
        cagr_source = inspect.getsource(qs.stats.cagr)
        
        print("=== QuantStats CAGR函数实现分析 ===")
        # print(cagr_source)
        # print("\n")
        
        # 解释periods参数的含义
        print("periods参数解释:")
        print("在QuantStats中，periods参数表示一年中的交易日数量")
        print("- 默认值为252（美国市场标准交易日）")
        print("- 当设置为365时，假设全年每天都是交易日")
        print("- 该参数直接影响年化计算的倍率")
        
    except ImportError:
        print("无法导入quantstats库，请使用pip install quantstats安装")

def load_test_data():
    """
    加载测试数据，如果有daily_returns.csv文件则使用，否则创建模拟数据
    """
    # 尝试加载已有的收益率数据
    try:
        returns_file = os.path.join(PROJECT_ROOT, 'daily_returns_no_stop.csv')
        daily_returns = pd.read_csv(returns_file, index_col=0)
        
        # 关键修复：将索引转换为日期时间格式
        daily_returns.index = pd.to_datetime(daily_returns.index)
        
        # 确保返回的是带日期索引的Series
        if 'time_return' in daily_returns.columns:
            return daily_returns['time_return']
        elif 'daily_return' in daily_returns.columns:
            return daily_returns['daily_return']
        else:
            # 如果找不到预期的列名，打印所有可用列并使用第一列
            print(f"警告: 未找到预期的收益率列。可用列: {daily_returns.columns.tolist()}")
            return daily_returns.iloc[:, 0]
    except Exception as e:
        print(f"加载收益率数据时出错: {e}")
        print("无法加载收益率数据，请确保daily_returns_no_stop.csv文件存在")
        sys.exit(1)


def explain_cagr_differences(manual_cagr, quantstats_365_cagr):
    """
    解释手动计算的CAGR和quantstats(periods=365)CAGR的差异
    """
    print("=== CAGR计算差异分析 ===")
    
    # 计算差异
    abs_diff = abs(manual_cagr - quantstats_365_cagr)
    pct_diff = abs_diff / manual_cagr * 100 if manual_cagr != 0 else float('inf')
    
    print(f"手动计算CAGR与QuantStats(periods=365)的差异:")
    print(f"- 绝对差异: {abs_diff:.6f}")
    print(f"- 相对差异: {pct_diff:.2f}%")
    
    # 解释差异原因
    print("\n差异原因分析:")
    print("1. 手动计算法基于实际日历年数(天数/365.25)计算年化收益率")
    print("   公式: CAGR = (最终价值/初始价值)^(1/年数) - 1")
    print("   其中年数 = (结束日期 - 开始日期).days / 365.25")
    
    print("\n2. QuantStats(periods=365)的计算公式:")
    print("   公式: CAGR = ((1 + 总收益率)^(365/交易日数)) - 1")
    print("   其中总收益率 = (1 + 每日收益率).prod() - 1")
    
    print("\n当回测周期接近整数年且包含接近全年交易日的数据时，两种方法结果会非常接近")
    print("当设定periods=252时，则假设一年只有252个交易日，年化收益会明显偏低")


if __name__ == "__main__":
    start_date = '20220729'
    end_date = '20250328'
    # 加载测试数据
    returns = load_test_data()
    
    # 打印索引类型信息以便调试
    print(f"测试数据: 从{start_date}到{end_date}的{len(returns)}个交易日")
    print(f"收益率序列索引类型: {type(returns.index)}")
    print(f"前5个索引值: {returns.index[:5]}")
    
    # 比较不同方法的CAGR计算结果
    results = compare_cagr_methods(returns, start_date, end_date)
    print(format_cagr_results(results))
    print("\n")
    
    # 分析quantstats库的CAGR实现
    analyze_quantstats_cagr_implementation()
    print("\n")
    
    # 解释手动计算与quantstats结果的差异
    if 'manual' in results and 'quantstats_365' in results and results['quantstats_365'] is not None:
        explain_cagr_differences(results['manual'], results['quantstats_365'])
    
    # 结论
    print("\n=== 结论 ===")
    print("lude.cc网站使用QuantStats库并设置periods=365计算CAGR")
    print("这种计算方式假设全年365天都是交易日，与基于实际日历年的手动计算结果非常接近")
    print("当使用默认的periods=252时，会得到明显偏低的年化收益率")
    print("建议在计算CAGR时清楚说明使用的年化标准，尤其是处理长期回测数据时")
