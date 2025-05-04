#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
因子策略模块
包含不同的因子选择和组合策略
"""

import itertools
import os
import sys

import numpy as np

# 修改为绝对导入路径
from lude.core.cagr_calculator import calculate_bonds_cagr


def domain_knowledge_factors():
    """基于领域知识对因子进行分类
    
    Returns:
        all_factors: 所有因子列表
        factor_groups: 按领域知识分组的因子字典
    """
    # 基础因子 - 溢价与价值相关
    premium_value_factors = [
        'conv_prem',  # 转股溢价率
        'theory_conv_prem',  # 理论溢价率
        'mod_conv_prem',  # 修正溢价率
        'pure_value',  # 纯债价值
        'bond_prem',  # 纯债溢价率
        'dblow',  # 双低
        'conv_value',  # 转股价值
        'option_value',  # 期权价值
        'theory_value',  # 理论价值
        'theory_bias',  # 理论偏离度
    ]

    # 基础因子 - 价格相关
    price_factors = [
        'close',  # 收盘价
        'pre_close',  # 前收盘价
        'open',  # 开盘价
        'high',  # 最高价
        'low',  # 最低价
        'pct_chg',  # 涨跌幅
    ]

    # 基础因子 - 交易相关
    trading_factors = [
        'amount',  # 成交额(万)
        'vol',  # 成交量(手)
        'turnover',  # 换手率
        'cap_mv_rate',  # 转债市占比
    ]

    # 基础因子 - 规模相关
    size_factors = [
        'issue_size',  # 发行规模(亿)
        'remain_size',  # 剩余规模(亿)
        'remain_cap',  # 剩余市值(亿)
    ]

    # 基础因子 - 时间相关
    time_factors = [
        'list_days',  # 上市天数
        'left_years',  # 剩余年限
    ]

    # 基础因子 - 其他
    other_base_factors = [
        'ytm',  # 到期收益率
        'conv_price',  # 转股价格
        'redeem_price_rate',  # 强赎触发价比率
        'redeem_remain_days',  # 强赎剩余计数
    ]

    # 正股因子 - 价格相关
    stock_price_factors = [
        'close_stk',  # 正股收盘价
        'pct_chg_stk',  # 正股涨跌幅
    ]

    # 正股因子 - 交易相关
    stock_trading_factors = [
        'amount_stk',  # 正股成交额(万)
        'vol_stk',  # 正股成交量
    ]

    # 正股因子 - 规模相关
    stock_size_factors = [
        'total_mv',  # 正股总市值(亿)
        'circ_mv',  # 正股流通市值(亿)
    ]

    # 正股因子 - 估值相关
    stock_valuation_factors = [
        'pb',  # 市净率
        'pe_ttm',  # 市盈率TTM
        'ps_ttm',  # 市销率TTM
        'debt_to_assets',  # 资产负债率
        'dv_ratio',  # 股息率
    ]

    # 技术指标因子 - 短期
    tech_short_factors = [
        'bias_5',  # 5日乖离率
        'close_ma_5',  # 5日均价
        'vol_5',  # 5日成交量
        'amount_5',  # 5日成交额
        'turnover_5',  # 5日换手率
        'pct_chg_5',  # 5日涨跌幅
        'pct_chg_5_stk',  # 正股5日涨跌幅
        'alpha_pct_chg_5',  # 5日超额涨跌幅
    ]

    # 技术指标因子 - 中期
    tech_medium_factors = [
        'bias_10',  # 10日乖离率
        'close_ma_10',  # 10日均价
        'vol_10',  # 10日成交量
        'amount_10',  # 10日成交额
        'turnover_10',  # 10日换手率
        'pct_chg_10',  # 10日涨跌幅
        'pct_chg_10_stk',  # 正股10日涨跌幅
        'alpha_pct_chg_10',  # 10日超额涨跌幅
    ]

    # 技术指标因子 - 长期
    tech_long_factors = [
        'bias_20',  # 20日乖离率
        'close_ma_20',  # 20日均价
        'vol_20',  # 20日成交量
        'amount_20',  # 20日成交额
        'turnover_20',  # 20日换手率
        'pct_chg_20',  # 20日涨跌幅
        'pct_chg_20_stk',  # 正股20日涨跌幅
        'alpha_pct_chg_20',  # 20日超额涨跌幅
    ]

    # 波动率相关因子
    volatility_factors = [
        'volatility',  # 年化波动率
        'volatility_stk',  # 正股年化波动率
    ]

    # 将所有因子分组
    factor_groups = {
        'premium_value': premium_value_factors,
        'price': price_factors,
        'trading': trading_factors,
        'size': size_factors,
        'time': time_factors,
        'other_base': other_base_factors,
        'stock_price': stock_price_factors,
        'stock_trading': stock_trading_factors,
        'stock_size': stock_size_factors,
        'stock_valuation': stock_valuation_factors,
        'tech_short': tech_short_factors,
        'tech_medium': tech_medium_factors,
        'tech_long': tech_long_factors,
        'volatility': volatility_factors
    }

    # 合并所有因子
    all_factors = []
    for group in factor_groups.values():
        all_factors.extend(group)

    return all_factors, factor_groups


def domain_knowledge_combinations(df, num_factors, max_combinations=50000):
    """使用领域知识生成因子组合
    
    Args:
        df: 数据框
        num_factors: 因子数量
        max_combinations: 最大组合数量
        
    Returns:
        factors: 因子列表
        combinations: 因子组合列表
    """
    # 获取所有因子和分组
    all_factors, factor_groups = domain_knowledge_factors()

    # 检查数据框中存在的因子
    existing_factors = [f for f in all_factors if f in df.columns]
    print(f"数据中存在 {len(existing_factors)}/{len(all_factors)} 个因子")

    # 根据领域知识生成组合
    # 策略: 从不同的因子组中选择因子，确保多样性

    # 定义重要的因子组
    key_groups = ['premium_value', 'price', 'trading', 'stock_valuation', 'tech_short']

    # 确保每个组合至少包含一个溢价相关因子
    premium_factors = [f for f in factor_groups['premium_value'] if f in existing_factors]

    # 生成组合
    combinations = []

    # 1. 从每个重要组中选择一个因子
    if num_factors <= len(key_groups):
        # 如果因子数量小于等于重要组数量，从重要组中选择
        group_combinations = []
        for group_subset in itertools.combinations(key_groups, num_factors):
            group_factors = []
            for group in group_subset:
                group_factors_list = [f for f in factor_groups[group] if f in existing_factors]
                if group_factors_list:
                    group_factors.append(np.random.choice(group_factors_list))
            if len(group_factors) == num_factors:
                group_combinations.append(tuple(sorted(group_factors)))

        # 去重
        group_combinations = list(set(group_combinations))
        combinations.extend(group_combinations)
    else:
        # 如果因子数量大于重要组数量，从所有组中选择
        for _ in range(min(1000, max_combinations // 10)):
            combo = []
            # 确保至少有一个溢价相关因子
            if premium_factors:
                combo.append(np.random.choice(premium_factors))

            # 从其他组中随机选择
            remaining_factors = [f for f in existing_factors if f not in combo]
            while len(combo) < num_factors and remaining_factors:
                factor = np.random.choice(remaining_factors)
                combo.append(factor)
                remaining_factors.remove(factor)

            if len(combo) == num_factors:
                combinations.append(tuple(sorted(combo)))

    # 2. 随机生成其他组合以增加多样性
    remaining_slots = max_combinations - len(combinations)
    if remaining_slots > 0:
        for _ in range(remaining_slots):
            combo = np.random.choice(existing_factors, size=num_factors, replace=False)
            combinations.append(tuple(sorted(combo)))

    # 去重并限制组合数量
    combinations = list(set(combinations))
    if len(combinations) > max_combinations:
        np.random.shuffle(combinations)
        combinations = combinations[:max_combinations]

    print(f"生成了 {len(combinations)} 个因子组合")
    return existing_factors, combinations


def prescreen_factors(df, factors, top_n=30, args=None):
    """预筛选最有潜力的单因子
    
    Args:
        df: 数据框
        factors: 因子列表
        top_n: 选择的顶部因子数量
        args: 参数
        
    Returns:
        top_factors: 筛选后的顶部因子
        combinations: 因子组合列表
    """
    print(f"预筛选单因子性能...")

    # 计算每个单因子的性能
    factor_performance = {}
    for factor in factors:
        if factor not in df.columns:
            continue

        # 测试升序和降序
        for ascending in [True, False]:
            # 设置排序方向
            direction = "升序" if ascending else "降序"

            # 创建单因子配置
            rank_factors = [{
                'name': factor,
                'weight': 1,
                'ascending': ascending
            }]

            # 计算CAGR
            try:
                cagr = calculate_bonds_cagr(
                    df,
                    start_date=args.start_date if args else '20220729',
                    end_date=args.end_date if args else '20250328',
                    hold_num=args.hold_num if args else 5,
                    threshold_num=None,
                    min_price=args.price_min if args else 100,
                    max_price=args.price_max if args else 150,
                    rank_factors=rank_factors,
                )

                factor_key = f"{factor}_{direction}"
                factor_performance[factor_key] = {
                    'factor': factor,
                    'ascending': ascending,
                    'cagr': cagr
                }
                print(f"因子: {factor} ({direction}) - CAGR: {cagr:.6f}")
            except Exception as e:
                print(f"计算因子 {factor} ({direction}) 性能时出错: {e}")

    # 按CAGR排序
    sorted_performance = sorted(
        factor_performance.values(),
        key=lambda x: x['cagr'],
        reverse=True
    )

    # 选择顶部因子
    top_factors = sorted_performance[:top_n]

    # 提取因子名称
    top_factor_names = [item['factor'] for item in top_factors]

    # 生成所有可能的组合
    combinations = []
    for combo in itertools.combinations(range(len(top_factor_names)), args.n_factors if args else 3):
        combinations.append(tuple(combo))

    print(f"从 {len(top_factor_names)} 个顶部因子中生成了 {len(combinations)} 个组合")
    return top_factor_names, combinations


def choose_strategy(strategy, df, factors, num_factors, args, max_combinations=50000):
    """根据选择的策略生成因子组合
    
    Args:
        strategy: 策略名称
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        
    Returns:
        factors: 因子列表
        combinations: 因子组合列表
    """
    if strategy == 'domain':
        # 使用领域知识生成组合
        print("使用领域知识生成组合")
        return domain_knowledge_combinations(df, num_factors, max_combinations)
    elif strategy == 'prescreen':
        # 使用预筛选策略
        print("使用预筛选策略")
        return prescreen_factors(df, factors, top_n=30, args=args)
    elif strategy == 'filter':
        # 使用冗余因子过滤策略
        print("使用冗余因子过滤策略")
        from lude.utils.common_utils import filter_redundant_factors
        filtered_factors = filter_redundant_factors(factors)

        # 生成所有可能的组合
        combinations = []
        for combo in itertools.combinations(range(len(filtered_factors)), num_factors):
            combinations.append(tuple(combo))

        # 限制组合数量
        if len(combinations) > max_combinations:
            np.random.seed(args.seed)
            indices = np.random.choice(len(combinations), max_combinations, replace=False)
            combinations = [combinations[i] for i in indices]

        print(f"从 {len(filtered_factors)} 个过滤后的因子中生成了 {len(combinations)} 个组合")
        return filtered_factors, combinations
    else:
        # 默认使用领域知识
        print("使用领域知识生成组合")
        return domain_knowledge_combinations(df, num_factors, max_combinations)
