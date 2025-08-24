#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CAGR计算器 - 修正版
修复了ascending参数的理解问题
原始理解：ascending=True表示值越小越好
正确理解：ascending=True表示值越大越好（与平台一致）
"""

from lude.core.cagr_calculator import *

# 重写calculate_bonds_cagr函数，修正ascending参数的理解
def calculate_bonds_cagr_corrected(df, factors, start_date=None, end_date=None, 
                                  price_range=None, filter_conditions=None,
                                  rebalance_interval=1, threshold_num=None, 
                                  stop_profit=None, **kwargs):
    """
    计算可转债策略的复合年增长率（CAGR）- 修正版
    
    修正内容：
    1. 反转所有因子的ascending参数，使其与平台理解一致
    2. 保持其他逻辑不变
    
    Args:
        df: DataFrame，包含可转债数据
        factors: list，因子配置列表
        start_date: str，开始日期
        end_date: str，结束日期
        price_range: tuple，价格范围 (min_price, max_price)
        filter_conditions: list，过滤条件
        rebalance_interval: int，调仓间隔（天）
        threshold_num: int，阈值轮动数量
        stop_profit: float，止盈比例
        **kwargs: 其他参数
    
    Returns:
        float: CAGR值
    """
    
    # 反转所有因子的ascending参数
    corrected_factors = []
    for factor in factors:
        corrected_factor = factor.copy()
        # 反转ascending参数
        corrected_factor['ascending'] = not factor.get('ascending', False)
        corrected_factors.append(corrected_factor)
    
    # 调用原始函数，但使用修正后的因子配置
    return calculate_bonds_cagr(df, corrected_factors, start_date, end_date,
                               price_range, filter_conditions,
                               rebalance_interval, threshold_num,
                               stop_profit, **kwargs)


# 导出修正后的函数
__all__ = ['calculate_bonds_cagr_corrected']