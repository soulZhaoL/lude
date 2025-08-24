#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多阶段优化策略模块
实现多阶段优化的核心逻辑

优化内容 (2024-07-30):
1. 重构阶段职责分离：
   - 预处理阶段：确定过滤条件（一次性，不在trial中重复生成）
   - 第一阶段：专注因子组合探索
   - 第二阶段：专注权重和排序方向优化

2. 简化目标函数：
   - 移除复杂的闭包设计
   - 使用预先确定的过滤条件，避免每个trial重新生成
   - 提高执行效率和代码可读性

3. 配置驱动优化：
   - 过滤因子的选择完全由配置文件filter_factors_optimized_config.yaml驱动
   - max_factors参数严格按照配置文件中的combination_rules.max_factors执行
   - 移除trial中不必要的因子选择逻辑
"""

import time
import optuna

from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.utils.logger import optimization_logger as logger
from lude.utils.memory_monitor import check_memory_warning, log_memory_stats
from .semantic_objective_v2 import (
    create_fixed_semantic_objective_function,
    create_fixed_refined_objective_function
)
from .config import StrategyConfig



def create_optimized_objective_function(df, combinations, args, all_filter_conditions=None, max_filter_factors=6):
    """创建优化的目标函数，同时优化打分因子和排除因子

    Args:
        df: 数据框
        combinations: 打分因子组合列表
        args: 参数
        all_filter_conditions: 所有可能的排除因子条件列表
        max_filter_factors: 最大排除因子数量（避免重复加载配置）

    Returns:
        objective: 目标函数
    """

    def objective(trial):
        # ========== 选择打分因子组合 ==========
        combination_idx = trial.suggest_int("combination_idx", 0, len(combinations) - 1)
        combination = combinations[combination_idx]

        # 为每个打分因子分配权重和排序方向
        rank_factors = []
        for i, factor in enumerate(combination):
            weight = trial.suggest_int(f"factor{i}_weight", 1, 5)
            ascending = trial.suggest_categorical(f"factor{i}_ascending", [True, False])

            rank_factors.append({"name": factor, "weight": weight, "ascending": ascending})

        # ========== 选择排除因子组合 ==========
        selected_filter_conditions = []
        if all_filter_conditions and len(all_filter_conditions) > 0:
            # 🎯 使用配置文件中的max_factors设置，在1-max_factors之间选择
            # 避免大量空排除因子试验，确保充分利用排除因子优化能力

            # 🎯 修复方案：使用固定的max_filter_factors数量，避免多层suggest
            num_filter_conditions = min(max_filter_factors, len(all_filter_conditions))

            # 选择具体的排除因子条件（保持原有suggest逻辑）
            for i in range(num_filter_conditions):
                condition_idx = trial.suggest_int(f"filter_condition_{i}_idx", 0, len(all_filter_conditions) - 1)
                selected_filter_conditions.append(all_filter_conditions[condition_idx])

            # 🎯 新增：验证排除因子条件的有效性，使用剪枝机制处理无效组合
            # is_valid, error_msg = _validate_filter_conditions(selected_filter_conditions)
            # if not is_valid:
            #     logger.warning(f"检测到无效的排除因子组合: {error_msg}")
            #     raise optuna.exceptions.TrialPruned()

        # 计算CAGR
        try:
            cagr = calculate_bonds_cagr(
                df,
                start_date=args.start_date if args else "20220729",
                end_date=args.end_date if args else "20250328",
                hold_num=args.hold_num if args else 5,
                threshold_num=None,
                min_price=args.price_min if args else 100,
                max_price=args.price_max if args else 150,
                rank_factors=rank_factors,
                filter_conditions=selected_filter_conditions,  # 使用动态选择的排除因子条件
                check_overfitting=True, verbose_overfitting=False
            )

            # 保存到trial
            trial.set_user_attr("rank_factors", rank_factors)
            trial.set_user_attr("filter_conditions", selected_filter_conditions)

            return cagr
        except ValueError as e:
            # 处理参数组合无效的情况（过拟合、条件过严等）
            if "过拟合" in str(e) or "无符合条件" in str(e):
                logger.debug(f"跳过无效参数组合: {e}, 当前打分因子: {rank_factors}, 当前排除因子: {selected_filter_conditions}")
                logger.debug(f"当前打分因子: {rank_factors}")
                logger.debug(f"当前排除因子: {selected_filter_conditions}")
                raise optuna.exceptions.TrialPruned()
            else:
                # 其他ValueError重新抛出
                raise
        except Exception as e:
            # 处理其他未预期的错误
            import traceback
            logger.error(f"计算CAGR时出现未预期错误: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.error(f"当前打分因子: {rank_factors}")
            logger.error(f"当前排除因子: {selected_filter_conditions}")
            raise optuna.exceptions.TrialPruned()

    return objective



def _create_study(study_name, args, sampler_type="random", n_trials=None):
    """创建optuna研究 - 使用增强型Redis存储
    
    🚨 严格原则：完全使用增强型存储，不允许降级处理
    增强型存储内部自带故障转移机制，无需额外fallback

    Args:
        study_name: 研究名称
        args: 参数
        sampler_type: 采样器类型 ("random" 或 "tpe")

    Returns:
        study: optuna研究对象
    """
    from lude.storage.enhanced_redis_storage import create_enhanced_study, load_enhanced_study
    
    # 配置采样器
    if sampler_type == "random":
        sampler = optuna.samplers.RandomSampler(seed=args.seed)
    else:
        # 🚨 内存优化：TPESampler配置
        sampler = optuna.samplers.TPESampler(
            seed=args.seed,
            n_startup_trials=max(100, int((n_trials or args.n_trials) * 0.15)),  # 至少100个或15%的启动试验
            n_ei_candidates=50,       # 增加候选点数量提升搜索质量
            multivariate=True,        # 启用多变量采样学习参数间相关性
            group=True,              # 启用参数分组优化
            warn_independent_sampling=False,  # 关闭独立采样警告
        )

    # 尝试加载已有的研究
    try:
        study = load_enhanced_study(study_name)
        logger.info(f"✅ 加载已有的研究 {study_name}，已完成 {len(study.trials)} 次试验")
    except:
        # 创建新的研究 - 使用增强型存储
        study = create_enhanced_study(
            study_name=study_name,
            direction="maximize",
            sampler=sampler
        )
        logger.info(f"✅ 创建新的研究 {study_name} (使用增强型Redis存储)")

    return study


def _run_first_stage_optimization(df, factors, num_factors, args, max_combinations):
    """运行第一阶段优化（语义化策略探索）

    Args:
        df: 数据框
        factors: 因子列表（保持兼容性，实际不使用预定义组合）
        num_factors: 因子数量（保持兼容性）
        args: 参数
        max_combinations: 最大组合数量（保持兼容性）

    Returns:
        first_stage_study: 第一阶段研究
        first_stage_strategies: 第一阶段策略配置（替代传统因子组合）
    """
    logger.info("\n===== 第一阶段：语义化策略探索 =====")

    # 初始化语义化策略配置
    strategy_config = StrategyConfig()
    
    # 创建第一阶段研究
    timestamp = int(time.time())  
    args._optimization_timestamp = timestamp  
    study_name = f"first_stage_semantic_{args.strategy}_{args.method}_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{args.seed}_{timestamp}"
    first_stage_study = _create_study(study_name, args, "tpe", n_trials=args.n_trials)

    # 创建语义化目标函数
    objective_func = create_fixed_semantic_objective_function(df, args, config=strategy_config)

    # 执行第一阶段优化（70%探索）
    n_trials_first_stage = int(args.n_trials * 0.7)
    adjusted_n_jobs = max(1, min(args.n_jobs // 2, 10))

    try:
        logger.info(f"第一阶段优化开始，共 {n_trials_first_stage} 个试验，使用 {adjusted_n_jobs} 个进程")
        # 🚨 内存优化：直接运行，仅在必要时清理（保持优化质量）
        first_stage_study.optimize(
            objective_func, n_trials=n_trials_first_stage, n_jobs=adjusted_n_jobs, gc_after_trial=True
        )
        
        # 运行完成后检查内存并清理（不打断优化过程）
        memory_status = check_memory_warning(warning_threshold=80.0, critical_threshold=90.0)
        if memory_status in ['warning', 'critical']:
            logger.info("优化完成后清理内存...")
            import gc
            gc.collect()
            logger.info(f"第一阶段优化完成，共 {len(first_stage_study.trials)} 个试验")
            
    except KeyboardInterrupt:
        logger.warning("用户中断了第一阶段优化")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"第一阶段优化出错: {e}")
        
        # 🚨 严格处理Redis连接错误 - 不允许fallback
        if "Connection reset by peer" in error_msg or "redis" in error_msg.lower() or "socket" in error_msg.lower():
            logger.error("检测到Redis连接问题，这是需要修复的根本问题")
            logger.error("可能的解决方案:")
            logger.error("1. 检查Redis服务状态: redis-cli ping")
            logger.error("2. 检查Redis配置: 超时设置、连接数限制")
            logger.error("3. 检查网络连接: netstat -an | grep 6379")
            logger.error("4. 检查系统资源: Redis内存使用、文件描述符限制")
            logger.error("5. 查看Redis日志: tail -f /var/log/redis/redis-server.log")
            
            # 重新抛出原始异常，不进行任何降级处理
            raise

    # 返回策略信息（替代传统因子组合）
    first_stage_strategies = list(strategy_config.investment_strategies.keys())
    logger.info(f"第一阶段探索完成，涉及策略: {first_stage_strategies}")
    
    return first_stage_study, first_stage_strategies


def _get_first_stage_results(first_stage_study, first_stage_strategies, _num_factors):
    """获取第一阶段结果（语义化策略版本）

    Args:
        first_stage_study: 第一阶段研究
        first_stage_strategies: 第一阶段策略列表
        _num_factors: 因子数量（保持兼容性）

    Returns:
        best_params: 最佳参数
        best_value: 最佳值
        best_strategies: 最佳策略组合
        top_strategies_with_params: TOP 10策略及其参数列表
    """
    # 检查第一阶段是否有结果
    if len(first_stage_study.trials) == 0:
        logger.error("第一阶段没有完成任何试验，无法继续")
        return None, None, None, []

    # 获取第一阶段最佳结果
    best_params = first_stage_study.best_params
    best_value = first_stage_study.best_value

    logger.info(f"\n第一阶段最佳CAGR: {best_value:.6f}")

    # 获取TOP 10策略及其参数
    top_strategies_with_params = []
    if len(first_stage_study.trials) > 0:
        # 按CAGR值排序获取TOP 10
        valid_trials = [t for t in first_stage_study.trials if t.value is not None]
        sorted_trials = sorted(valid_trials, key=lambda t: t.value, reverse=True)
        top_trials = sorted_trials[:min(10, len(sorted_trials))]
        
        logger.info(f"\n第一阶段TOP {len(top_trials)} 策略:")
        for idx, trial in enumerate(top_trials):
            primary_strategy = trial.params.get("primary_strategy", "unknown")
            secondary_strategy = trial.params.get("secondary_strategy", None)
            use_mixed = trial.params.get("use_mixed_strategy", False)
            
            # 收集策略及其参数信息
            strategy_info = {
                'primary_strategy': primary_strategy,
                'secondary_strategy': secondary_strategy,
                'use_mixed_strategy': use_mixed,
                'params': trial.params,
                'value': trial.value,
                'user_attrs': trial.user_attrs
            }
            top_strategies_with_params.append(strategy_info)
            
            # 打印基本信息
            strategy_desc = f"{primary_strategy}"
            if use_mixed and secondary_strategy:
                strategy_desc += f" + {secondary_strategy}"
            logger.info(f"  {idx + 1}. CAGR: {trial.value:.6f}, 策略: {strategy_desc}")
            
            # 打印因子权重信息（从user_attrs中获取）
            if 'rank_factors' in trial.user_attrs:
                rank_factors = trial.user_attrs['rank_factors']
                logger.info(f"     因子配置:")
                for factor_info in rank_factors:
                    factor_name = factor_info['name']
                    weight = factor_info['weight']
                    ascending = factor_info['ascending']
                    direction = "升序" if ascending else "降序"
                    logger.info(f"       - {factor_name}: 权重={weight}, 方向={direction}")

    # 提取最佳策略组合
    if "primary_strategy" in best_params:
        best_primary = best_params["primary_strategy"]
        best_secondary = best_params.get("secondary_strategy", None)
        best_mixed = best_params.get("use_mixed_strategy", False)
        
        best_strategies = {
            'primary': best_primary,
            'secondary': best_secondary,
            'mixed': best_mixed
        }

        logger.info(f"第一阶段最佳策略组合 (CAGR: {best_value:.6f}):")
        logger.info(f"  主策略: {best_primary}")
        if best_mixed and best_secondary:
            logger.info(f"  次策略: {best_secondary}")
        
        # 显示因子详情
        if first_stage_study.best_trial and 'rank_factors' in first_stage_study.best_trial.user_attrs:
            rank_factors = first_stage_study.best_trial.user_attrs['rank_factors']
            logger.info(f"  因子详情:")
            for i, factor_info in enumerate(rank_factors):
                factor_name = factor_info['name']
                weight = factor_info['weight']
                ascending = factor_info['ascending']
                direction = "升序" if ascending else "降序"
                logger.info(f"    {i + 1}. {factor_name}: 权重={weight}, 方向={direction}")

        return best_params, best_value, best_strategies, top_strategies_with_params
    else:
        logger.warning("无法获取第一阶段最佳策略组合")
        return None, None, None, top_strategies_with_params



def _run_second_stage_optimization(
        df,
        factors,
        num_factors,
        args,
        first_stage_study,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_strategies,
        top_strategies_with_params,
        max_combinations,
):
    """运行第二阶段优化（基于最佳策略的精调）

    Args:
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        first_stage_best_params: 第一阶段最佳参数
        first_stage_best_value: 第一阶段最佳值
        first_stage_strategies: 第一阶段策略列表
        top_strategies_with_params: TOP 10策略及其参数
        max_combinations: 最大组合数量

    Returns:
        second_stage_study: 第二阶段研究
        best_strategies_for_refinement: 用于精调的最佳策略信息
    """
    logger.info("\n===== 第二阶段：语义化策略精调 =====")

    # 初始化语义化策略配置
    strategy_config = StrategyConfig()
    
    # 提取最佳策略信息用于精调
    from .semantic_objective_v2 import analyze_best_strategies
    best_strategies_for_refinement = analyze_best_strategies(first_stage_study, top_n=10)

    # 创建第二阶段研究  
    timestamp = getattr(args, '_optimization_timestamp', int(time.time()))
    study_name = f"second_stage_semantic_{args.strategy}_{args.method}_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{args.seed}_{timestamp}"
    second_stage_study = _create_study(study_name, args, args.method, n_trials=args.n_trials)

    # 创建精调目标函数（使用语义化策略的精调版本）
    objective_func = create_fixed_refined_objective_function(
        df, 
        best_strategies_for_refinement, 
        args, 
        config=strategy_config
    )

    # 执行第二阶段优化（30%精调）
    n_trials_second_stage = int(args.n_trials * 0.3)
    adjusted_n_jobs = max(1, min(args.n_jobs // 2, 10))
    
    try:
        logger.info(f"第二阶段优化开始，共 {n_trials_second_stage} 个试验，使用 {adjusted_n_jobs} 个进程")
        # 🚨 内存优化：直接运行第二阶段，保持优化质量
        second_stage_study.optimize(
            objective_func, n_trials=n_trials_second_stage, n_jobs=adjusted_n_jobs, gc_after_trial=True
        )
        
        # 第二阶段完成后清理内存
        memory_status = check_memory_warning(warning_threshold=80.0, critical_threshold=90.0)
        if memory_status in ['warning', 'critical']:
            logger.info("第二阶段优化完成后清理内存...")
            import gc
            gc.collect()
            logger.info(f"第二阶段优化完成，共 {len(second_stage_study.trials)} 个试验")
                
    except KeyboardInterrupt:
        logger.warning("用户中断了第二阶段优化")
    except Exception as e:
        logger.error(f"第二阶段优化出错: {e}")

    return second_stage_study, best_strategies_for_refinement



def multistage_optimization(df, factors, num_factors, args, max_combinations=50000, enable_filter_opt=False):
    """优化后的多阶段优化策略

    预处理阶段：确定过滤条件
    第一阶段：专注因子组合探索
    第二阶段：专注权重和排序方向优化

    Args:
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        enable_filter_opt: 是否启用过滤因子组合优化

    Returns:
        factors: 因子列表
        combinations: 所有探索过的因子组合
        final_study: 最终的优化研究
    """
    logger.info(f"执行优化后的多阶段优化策略...")
    
    # 🚨 内存监控：记录优化开始时的内存状态
    logger.info("开始多阶段优化，记录初始内存状态:")
    log_memory_stats()

    # 暂不使用排除因子
    logger.info("\n===== 暂不使用排除因子条件 =====")

    # 第一阶段：语义化策略探索
    first_stage_study, first_stage_strategies = _run_first_stage_optimization(
        df, factors, num_factors, args, max_combinations
    )

    # 获取第一阶段结果，包括TOP 10策略
    first_stage_best_params, first_stage_best_value, _, top_strategies_with_params = _get_first_stage_results(
        first_stage_study, first_stage_strategies, num_factors
    )

    if first_stage_best_params is None:
        logger.warning("第一阶段最佳参数为空，跳过第二阶段优化")
        return factors, first_stage_strategies, first_stage_study

    # 第二阶段：语义化策略精调
    second_stage_study, best_strategies_for_refinement = _run_second_stage_optimization(
        df,
        factors,
        num_factors,
        args,
        first_stage_study,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_strategies,
        top_strategies_with_params,
        max_combinations,
    )

    # 创建最终研究并合并结果（语义化策略版本）
    final_study, all_strategies = _create_final_study_and_merge_results_semantic(
        args,
        first_stage_study,
        first_stage_strategies,
        second_stage_study,
        best_strategies_for_refinement,
        first_stage_best_value,
        num_factors,
        None  # all_filter_conditions参数
    )

    return factors, all_strategies, final_study


def _create_final_study_and_merge_results_semantic(
        args,
        first_stage_study,
        first_stage_strategies,
        second_stage_study,
        best_strategies_for_refinement,
        first_stage_best_value,
        num_factors,
        all_filter_conditions=None,
):
    """创建最终研究并合并结果（语义化策略版本）

    Args:
        args: 参数
        first_stage_study: 第一阶段研究
        first_stage_strategies: 第一阶段策略
        second_stage_study: 第二阶段研究
        best_strategies_for_refinement: 精调策略信息
        first_stage_best_value: 第一阶段最佳值
        num_factors: 因子数量
        all_filter_conditions: 所有排除因子条件列表

    Returns:
        final_study: 最终研究
        all_strategies: 所有策略信息
    """
    # 创建最终研究
    filter_suffix = "filter" if getattr(args, 'enable_filter_opt', False) else "nofilter"
    timestamp = getattr(args, '_optimization_timestamp', int(time.time()))
    study_name = f"final_semantic_{args.strategy}_{args.method}_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{filter_suffix}_{args.seed}_{timestamp}"
    final_study = _create_study(study_name, args, args.method)

    # 比较两个阶段的结果
    second_stage_best_value = second_stage_study.best_value if len(second_stage_study.trials) > 0 else -float("inf")
    value_diff = second_stage_best_value - first_stage_best_value

    # 决定使用哪个阶段的结果
    if abs(value_diff) < 0.0001:
        logger.info(f"第二阶段结果 ({second_stage_best_value:.6f}) 与第一阶段 ({first_stage_best_value:.6f}) 基本相同")
        logger.info("使用第二阶段的最佳结果")
        use_second_stage = True
    elif value_diff < 0:
        logger.info(f"第一阶段结果 ({first_stage_best_value:.6f}) 优于第二阶段 ({second_stage_best_value:.6f})")
        logger.info("使用第一阶段的最佳结果")
        use_second_stage = False
    else:
        logger.info(f"第二阶段结果 ({second_stage_best_value:.6f}) 优于第一阶段 ({first_stage_best_value:.6f})")
        logger.info("使用第二阶段的最佳结果")
        use_second_stage = True

    # 根据选择添加最佳结果到最终研究
    if use_second_stage:
        best_study = second_stage_study
        best_value = second_stage_best_value
    else:
        best_study = first_stage_study
        best_value = first_stage_best_value

    # 获取最佳策略信息并添加到最终研究
    try:
        best_params = best_study.best_params
        best_trial = best_study.best_trial
        
        # 从 user_attrs 中获取因子和排除条件信息
        rank_factors = best_trial.user_attrs.get('rank_factors', [])
        filter_conditions = best_trial.user_attrs.get('filter_conditions', [])

        # 创建分布字典（为语义化策略参数创建分布）
        distributions = {}
        for param_name, param_value in best_params.items():
            if param_name == "primary_strategy":
                from .config import StrategyConfig
                strategy_config = StrategyConfig()
                distributions[param_name] = optuna.distributions.CategoricalDistribution(
                    list(strategy_config.investment_strategies.keys())
                )
            elif param_name == "secondary_strategy":
                from .config import StrategyConfig
                strategy_config = StrategyConfig()
                available_secondary = list(strategy_config.investment_strategies.keys())
                distributions[param_name] = optuna.distributions.CategoricalDistribution(available_secondary)
            elif param_name == "use_mixed_strategy":
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            elif param_name.startswith("weight_"):
                distributions[param_name] = optuna.distributions.IntDistribution(1, 5)
            elif param_name.startswith("ascending_") or param_name.startswith("aux_ascending_"):
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            elif param_name.startswith("n_") and "factors" in param_name:
                distributions[param_name] = optuna.distributions.IntDistribution(1, 10)
            elif param_name == "enable_auxiliary":
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            elif isinstance(param_value, int):
                distributions[param_name] = optuna.distributions.IntDistribution(0, 100)
            elif isinstance(param_value, bool):
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            else:
                logger.warning(f"未知参数类型: {param_name} = {param_value}")

        # 创建最终trial，保存完整的user_attrs
        user_attrs = {
            "rank_factors": rank_factors,
            "filter_conditions": filter_conditions,
            "primary_strategy": best_params.get("primary_strategy"),
            "secondary_strategy": best_params.get("secondary_strategy"),
            "use_mixed_strategy": best_params.get("use_mixed_strategy", False)
        }
        
        trial = optuna.trial.create_trial(
            params=best_params, distributions=distributions, value=best_value, user_attrs=user_attrs
        )
        final_study.add_trial(trial)

        # 直接添加属性确保能被获取到（备用机制）
        setattr(final_study, "best_rank_factors", rank_factors)
        setattr(final_study, "best_filter_conditions", filter_conditions)

        # 打印最佳结果
        logger.info(f"\n最佳语义化策略组合 (CAGR: {best_value:.6f}):")
        
        # 打印策略信息
        primary_strategy = best_params.get("primary_strategy", "unknown")
        secondary_strategy = best_params.get("secondary_strategy")
        use_mixed = best_params.get("use_mixed_strategy", False)
        
        logger.info("🎢 投资策略:")
        logger.info(f"  主策略: {primary_strategy}")
        if use_mixed and secondary_strategy:
            logger.info(f"  次策略: {secondary_strategy}")
        
        logger.info("📊 打分因子:")
        for i, factor in enumerate(rank_factors):
            logger.info(f"  {i + 1}. {factor['name']}")
            logger.info(f"     - 权重: {factor['weight']}")
            logger.info(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
            logger.info(f"     - 来源: {factor.get('source', 'unknown')}")

        # 打印排除因子信息
        if filter_conditions:
            logger.info("🚫 排除因子:")
            for i, condition in enumerate(filter_conditions):
                logger.info(f"  {i + 1}. {condition['factor']} {condition['operator']} {condition['value']}")
        else:
            logger.info("🚫 排除因子: 无")

    except Exception as e:
        logger.error(f"创建最终研究时出错: {e}")
        raise e

    # 返回所有探索过的策略信息
    all_strategies = {
        'first_stage_strategies': first_stage_strategies,
        'refinement_strategies': best_strategies_for_refinement,
        'final_strategy': {
            'primary': best_params.get("primary_strategy"),
            'secondary': best_params.get("secondary_strategy"),
            'mixed': best_params.get("use_mixed_strategy", False)
        }
    }
    
    return final_study, all_strategies
