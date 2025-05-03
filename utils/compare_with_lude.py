"""
对比CAGR计算方法与lude.cc网站结果

该脚本读取现有的收益率数据，使用多种方法计算CAGR，
并对比哪种计算方法的结果与lude.cc网站最为接近。
"""

import os
import sys
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径，以便能够导入utils模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cagr_utils import (
    compare_cagr_methods,
    format_cagr_results
)

# lude.cc网站参考收益率 - 可配置
LUDE_CAGR_NO_STOP = 0.0258  # 不止盈情况
LUDE_CAGR_WITH_STOP = 0.4573	  # 启用止盈情况

def find_closest_method(cagr_results, target_cagr):
    """
    找出最接近目标CAGR的计算方法
    
    参数:
        cagr_results: 各种方法的CAGR计算结果
        target_cagr: 目标CAGR值
    
    返回:
        closest_method: 最接近的计算方法
        closest_diff: 最小差异值
    """
    closest_method = None
    closest_diff = float('inf')
    
    for method, cagr in cagr_results.items():
        if cagr is not None:
            diff = abs(cagr - target_cagr)
            if diff < closest_diff:
                closest_diff = diff
                closest_method = method
    
    return closest_method, closest_diff

def main():
    # 加载收益率数据
    try:
        # 先尝试加载不止盈情况的收益率
        returns_no_stop_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'daily_returns_no_stop.csv')
        returns_no_stop_df = pd.read_csv(returns_no_stop_file, index_col=0)
        
        # 转换索引为日期时间格式
        returns_no_stop_df.index = pd.to_datetime(returns_no_stop_df.index)
        returns_no_stop = returns_no_stop_df['daily_return']
        
        # 再尝试加载启用止盈情况的收益率
        returns_with_stop_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'daily_returns_with_stop.csv')
        returns_with_stop_df = pd.read_csv(returns_with_stop_file, index_col=0)
        
        # 转换索引为日期时间格式
        returns_with_stop_df.index = pd.to_datetime(returns_with_stop_df.index)
        returns_with_stop = returns_with_stop_df['daily_return']
        
        # 提取日期范围
        start_date = returns_no_stop.index[0]
        end_date = returns_no_stop.index[-1]
        
        # 转换日期格式
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
    except Exception as e:
        print(f"加载收益率数据时出错: {e}")
        sys.exit(1)
    
    print("=" * 80)
    print("开始比较各种CAGR计算方法与lude.cc网站结果")
    print("=" * 80)
    
    # 1. 不止盈情况
    print("\n1. 不止盈情况的CAGR计算比较")
    print("-" * 50)
    
    # 计算所有方法的CAGR
    results_no_stop = compare_cagr_methods(
        returns_no_stop, 
        start_date=start_date_str, 
        end_date=end_date_str,
        trading_periods=252,  # 标准交易日
        calendar_periods=365  # 日历日
    )
    
    # 打印详细结果
    print("各方法计算结果:")
    formatted_results = format_cagr_results(results_no_stop)
    print(formatted_results)
    
    # 找出最接近lude.cc结果的方法
    closest_method_no_stop, closest_diff_no_stop = find_closest_method(results_no_stop, LUDE_CAGR_NO_STOP)
    print(f"\nlude.cc网站不止盈结果: {LUDE_CAGR_NO_STOP:.6f} ({LUDE_CAGR_NO_STOP*100:.2f}%)")
    print(f"最接近lude.cc的计算方法: {closest_method_no_stop}")
    print(f"最小差异: {closest_diff_no_stop:.6f} ({closest_diff_no_stop*100:.2f}%)")
    print(f"计算结果: {results_no_stop[closest_method_no_stop]:.6f} ({results_no_stop[closest_method_no_stop]*100:.2f}%)")
    
    # 2. 启用止盈情况
    print("\n\n2. 启用止盈情况的CAGR计算比较")
    print("-" * 50)
    
    # 计算所有方法的CAGR
    results_with_stop = compare_cagr_methods(
        returns_with_stop, 
        start_date=start_date_str, 
        end_date=end_date_str,
        trading_periods=252,  # 标准交易日
        calendar_periods=365  # 日历日
    )
    
    # 打印详细结果
    print("各方法计算结果:")
    formatted_results = format_cagr_results(results_with_stop)
    print(formatted_results)
    
    # 找出最接近lude.cc结果的方法
    closest_method_with_stop, closest_diff_with_stop = find_closest_method(results_with_stop, LUDE_CAGR_WITH_STOP)
    print(f"\nlude.cc网站启用止盈结果: {LUDE_CAGR_WITH_STOP:.6f} ({LUDE_CAGR_WITH_STOP*100:.2f}%)")
    print(f"最接近lude.cc的计算方法: {closest_method_with_stop}")
    print(f"最小差异: {closest_diff_with_stop:.6f} ({closest_diff_with_stop*100:.2f}%)")
    print(f"计算结果: {results_with_stop[closest_method_with_stop]:.6f} ({results_with_stop[closest_method_with_stop]*100:.2f}%)")
    
    # 综合分析
    print("\n\n3. 综合分析")
    print("-" * 50)
    print(f"不止盈情况最匹配方法: {closest_method_no_stop}")
    print(f"启用止盈情况最匹配方法: {closest_method_with_stop}")
    
    # 计算所有方法与实际lude.cc结果的平均偏差
    method_avg_diffs = {}
    for method in results_no_stop.keys():
        if method in results_with_stop and results_no_stop[method] is not None and results_with_stop[method] is not None:
            diff_no_stop = abs(results_no_stop[method] - LUDE_CAGR_NO_STOP)
            diff_with_stop = abs(results_with_stop[method] - LUDE_CAGR_WITH_STOP)
            avg_diff = (diff_no_stop + diff_with_stop) / 2
            method_avg_diffs[method] = avg_diff
    
    # 找出综合偏差最小的方法
    if method_avg_diffs:
        best_method = min(method_avg_diffs, key=method_avg_diffs.get)
        print(f"\n综合评估，最可能的lude.cc计算方法是: {best_method}")
        print(f"该方法的平均偏差: {method_avg_diffs[best_method]:.6f} ({method_avg_diffs[best_method]*100:.2f}%)")
        
        # 详细展示最佳方法的计算结果
        print("\n该方法的详细计算结果:")
        print(f"不止盈情况: {results_no_stop[best_method]:.6f} ({results_no_stop[best_method]*100:.2f}%)")
        print(f"止盈情况: {results_with_stop[best_method]:.6f} ({results_with_stop[best_method]*100:.2f}%)")
        
        # 与lude.cc结果的差异
        print("\n与lude.cc结果的差异:")
        print(f"不止盈情况差异: {abs(results_no_stop[best_method] - LUDE_CAGR_NO_STOP):.6f} ({abs(results_no_stop[best_method] - LUDE_CAGR_NO_STOP)*100:.2f}%)")
        print(f"止盈情况差异: {abs(results_with_stop[best_method] - LUDE_CAGR_WITH_STOP):.6f} ({abs(results_with_stop[best_method] - LUDE_CAGR_WITH_STOP)*100:.2f}%)")

if __name__ == "__main__":
    main()
