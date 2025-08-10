#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化引擎模块
负责执行优化过程的核心逻辑
"""

import json
import os

import optuna

from lude.config.config_loader import get_optimization_config, get_filter_factors_config
from lude.config.paths import RESULTS_DIR, FACTOR_MAPPING_PATH
# 导入常量和工具函数
from lude.utils.common_utils import create_sampler
from lude.utils.common_utils import save_optimization_result
from lude.utils.dingtalk.dingtalk_notifier import send_optimization_result_to_dingtalk
from lude.utils.factor_saver import save_high_performance_factors
from lude.utils.logger import optimization_logger as logger


def load_factor_mapping():
    """加载因子中英文映射
    
    Returns:
        factor_mapping: 因子映射字典，键为英文名，值为中文名
    """
    try:
        with open(FACTOR_MAPPING_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载因子映射文件时出错: {e}")
        return {}


def run_optimization(df, args):
    """运行优化过程
    
    Args:
        df: 数据框
        args: 参数
        
    Returns:
        model_path: 保存的模型路径
    """
    logger.info(f"===== 开始优化 =====")
    logger.info(f"策略: {args.strategy}")
    logger.info(f"方法: {args.method}")
    logger.info(f"迭代次数: {args.n_trials}")
    logger.info(f"因子数量: {args.n_factors}")
    logger.info(f"回测日期: {args.start_date} 至 {args.end_date}")
    logger.info(f"价格范围: {args.price_min} - {args.price_max}")
    logger.info(f"持仓数量: {args.hold_num}")
    logger.info(f"并行任务数: {args.n_jobs}")
    logger.info(f"随机种子: {args.seed}")
    logger.info(f"过滤优化状态: {'启用' if args.enable_filter_opt else '禁用'}")

    # 添加自定义因子
    # df = add_custom_factors(df)

    # 获取所有可用因子 - 使用factor_mapping_filter.json定义的因子列表
    factor_mapping = load_factor_mapping()
    available_factors = list(factor_mapping.keys())

    # 只保留在数据中实际存在且在映射文件中定义的因子
    factors = [col for col in df.columns if col in available_factors]

    logger.info(f"因子映射文件中定义了 {len(available_factors)} 个因子")
    logger.info(f"数据中实际可用的因子有 {len(factors)} 个")
    
    # 检查是否启用过滤优化
    enable_filter_opt = getattr(args, 'enable_filter_opt', False)
    logger.info(f"过滤优化状态: {'启用' if enable_filter_opt else '禁用'}")

    # 🎯 优先获取配置文件中的max_combinations，如果为空则使用系统预置的
    try:
        # 尝试从配置文件获取max_combinations
        optimal_max_combinations = get_filter_factors_config('combination_rules.max_combinations')
        logger.info(f"从配置文件获取max_combinations: {optimal_max_combinations}")
    except (FileNotFoundError, KeyError) as e:
        # 配置文件不存在或配置项不存在时，使用系统预置的动态计算方式
        optimal_max_combinations = get_max_combinations_for_trials(args.n_trials)
        logger.warning(f"配置文件中未找到max_combinations，使用动态计算值: {optimal_max_combinations}")
    
    # 统一调用策略运行器
    from lude.optimization.strategies.strategy_runner import run_strategy
    
    factors, factor_combinations, study = run_strategy(
        args.strategy, df, factors, args.n_factors, args, 
        max_combinations=optimal_max_combinations, enable_filter_opt=enable_filter_opt
    )

    # 打印最佳结果
    if len(study.trials) > 0:
        logger.info(f"===== 优化结果 =====")
        logger.info(f"最佳CAGR: {study.best_value:.6f}")

        # 提取最佳因子组合
        best_rank_factors = None

        # 首先检查study对象本身是否直接保存了best_rank_factors属性（由多阶段优化器设置的备选方案）
        if hasattr(study, 'best_rank_factors'):
            best_rank_factors = study.best_rank_factors
            logger.info("从study对象的属性中获取最佳因子配置")
        # 然后尝试从best_trial的user_attrs中获取
        elif hasattr(study.best_trial, 'user_attrs') and 'rank_factors' in study.best_trial.user_attrs:
            best_rank_factors = study.best_trial.user_attrs['rank_factors']
            logger.info("从best_trial的user_attrs中获取最佳因子配置")

        if best_rank_factors:
            logger.info(f"最佳因子组合:")
            for i, factor in enumerate(best_rank_factors):
                logger.info(f"  {i + 1}. {factor['name']}")
                logger.info(f"     - 权重: {factor['weight']}")
                logger.info(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
        else:
            logger.warning("无法获取最佳因子组合详情")

            # 尝试从best_trial的参数重建rank_factors（最后的备选方案）
            try:
                if 'combination_idx' in study.best_params:
                    combination_idx = study.best_params['combination_idx']

                    # 从factor_combinations获取组合
                    if combination_idx < len(factor_combinations):
                        combination_indices = factor_combinations[combination_idx]
                        combination = [factors[i] for i in combination_indices] if isinstance(
                            combination_indices[0], int) else combination_indices
                    else:
                        logger.warning(f"警告: combination_idx={combination_idx}超出组合范围")
                        combination = None

                    # 如果成功获取到组合，重建rank_factors
                    if combination:
                        best_rank_factors = []
                        for i, factor in enumerate(combination):
                            weight_param = f'factor{i}_weight'
                            asc_param = f'factor{i}_ascending'

                            weight = study.best_params.get(weight_param, 1)
                            ascending = study.best_params.get(asc_param, True)

                            best_rank_factors.append({
                                'name': factor,
                                'weight': weight,
                                'ascending': ascending
                            })

                        logger.info("已从参数重建最佳因子组合:")
                        for i, factor in enumerate(best_rank_factors):
                            logger.info(f"  {i + 1}. {factor['name']}")
                            logger.info(f"     - 权重: {factor['weight']}")
                            logger.info(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
            except Exception as e:
                logger.error(f"尝试重建最佳因子组合时出错: {e}")

        # 获取排除因子信息
        best_filter_conditions = []
        if hasattr(study, 'best_filter_conditions'):
            best_filter_conditions = study.best_filter_conditions
        elif hasattr(study.best_trial, 'user_attrs') and 'filter_conditions' in study.best_trial.user_attrs:
            best_filter_conditions = study.best_trial.user_attrs['filter_conditions']

        # 保存最佳模型（包含排除因子信息）
        model_path = save_optimization_result(study, factors, factor_combinations, args, best_rank_factors, best_filter_conditions)

        # 获取配置的CAGR阈值
        cagr_threshold = get_optimization_config('notification.dingtalk.cagr_threshold')

        # 如果有最佳因子组合，初始化因子数据（factor_mapping已在前面加载）
        factor_data = []
        if best_rank_factors:
            # 准备因子组合详细数据
            factor_data = [{
                'name': factor['name'],
                'description': factor_mapping.get(factor['name']),
                'weight': factor['weight'],
                'ascending': factor['ascending']
            } for factor in best_rank_factors]

        # 年化收益率超过阈值时统一处理保存和推送
        if study.best_value >= cagr_threshold and best_rank_factors:
            try:
                # 准备元数据（不包含排除因子，因为排除因子已提升为独立参数）
                metadata = {
                    'strategy': args.strategy if hasattr(args, 'strategy') else 'default',
                    'start_date': args.start_date if hasattr(args, 'start_date') else None,
                    'end_date': args.end_date if hasattr(args, 'end_date') else None,
                    'hold_num': args.hold_num if hasattr(args, 'hold_num') else None,
                    'n_trials': args.n_trials if hasattr(args, 'n_trials') else None,
                    'seed': args.seed if hasattr(args, 'seed') else None,
                    'price_range': [args.min_price, args.max_price] if hasattr(args, 'min_price') and hasattr(args, 'max_price') else None,
                    'model_path': model_path
                }

                # 保存高绩效因子组合（排除因子作为独立参数传递）
                save_high_performance_factors(factor_data, study.best_value, best_filter_conditions, metadata)
                logger.info(f"已保存高绩效因子组合 (CAGR: {study.best_value:.6f}) 到文件")

                # 发送优化结果到钉钉
                dingtalk_enabled = get_optimization_config('notification.dingtalk.enabled')
                if dingtalk_enabled:
                    send_optimization_result_to_dingtalk(
                        cagr=study.best_value,
                        rank_factors=factor_data,
                        filter_conditions=best_filter_conditions,  # 添加排除因子信息
                        seed=args.seed,
                        strategy=args.strategy,
                        n_trials=args.n_trials,
                        start_date=args.start_date,
                        end_date=args.end_date,
                        hold_num=args.hold_num,
                        price_range=[args.min_price, args.max_price] if hasattr(args, 'min_price') else None,
                        model_path=model_path
                    )
                    logger.info("已发送结果到钉钉")
                else:
                    logger.info("钉钉推送已禁用")

            except Exception as e:
                logger.error(f"保存高绩效因子组合或发送钉钉通知时出错: {e}")
        else:
            logger.info(f"年化收益率未达到{cagr_threshold * 100}%，不推送")

        return model_path
    else:
        logger.warning("没有完成任何试验，无法获取结果")
        return None

def get_max_combinations_for_trials(n_trials: int) -> int:
    """根据训练次数获取对应的最大组合数
    
    Args:
        n_trials: 训练次数
        
    Returns:
        int: 对应的max_combinations值
    """
    # 简单直接的映射关系
    if n_trials <= 100:
        return 1000
    elif n_trials <= 500:
        return 5000
    elif n_trials <= 1000:
        return 10000
    elif n_trials <= 3000:
        return 30000
    elif n_trials <= 5000:
        return 50000
    else:
        return 100000