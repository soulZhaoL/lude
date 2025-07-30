#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一的策略运行器模块
提供统一的策略接口，让所有策略都返回相同的数据结构
"""

import os
import optuna
from lude.config.paths import RESULTS_DIR
from lude.utils.common_utils import create_sampler
from lude.utils.logger import optimization_logger as logger


def run_strategy(strategy_name, df, factors, num_factors, args, max_combinations=50000, enable_filter_opt=False):
    """
    统一的策略运行接口
    
    Args:
        strategy_name: 策略名称
        df: 数据框
        factors: 可用因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        enable_filter_opt: 是否启用过滤优化
        
    Returns:
        factors: 因子列表
        factor_combinations: 因子组合列表
        study: 优化研究对象
    """
    logger.info(f"运行策略: {strategy_name}")
    
    if strategy_name == 'multistage':
        return _run_multistage_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)
    elif strategy_name == 'domain':
        return _run_domain_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)
    elif strategy_name == 'prescreen':
        return _run_prescreen_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)
    elif strategy_name == 'filter':
        return _run_filter_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)
    else:
        logger.warning(f"未知策略 '{strategy_name}'，回退到domain策略")
        return _run_multistage_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)


def _run_multistage_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行多阶段策略"""
    from lude.optimization.strategies.multistage import multistage_optimization
    
    # 直接调用multistage优化，它已经返回正确的格式
    return multistage_optimization(
        df, factors, num_factors, args, max_combinations, enable_filter_opt
    )


def _run_domain_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行领域知识策略"""
    logger.warning("领域知识策略已弃用，请使用multistage策略")
    pass


def _run_prescreen_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行预筛选策略"""
    logger.warning("预筛选策略已弃用，请使用multistage策略")
    pass


def _run_filter_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行过滤策略"""
    logger.warning("过滤策略已弃用，请使用multistage策略")
    pass
