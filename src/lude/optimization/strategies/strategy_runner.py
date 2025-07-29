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
        return _run_domain_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt)


def _run_multistage_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行多阶段策略"""
    from lude.optimization.strategies.multistage import multistage_optimization
    
    # 直接调用multistage优化，它已经返回正确的格式
    return multistage_optimization(
        df, factors, num_factors, args, max_combinations, enable_filter_opt
    )


def _run_domain_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行领域知识策略"""
    from lude.optimization.strategies.factor_selection import domain_knowledge_combinations
    
    # 生成因子组合
    selected_factors, factor_combinations = domain_knowledge_combinations(df, num_factors, max_combinations)
    
    # 创建并运行优化研究
    study = _create_and_run_study(
        strategy_name='domain',
        df=df,
        factors=selected_factors,
        factor_combinations=factor_combinations,
        args=args,
        enable_filter_opt=enable_filter_opt
    )
    
    return selected_factors, factor_combinations, study


def _run_prescreen_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行预筛选策略"""
    from lude.optimization.strategies.factor_selection import prescreen_factors
    
    # 生成因子组合
    selected_factors, factor_combinations = prescreen_factors(
        df, factors, top_n=30, args=args, enable_filter_opt=enable_filter_opt
    )
    
    # 创建并运行优化研究
    study = _create_and_run_study(
        strategy_name='prescreen',
        df=df,
        factors=selected_factors,
        factor_combinations=factor_combinations,
        args=args,
        enable_filter_opt=enable_filter_opt
    )
    
    return selected_factors, factor_combinations, study


def _run_filter_strategy(df, factors, num_factors, args, max_combinations, enable_filter_opt):
    """运行过滤策略"""
    from lude.utils.common_utils import filter_redundant_factors
    import itertools
    import numpy as np
    
    # 过滤冗余因子
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
    
    # 创建并运行优化研究
    study = _create_and_run_study(
        strategy_name='filter',
        df=df,
        factors=filtered_factors,
        factor_combinations=combinations,
        args=args,
        enable_filter_opt=enable_filter_opt
    )
    
    return filtered_factors, combinations, study


def _create_and_run_study(strategy_name, df, factors, factor_combinations, args, enable_filter_opt):
    """
    为非multistage策略创建并运行优化研究
    
    Args:
        strategy_name: 策略名称
        df: 数据框
        factors: 因子列表
        factor_combinations: 因子组合列表
        args: 参数
        enable_filter_opt: 是否启用过滤优化
        
    Returns:
        study: 优化研究对象
    """
    # 创建研究名称和存储
    study_name = f"{strategy_name}_{args.method}_{args.n_factors}factors_{args.seed}"
    db_path = os.path.join(RESULTS_DIR, f"{study_name}.db")
    storage_name = f"sqlite:///{db_path}"
    
    try:
        # 尝试加载已有的研究
        study = optuna.load_study(study_name=study_name, storage=storage_name)
        logger.info(f"加载已有的研究，已完成 {len(study.trials)} 次试验")
    except:
        # 创建新的研究
        study = optuna.create_study(
            study_name=study_name,
            storage=storage_name,
            direction="maximize",
            sampler=create_sampler(args.method, args.seed),
            load_if_exists=True
        )
        logger.info("创建新的研究")
    
    # 创建目标函数
    objective_func = _create_objective_function(df, factors, factor_combinations, args, enable_filter_opt)
    
    # 执行优化
    try:
        study.optimize(
            objective_func,
            n_trials=args.n_trials,
            n_jobs=args.n_jobs,
            gc_after_trial=True
        )
    except KeyboardInterrupt:
        logger.warning("用户中断了优化")
    except Exception as e:
        logger.error(f"优化过程出错: {e}")
    
    return study


def _create_objective_function(df, factors, factor_combinations, args, enable_filter_opt):
    """
    为非multistage策略创建目标函数
    
    Args:
        df: 数据框
        factors: 因子列表
        factor_combinations: 因子组合列表
        args: 参数
        enable_filter_opt: 是否启用过滤优化
        
    Returns:
        objective: 目标函数
    """
    from lude.core.cagr_calculator import calculate_bonds_cagr
    
    def objective(trial):
        # 选择因子组合
        combination_idx = trial.suggest_int("combination_idx", 0, len(factor_combinations) - 1)
        combination_indices = factor_combinations[combination_idx]
        
        # 将索引转换为实际因子名称
        if isinstance(combination_indices[0], int):
            combination = [factors[i] for i in combination_indices]
        else:
            combination = combination_indices
        
        # 为每个因子分配权重和排序方向
        rank_factors = []
        for i, factor in enumerate(combination):
            weight = trial.suggest_int(f"factor{i}_weight", 1, 5)
            ascending = trial.suggest_categorical(f"factor{i}_ascending", [True, False])
            
            rank_factors.append({
                'name': factor,
                'weight': weight,
                'ascending': ascending
            })
        
        # 生成过滤条件（如果启用）
        filter_conditions = None
        if enable_filter_opt:
            try:
                from lude.utils.filter_generator import create_filter_conditions_for_trial
                # 获取数据中可用的因子列表
                available_factors = [col for col in df.columns if col not in ['date', 'bond_id', 'bond_nm', 'stock_id']]
                filter_conditions = create_filter_conditions_for_trial(trial, available_factors)
                
                # 记录生成的过滤条件
                if filter_conditions:
                    trial.set_user_attr("filter_conditions", filter_conditions)
                    logger.debug(f"Trial {trial.number}: 生成了 {len(filter_conditions)} 个过滤条件")
                else:
                    logger.debug(f"Trial {trial.number}: 未生成过滤条件")
                    
            except Exception as e:
                logger.error(f"生成过滤条件时出错: {e}")
                filter_conditions = None
        
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
                filter_conditions=filter_conditions,
            )
            
            # 保存rank_factors到trial
            trial.set_user_attr("rank_factors", rank_factors)
            
            return cagr
        except Exception as e:
            logger.error(f"计算CAGR时出错: {e}")
            raise optuna.exceptions.TrialPruned()
    
    return objective