"""
绩效指标计算模块测试脚本

使用示例数据测试performance_metrics.py模块的功能。
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pprint import pprint

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.lude.utils.performance_metrics import calculate_performance_metrics
from src.lude.config.paths import DATA_DIR

def test_performance_metrics():
    """测试绩效指标计算功能"""
    # 加载数据文件
    cb_data_path = os.path.join(DATA_DIR, 'cb_data.pq')
    
    print(f"加载可转债数据: {cb_data_path}")
    if not os.path.exists(cb_data_path):
        print(f"错误：找不到可转债数据文件: {cb_data_path}")
        sys.exit(1)
        
    df = pd.read_parquet(cb_data_path)
    print(f"数据加载成功，共 {len(df)} 条记录")
    
    start_date = '20220729'
    end_date = '20250328'
    hold_num = 5
    min_price = 100
    max_price = 150

    factors = [
        {'name': 'conv_prem', 'weight': 4, 'ascending': False},
        {'name': 'debt_to_assets', 'weight': 3, 'ascending': True},
        {'name': 'pct_chg_5_stk', 'weight': 3, 'ascending': True},
        {'name': 'turnover_5', 'weight': 3, 'ascending': True}
    ]

    print("\n测试1: 使用默认参数(启用止盈)")
    # 计算启用止盈情况的综合指标
    results = calculate_performance_metrics(
        df, start_date, end_date, hold_num, min_price, max_price, factors
    )

    # 打印各项指标结果
    print("\n策略绩效指标:")
    print(f"年化收益率: {results['cagr']:.6f} ({results['cagr']*100:.2f}%)")
    print(f"最大回撤率: {results['max_drawdown']:.6f} ({results['max_drawdown']*100:.2f}%)")
    print(f"夏普比率: {results['sharpe_ratio']:.6f}")
    print(f"索提诺比率: {results['sortino_ratio']:.6f}")
    print(f"卡玛比率: {results['calmar_ratio']:.6f}")
    
    
    return results

if __name__ == '__main__':
    # 执行测试
    results = test_performance_metrics()
    
  
