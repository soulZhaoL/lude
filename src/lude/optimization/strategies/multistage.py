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
   - 过滤因子的选择完全由配置文件filter_factors_config.yaml驱动
   - max_factors参数严格按照配置文件中的combination_rules.max_factors执行
   - 移除trial中不必要的因子选择逻辑
"""

import itertools
import os


import numpy as np
import optuna

from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.utils.common_utils import RESULTS_DIR  # 导入结果目录常量
from lude.utils.logger import optimization_logger as logger


def _prepare_all_filter_conditions(df, enable_filter_opt):
    """预处理生成所有可能的排除因子条件（类似打分因子的组合生成）

    Args:
        df: 数据框
        enable_filter_opt: 是否启用过滤优化

    Returns:
        all_filter_conditions: 所有可能的排除因子条件列表
    """
    if not enable_filter_opt:
        logger.info("过滤优化未启用，跳过排除因子条件生成")
        return None

    try:
        from lude.utils.filter_generator import FilterFactorGenerator

        # 直接从配置文件获取排除因子列表
        generator = FilterFactorGenerator()
        config_factors = generator.get_available_factors()

        logger.info(f"配置文件中的排除因子: {config_factors}")

        # 生成所有可能的排除因子条件组合
        all_filter_conditions = []
        for factor_name in config_factors:
            factor_config = generator.config['filter_factors'][factor_name]
            operators = factor_config.get('operators', ['gte', 'lte'])
            value_options = factor_config.get('value_options', [])

            # 为每个因子生成所有可能的条件
            for operator in operators:
                for value in value_options:
                    condition = {
                        'factor': factor_name,
                        'operator': generator._convert_operator(operator),
                        'value': value
                    }
                    all_filter_conditions.append(condition)

        logger.info(f"成功生成 {len(all_filter_conditions)} 个可能的排除因子条件")
        logger.info(
            f"每个trial将从中选择最多 {generator.config.get('combination_rules', {}).get('max_factors', 6)} 个条件")

        return all_filter_conditions

    except Exception as e:
        logger.error(f"生成排除因子条件时出错: {e}")
        return None


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
            # 动态选择排除因子数量 (0到max_filter_factors之间)
            num_filter_conditions = trial.suggest_int("num_filter_conditions", 0,
                                                      min(max_filter_factors, len(all_filter_conditions)))

            if num_filter_conditions > 0:
                # 选择具体的排除因子条件
                for i in range(num_filter_conditions):
                    condition_idx = trial.suggest_int(f"filter_condition_{i}_idx", 0, len(all_filter_conditions) - 1)
                    selected_filter_conditions.append(all_filter_conditions[condition_idx])

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
        except Exception as e:
            # 添加更详细的错误信息
            import traceback
            logger.error(f"计算CAGR时出错: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.error(f"当前打分因子: {rank_factors}")
            logger.error(f"当前排除因子: {selected_filter_conditions}")
            raise optuna.exceptions.TrialPruned()

    return objective


def _prepare_first_stage_combinations(factors, num_factors, args, max_combinations):
    """准备第一阶段的因子组合

    Args:
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量

    Returns:
        first_stage_combinations: 第一阶段因子组合列表
    """
    logger.info(f"准备第一阶段因子组合...")

    # 生成所有可能的组合
    all_combinations = []
    for combo in itertools.combinations(range(len(factors)), num_factors):
        all_combinations.append(tuple(sorted(combo)))

    # 如果组合数量过多，随机采样
    if len(all_combinations) > max_combinations:
        np.random.seed(args.seed)
        indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
        all_combinations = [all_combinations[i] for i in indices]

    logger.info(f"生成了 {len(all_combinations)} 个因子组合")

    # 将索引组合转换为实际因子组合
    first_stage_combinations = []
    for combo in all_combinations:
        factor_combo = tuple(factors[i] for i in combo)
        first_stage_combinations.append(factor_combo)

    return first_stage_combinations


def _create_study(study_name, args, sampler_type="random"):
    """创建optuna研究

    Args:
        study_name: 研究名称
        args: 参数
        sampler_type: 采样器类型 ("random" 或 "tpe")

    Returns:
        study: optuna研究对象
    """
    db_path = os.path.join(RESULTS_DIR, f"{study_name}.db")
    storage_name = f"sqlite:///{db_path}"

    try:
        # 尝试加载已有的研究
        study = optuna.load_study(study_name=study_name, storage=storage_name)
        logger.info(f"加载已有的研究 {study_name}，已完成 {len(study.trials)} 次试验")
    except:
        # 创建新的研究
        if sampler_type == "random":
            sampler = optuna.samplers.RandomSampler(seed=args.seed)
        else:
            sampler = optuna.samplers.TPESampler(seed=args.seed)

        study = optuna.create_study(
            study_name=study_name, storage=storage_name, direction="maximize", sampler=sampler, load_if_exists=True
        )
        logger.info(f"创建新的研究 {study_name}")

    return study


def _run_first_stage_optimization(df, factors, num_factors, args, max_combinations, all_filter_conditions=None):
    """运行第一阶段优化（专注因子组合探索）

    Args:
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        all_filter_conditions: 所有可能的排除因子条件

    Returns:
        first_stage_study: 第一阶段研究
        first_stage_combinations: 第一阶段因子组合
    """
    logger.info("\n===== 第一阶段：探索因子组合 =====")

    # 准备因子组合
    first_stage_combinations = _prepare_first_stage_combinations(factors, num_factors, args, max_combinations)

    # 创建第一阶段研究
    study_name = f"first_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
    first_stage_study = _create_study(study_name, args, "random")

    # 获取max_filter_factors配置（一次性加载，避免重复）
    from lude.utils.filter_generator import FilterFactorGenerator
    generator = FilterFactorGenerator()
    max_filter_factors = generator.config.get('combination_rules', {}).get('max_factors', 6)

    # 创建目标函数（使用所有可能的排除因子条件）
    objective_func = create_optimized_objective_function(df, first_stage_combinations, args, all_filter_conditions,
                                                         max_filter_factors)

    # 执行第一阶段优化
    n_trials_first_stage = min(args.n_trials // 2, 2000)
    adjusted_n_jobs = max(1, min(args.n_jobs // 2, 10))

    try:
        first_stage_study.optimize(
            objective_func, n_trials=n_trials_first_stage, n_jobs=adjusted_n_jobs, gc_after_trial=True
        )
    except KeyboardInterrupt:
        logger.warning("用户中断了第一阶段优化")
    except Exception as e:
        logger.error(f"第一阶段优化出错: {e}")

    return first_stage_study, first_stage_combinations


def _get_first_stage_results(first_stage_study, first_stage_combinations, _num_factors):
    """获取第一阶段结果

    Args:
        first_stage_study: 第一阶段研究
        first_stage_combinations: 第一阶段因子组合
        num_factors: 因子数量

    Returns:
        best_params: 最佳参数
        best_value: 最佳值
        best_combination: 最佳因子组合
    """
    # 检查第一阶段是否有结果
    if len(first_stage_study.trials) == 0:
        logger.error("第一阶段没有完成任何试验，无法继续")
        return None, None, None

    # 获取第一阶段最佳结果
    best_params = first_stage_study.best_params
    best_value = first_stage_study.best_value

    logger.info(f"\n第一阶段最佳CAGR: {best_value:.6f}")

    # 提取最佳因子组合
    if "combination_idx" in best_params:
        best_combination_idx = best_params["combination_idx"]
        best_combination = first_stage_combinations[best_combination_idx]

        logger.info(f"第一阶段最佳因子组合 (CAGR: {best_value:.6f}):")
        for i, factor in enumerate(best_combination):
            weight_param = f"factor{i}_weight"
            asc_param = f"factor{i}_ascending"

            weight = best_params.get(weight_param, 1)
            ascending = best_params.get(asc_param, True)

            direction = "升序" if ascending else "降序"
            logger.info(f"  {i + 1}. {factor}")
            logger.info(f"     - 权重: {weight}")
            logger.info(f"     - 排序方向: {direction}")

        return best_params, best_value, best_combination
    else:
        logger.warning("无法获取第一阶段最佳因子组合")
        return None, None, None


def _prepare_second_stage_combinations(factors, num_factors, best_combination, max_combinations, args):
    """准备第二阶段的因子组合

    Args:
        factors: 因子列表
        num_factors: 因子数量
        best_combination: 第一阶段最佳组合
        max_combinations: 最大组合数量
        args: 参数

    Returns:
        second_stage_combinations: 第二阶段因子组合列表
    """
    logger.info("准备第二阶段因子组合...")

    # 生成第二阶段的因子组合
    # 策略：从最佳组合开始，替换1-2个因子生成新组合
    second_stage_combinations = []

    # 添加第一阶段最佳组合
    second_stage_combinations.append(best_combination)

    # 替换1个因子生成新组合
    for i in range(num_factors):
        for factor in factors:
            if factor not in best_combination:
                new_combination = list(best_combination)
                new_combination[i] = factor
                new_combination = tuple(sorted(new_combination))
                if new_combination not in second_stage_combinations:
                    second_stage_combinations.append(new_combination)

    # 如果组合数量较少，替换2个因子生成更多组合
    if len(second_stage_combinations) < 100:
        for i, j in itertools.combinations(range(num_factors), 2):
            for factor1, factor2 in itertools.combinations([f for f in factors if f not in best_combination], 2):
                new_combination = list(best_combination)
                new_combination[i] = factor1
                new_combination[j] = factor2
                new_combination = tuple(sorted(new_combination))
                if new_combination not in second_stage_combinations:
                    second_stage_combinations.append(new_combination)

    # 限制第二阶段组合数量
    max_second_stage = min(500, max_combinations // 10)
    if len(second_stage_combinations) > max_second_stage:
        np.random.seed(args.seed)
        indices = np.random.choice(len(second_stage_combinations), max_second_stage, replace=False)
        second_stage_combinations = [second_stage_combinations[i] for i in indices]

    logger.info(f"第二阶段将探索 {len(second_stage_combinations)} 个因子组合")

    return second_stage_combinations


def _add_first_stage_best_to_second_stage(
        second_stage_study, first_stage_best_params, first_stage_best_value, second_stage_combinations, num_factors
):
    """将第一阶段最佳结果添加到第二阶段研究中

    Args:
        second_stage_study: 第二阶段研究
        first_stage_best_params: 第一阶段最佳参数
        first_stage_best_value: 第一阶段最佳值
        second_stage_combinations: 第二阶段组合
        num_factors: 因子数量
    """
    try:
        # 获取第一阶段最佳组合在第二阶段组合中的索引
        first_best_combination_idx = 0  # 已经确保第一阶段最佳组合在第二阶段组合的第一个位置

        # 创建新的参数集合
        new_params = {"combination_idx": first_best_combination_idx}

        # 复制所有因子参数
        for i in range(num_factors):
            weight_param = f"factor{i}_weight"
            asc_param = f"factor{i}_ascending"
            if weight_param in first_stage_best_params:
                new_params[weight_param] = first_stage_best_params[weight_param]
            if asc_param in first_stage_best_params:
                new_params[asc_param] = first_stage_best_params[asc_param]

        # 创建分布字典
        distributions = {}
        distributions["combination_idx"] = optuna.distributions.IntDistribution(0, len(second_stage_combinations) - 1)
        for i in range(num_factors):
            weight_param = f"factor{i}_weight"
            asc_param = f"factor{i}_ascending"
            distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
            distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

        # 创建trial并添加到研究中
        trial = optuna.trial.create_trial(params=new_params, distributions=distributions, value=first_stage_best_value)
        second_stage_study.add_trial(trial)
        logger.info("成功将第一阶段最佳参数添加到第二阶段研究中")
    except Exception as e:
        logger.error(f"添加第一阶段最佳参数到第二阶段时出错: {e}")
        logger.warning("继续执行第二阶段...")


def _run_second_stage_optimization(
        df,
        factors,
        num_factors,
        args,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_combinations,
        max_combinations,
        all_filter_conditions=None,
):
    """运行第二阶段优化（专注权重和排序方向优化）

    Args:
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        first_stage_best_params: 第一阶段最佳参数
        first_stage_best_value: 第一阶段最佳值
        first_stage_combinations: 第一阶段因子组合
        max_combinations: 最大组合数量
        all_filter_conditions: 所有可能的排除因子条件

    Returns:
        second_stage_study: 第二阶段研究
        second_stage_combinations: 第二阶段因子组合
    """
    logger.info("\n===== 第二阶段：优化权重和排序方向 =====")

    # 获取第一阶段最佳组合
    best_combination_idx = first_stage_best_params["combination_idx"]
    best_combination = first_stage_combinations[best_combination_idx]

    # 准备第二阶段因子组合（基于第一阶段最佳组合的变化）
    second_stage_combinations = _prepare_second_stage_combinations(
        factors, num_factors, best_combination, max_combinations, args
    )

    # 创建第二阶段研究
    study_name = f"second_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
    second_stage_study = _create_study(study_name, args, args.method)

    # 将第一阶段最佳结果添加到第二阶段
    _add_first_stage_best_to_second_stage(
        second_stage_study, first_stage_best_params, first_stage_best_value, second_stage_combinations, num_factors
    )

    # 获取max_filter_factors配置（复用第一阶段的配置，避免重复加载）
    from lude.utils.filter_generator import FilterFactorGenerator
    generator = FilterFactorGenerator()
    max_filter_factors = generator.config.get('combination_rules', {}).get('max_factors', 6)

    # 创建目标函数（使用所有可能的排除因子条件）
    objective_func = create_optimized_objective_function(df, second_stage_combinations, args, all_filter_conditions,
                                                         max_filter_factors)

    # 执行第二阶段优化
    n_trials_first_stage = min(args.n_trials // 2, 2000)
    n_trials_second_stage = args.n_trials - n_trials_first_stage
    adjusted_n_jobs = max(1, min(args.n_jobs // 2, 10))

    try:
        second_stage_study.optimize(
            objective_func, n_trials=n_trials_second_stage, n_jobs=adjusted_n_jobs, gc_after_trial=True
        )
    except KeyboardInterrupt:
        logger.warning("用户中断了第二阶段优化")
    except Exception as e:
        logger.error(f"第二阶段优化出错: {e}")

    return second_stage_study, second_stage_combinations


def _build_rank_factors(best_params, combinations, _num_factors):
    """重建rank_factors

    Args:
        best_params: 最佳参数
        combinations: 因子组合
        num_factors: 因子数量

    Returns:
        rank_factors: 重建的rank_factors列表
    """
    combination_idx = best_params["combination_idx"]
    combination = combinations[combination_idx]

    rank_factors = []
    for i, factor in enumerate(combination):
        weight_param = f"factor{i}_weight"
        asc_param = f"factor{i}_ascending"

        factor_info = {
            "name": factor,
            "weight": best_params.get(weight_param, 1),
            "ascending": best_params.get(asc_param, True),
        }
        rank_factors.append(factor_info)

    return rank_factors


def _create_final_study_and_merge_results(
        args,
        first_stage_study,
        first_stage_combinations,
        second_stage_study,
        second_stage_combinations,
        first_stage_best_value,
        num_factors,
):
    """创建最终研究并合并结果

    Args:
        args: 参数
        first_stage_study: 第一阶段研究
        first_stage_combinations: 第一阶段组合
        second_stage_study: 第二阶段研究
        second_stage_combinations: 第二阶段组合
        first_stage_best_value: 第一阶段最佳值
        num_factors: 因子数量

    Returns:
        final_study: 最终研究
        all_combinations: 所有组合
    """
    # 创建最终研究
    study_name = f"final_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
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
        best_combinations = second_stage_combinations
        best_value = second_stage_best_value
    else:
        best_study = first_stage_study
        best_combinations = first_stage_combinations
        best_value = first_stage_best_value

    # 重建rank_factors并添加到最终研究
    try:
        best_params = best_study.best_params
        rank_factors = _build_rank_factors(best_params, best_combinations, num_factors)

        # 创建分布字典
        distributions = {}
        distributions["combination_idx"] = optuna.distributions.IntDistribution(0, len(best_combinations) - 1)
        for i in range(num_factors):
            weight_param = f"factor{i}_weight"
            asc_param = f"factor{i}_ascending"
            distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
            distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

        # 创建最终trial
        trial = optuna.trial.create_trial(
            params=best_params, distributions=distributions, value=best_value, user_attrs={"rank_factors": rank_factors}
        )
        final_study.add_trial(trial)

        # 直接添加属性确保能被获取到
        setattr(final_study, "best_rank_factors", rank_factors)

        # 打印最佳结果
        logger.info(f"\n最佳因子组合 (CAGR: {best_value:.6f}):")
        for i, factor in enumerate(rank_factors):
            logger.info(f"  {i + 1}. {factor['name']}")
            logger.info(f"     - 权重: {factor['weight']}")
            logger.info(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")

    except Exception as e:
        logger.error(f"创建最终研究时出错: {e}")

    # 返回所有探索过的因子组合
    all_combinations = list(set(first_stage_combinations + second_stage_combinations))
    return final_study, all_combinations


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

    # 预处理阶段：生成所有可能的排除因子条件
    logger.info("\n===== 预处理阶段：生成所有可能的排除因子条件 =====")
    all_filter_conditions = _prepare_all_filter_conditions(df, enable_filter_opt)

    # 第一阶段：专注因子组合探索
    first_stage_study, first_stage_combinations = _run_first_stage_optimization(
        df, factors, num_factors, args, max_combinations, all_filter_conditions
    )

    # 获取第一阶段结果
    first_stage_best_params, first_stage_best_value, _ = _get_first_stage_results(
        first_stage_study, first_stage_combinations, num_factors
    )

    if first_stage_best_params is None:
        logger.warning("第一阶段最佳参数为空，跳过第二阶段优化")
        return factors, first_stage_combinations, first_stage_study

    # 第二阶段：专注权重和排序方向优化
    second_stage_study, second_stage_combinations = _run_second_stage_optimization(
        df,
        factors,
        num_factors,
        args,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_combinations,
        max_combinations,
        all_filter_conditions,
    )

    # 创建最终研究并合并结果
    final_study, all_combinations = _create_final_study_and_merge_results(
        args,
        first_stage_study,
        first_stage_combinations,
        second_stage_study,
        second_stage_combinations,
        first_stage_best_value,
        num_factors,
    )

    return factors, all_combinations, final_study
