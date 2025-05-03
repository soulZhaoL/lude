#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用工具函数模块
包含数据加载、采样器创建等基础功能
"""

import os
import pandas as pd
import optuna
import numpy as np
from datetime import datetime
import joblib

# 创建结果目录
RESULTS_DIR = "optimization_results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def load_data():
    """加载数据"""
    print("正在加载数据...")
    df = pd.read_parquet('cb_data.pq')
    return df


def create_sampler(method, seed=None):
    """创建采样器
    
    Args:
        method: 优化方法 (tpe, random, cmaes)
        seed: 随机种子
        
    Returns:
        optuna采样器
    """
    if method == 'random':
        return optuna.samplers.RandomSampler(seed=seed)
    elif method == 'cmaes':
        return optuna.samplers.CmaEsSampler(seed=seed)
    else:  # 默认使用TPE
        return optuna.samplers.TPESampler(seed=seed)


def save_optimization_result(study, factors, combinations, args, best_rank_factors=None):
    """保存优化结果
    
    Args:
        study: optuna study对象
        factors: 因子列表
        combinations: 因子组合列表
        args: 参数
        best_rank_factors: 最佳因子配置
    
    Returns:
        model_path: 保存的模型路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = f"{RESULTS_DIR}/best_model_{args.strategy}_{args.method}_{args.n_factors}factors_{timestamp}.pkl"

    # 如果没有提供best_rank_factors，尝试从study中提取
    if best_rank_factors is None and hasattr(study.best_trial,
                                             'user_attrs') and 'rank_factors' in study.best_trial.user_attrs:
        best_rank_factors = study.best_trial.user_attrs['rank_factors']

    model_data = {
        "study_name": study.study_name,
        "best_value": study.best_value,
        "best_rank_factors": best_rank_factors,
        "best_params": study.best_params,
        "factors": factors,
        "combinations": combinations,
        "date_range": (args.start_date, args.end_date),
        "price_range": (args.price_min, args.price_max),
        "hold_num": args.hold_num,
        "timestamp": timestamp
    }

    # 保存模型
    try:
        joblib.dump(model_data, model_path)
        print(f"\n最佳模型已保存至: {model_path}")
    except Exception as e:
        print(f"保存模型时出错: {e}")

    return model_path


def filter_redundant_factors(factors, threshold=0.8):
    """根据业务知识过滤掉冗余因子
    
    Args:
        factors: 因子列表
        threshold: 相似度阈值，高于此值的因子将被视为冗余
    
    Returns:
        filtered_factors: 过滤后的因子列表
    """
    # 定义冗余因子组
    redundant_groups = [
        # 溢价率相关
        ['conv_prem', 'theory_conv_prem', 'mod_conv_prem'],
        # 规模相关
        ['issue_size', 'remain_size', 'remain_cap'],
        # 价格相关
        ['close', 'pre_close', 'open', 'high', 'low'],
        # 成交相关
        ['amount', 'vol', 'turnover'],
        # 转股相关
        ['conv_price', 'conv_value'],
        # 理论价值相关
        ['theory_value', 'theory_bias', 'pure_value'],
        # 正股价格相关
        ['close_stk', 'pre_close_stk', 'open_stk', 'high_stk', 'low_stk'],
        # 正股成交相关
        ['amount_stk', 'vol_stk', 'turnover_stk'],
        # 正股市值相关
        ['total_mv', 'circ_mv'],
        # 正股估值相关
        ['pe_ttm', 'pb', 'ps_ttm'],
        # 技术指标相关
        ['bias_5', 'bias_10', 'bias_20'],
        ['close_ma_5', 'close_ma_10', 'close_ma_20'],
        ['vol_5', 'vol_10', 'vol_20'],
        ['amount_5', 'amount_10', 'amount_20'],
        ['turnover_5', 'turnover_10', 'turnover_20'],
        ['pct_chg_5', 'pct_chg_10', 'pct_chg_20'],
        ['pct_chg_5_stk', 'pct_chg_10_stk', 'pct_chg_20_stk'],
    ]

    # 创建一个集合来存储要保留的因子
    filtered_factors = set(factors)

    # 对每个冗余组进行处理
    for group in redundant_groups:
        # 找出该组中存在于原始因子列表中的因子
        existing_factors = [f for f in group if f in factors]

        # 如果该组中有多个因子存在于原始列表中，随机保留一个，移除其他的
        if len(existing_factors) > 1:
            # 随机选择一个因子保留
            np.random.shuffle(existing_factors)
            keep_factor = existing_factors[0]

            # 移除其他因子
            for factor in existing_factors[1:]:
                if factor in filtered_factors:
                    filtered_factors.remove(factor)
                    print(f"移除冗余因子: {factor} (与 {keep_factor} 冗余)")

    return list(filtered_factors)
