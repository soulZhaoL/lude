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
from lude.utils.logger import optimization_logger as logger

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
    logger.info(f"数据中存在 {len(existing_factors)}/{len(all_factors)} 个因子")

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

    logger.info(f"生成了 {len(combinations)} 个因子组合")
    return existing_factors, combinations


def prescreen_factors(df, factors, top_n=30, args=None, enable_filter_opt=False):
    """预筛选最有潜力的单因子 - 简化版本，推荐使用multistage策略
    
    Args:
        df: 数据框
        factors: 因子列表
        top_n: 选择的顶部因子数量
        args: 参数
        enable_filter_opt: 是否启用过滤优化（当前不支持，建议使用multistage策略）
        
    Returns:
        top_factors: 筛选后的顶部因子
        combinations: 因子组合列表
    """
    logger.warning("prescreen策略已简化，推荐使用multistage策略以获得完整功能")
    
    if enable_filter_opt:
        logger.warning("prescreen策略不支持过滤优化，请使用multistage策略")
    
    # 简化实现：直接使用领域知识选择因子
    all_factors, factor_groups = domain_knowledge_factors()
    existing_factors = [f for f in all_factors if f in df.columns]
    
    # 选择前top_n个因子
    selected_factors = existing_factors[:min(top_n, len(existing_factors))]
    
    # 生成组合
    combinations = []
    num_factors = args.n_factors if args else 3
    for combo in itertools.combinations(range(len(selected_factors)), num_factors):
        combinations.append(tuple(combo))
    
    logger.info(f"预筛选策略：选择了 {len(selected_factors)} 个因子，生成 {len(combinations)} 个组合")
    return selected_factors, combinations


# NOTE: choose_strategy函数已被弃用，请使用lude.optimization.strategies.strategy_runner.run_strategy
# 保留此函数仅为向后兼容性，但建议直接使用统一的策略运行器

def choose_strategy(strategy, df, factors, num_factors, args, max_combinations=50000, enable_filter_opt=False):
    """
    [已弃用] 根据选择的策略生成因子组合
    
    注意：此函数已弃用，请使用 lude.optimization.strategies.strategy_runner.run_strategy
    
    Args:
        strategy: 策略名称
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        enable_filter_opt: 是否启用过滤优化
        
    Returns:
        factors: 因子列表
        combinations: 因子组合列表
    """
    logger.warning("choose_strategy函数已弃用，建议使用strategy_runner.run_strategy统一接口")
    
    if strategy == 'domain':
        logger.info("使用领域知识生成组合")
        return domain_knowledge_combinations(df, num_factors, max_combinations)
    elif strategy == 'prescreen':
        logger.info("使用预筛选策略")
        return prescreen_factors(df, factors, top_n=30, args=args, enable_filter_opt=enable_filter_opt)
    elif strategy == 'filter':
        logger.info("使用冗余因子过滤策略")
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

        logger.info(f"从 {len(filtered_factors)} 个过滤后的因子中生成了 {len(combinations)} 个组合")
        return filtered_factors, combinations  
    else:
        logger.warning(f"未知策略 '{strategy}'，回退到领域知识策略")
        return domain_knowledge_combinations(df, num_factors, max_combinations)
