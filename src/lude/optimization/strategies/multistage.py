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

import itertools
import os
import json
import time
from typing import Dict, Optional

import numpy as np
import optuna

from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.utils.common_utils import RESULTS_DIR  # 导入结果目录常量
from lude.utils.logger import optimization_logger as logger
from lude.utils.memory_monitor import check_memory_warning, log_memory_stats

def _validate_filter_conditions(selected_filter_conditions):
    """验证排除因子条件的有效性
    
    Args:
        selected_filter_conditions: 选择的排除因子条件列表
    
    Returns:
        tuple: (is_valid, error_msg)
    """
    if not selected_filter_conditions:
        return True, "无排除因子条件"
    
    # 检查重复因子 + 操作符组合
    factor_operator_combinations = set()
    factor_conditions = {}  # {factor_name: [conditions]}
    
    for cond in selected_filter_conditions:
        factor_name = cond['factor']
        operator = cond['operator']
        value = cond['value']
        
        # 检查重复的因子+操作符
        factor_op = (factor_name, operator)
        if factor_op in factor_operator_combinations:
            return False, f"存在重复的因子+操作符组合: {factor_name} {operator}"
        factor_operator_combinations.add(factor_op)
        
        # 按因子分组收集条件
        if factor_name not in factor_conditions:
            factor_conditions[factor_name] = []
        factor_conditions[factor_name].append({'operator': operator, 'value': value})
    
    # 检查同因子的范围条件是否合理
    for factor_name, conditions in factor_conditions.items():
        if len(conditions) >= 2:
            # 有多个条件时，检查是否能形成合理范围
            ge_values = [c['value'] for c in conditions if c['operator'] == '>=']
            le_values = [c['value'] for c in conditions if c['operator'] == '<=']
            
            # 如果有>=和<=条件，检查范围合理性
            if ge_values and le_values:
                min_ge = min(ge_values)
                max_le = max(le_values)
                if min_ge > max_le:
                    return False, f"因子 {factor_name} 的范围条件不合理: >= {min_ge} 且 <= {max_le}"
    
    return True, "条件有效"


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
        from lude.utils.filter_generator_optimized import OptimizedFilterFactorGenerator

        # 直接从优化配置文件获取排除因子列表
        generator = OptimizedFilterFactorGenerator()
        config_factors = generator.get_available_factors()

        logger.info(f"配置文件中的排除因子: {config_factors}")

        # 生成所有可能的排除因子条件组合
        all_filter_conditions = []
        for factor_name in config_factors:
            # 使用新生成器的方法生成单因子条件
            conditions = generator.generate_single_factor_conditions(factor_name)
            all_filter_conditions.extend(conditions)

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
    
    # ========== 🎯 预生成无操作符冲突的条件索引组合 ==========
    filter_index_combinations = []
    if all_filter_conditions and len(all_filter_conditions) > 0:
        max_cond = min(max_filter_factors, len(all_filter_conditions))
        min_cond = max(1, max_cond - 1)  # 确保至少选择1个条件
        logger.info(f"过滤因子条件, max_cond: {max_cond}, min_cond: {min_cond}")
        
        # 🚨 关键设计：预构建无操作符冲突的有效索引组合
        # 允许同名因子，但禁止相同操作符重复（如两个"pct_chg >="）
        def is_valid_combination(indices):
            """检查索引组合是否有效：禁止相同因子的相同操作符重复，但允许不同阈值"""
            selected_conditions = [all_filter_conditions[i] for i in indices]
            
            # 🚨 关键修复：按 (factor, operator) 分组，但允许不同的value值
            # 统计每个 (因子,操作符) 组合的出现次数
            factor_operator_combinations = []
            for condition in selected_conditions:
                combo_key = (condition['factor'], condition['operator'])
                factor_operator_combinations.append(combo_key)
            
            # 检查是否有重复的 (因子,操作符) 组合
            from collections import Counter
            combo_counts = Counter(factor_operator_combinations)
            
            # 如果任何 (因子,操作符) 组合出现次数>1，则无效
            for count in combo_counts.values():
                if count > 1:
                    return False
            return True
        
        # 预生成所有有效的索引组合
        valid_count = 0
        total_count = 0
        for num_conditions in range(min_cond, max_cond + 1):
            for combo_indices in itertools.combinations(range(len(all_filter_conditions)), num_conditions):
                total_count += 1
                if is_valid_combination(combo_indices):
                    filter_index_combinations.append(list(combo_indices))
                    valid_count += 1
        
        logger.info(f"预生成 {valid_count} 个无操作符冲突的有效索引组合 (总计{total_count}个，过滤率{(total_count-valid_count)/total_count*100:.1f}%)")

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

        # ========== 🎯 选择无操作符冲突的排除因子条件 ==========
        selected_filter_conditions = []
        if filter_index_combinations and all_filter_conditions:
            # 直接从预构建的有效组合中选择，无需后处理
            combo_idx = trial.suggest_int("filter_combo_idx", 0, len(filter_index_combinations) - 1)
            selected_indices = filter_index_combinations[combo_idx]
            
            # 根据索引获取条件，已确保无操作符冲突
            selected_filter_conditions = [all_filter_conditions[idx] for idx in selected_indices]

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
            n_startup_trials=10,      # 从默认10减少到10（已经是最小）
            n_ei_candidates=12,       # 从默认24减少到12（节省50%内存）
            # multivariate=False,       # 禁用多变量采样（显著节省内存）
            # constant_liar=False,      # 禁用并行优化谎言策略（节省内存）
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
    # 包含所有关键参数避免数据混合，添加时间戳确保每次运行独立
    filter_suffix = "filter" if getattr(args, 'enable_filter_opt', False) else "nofilter"
    timestamp = int(time.time())  # 添加时间戳确保唯一性
    args._optimization_timestamp = timestamp  # 保存时间戳供后续阶段使用
    study_name = f"first_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{filter_suffix}_{args.seed}_{timestamp}"
    first_stage_study = _create_study(study_name, args, "random")

    # 获取max_filter_factors配置（一次性加载，避免重复）
    from lude.utils.filter_generator_optimized import OptimizedFilterFactorGenerator
    generator = OptimizedFilterFactorGenerator()
    max_filter_factors = generator.config.get('combination_rules', {}).get('max_factors', 6)

    # 创建目标函数（使用所有可能的排除因子条件）
    objective_func = create_optimized_objective_function(df, first_stage_combinations, args, all_filter_conditions,
                                                         max_filter_factors)

    # 执行第一阶段优化
    n_trials_first_stage = min(args.n_trials // 2, 2000)
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

    return first_stage_study, first_stage_combinations


def _get_first_stage_results(first_stage_study, first_stage_combinations, _num_factors):
    """获取第一阶段结果，包括TOP 10组合

    Args:
        first_stage_study: 第一阶段研究
        first_stage_combinations: 第一阶段因子组合
        num_factors: 因子数量

    Returns:
        best_params: 最佳参数
        best_value: 最佳值
        best_combination: 最佳因子组合
        top_combinations_with_params: TOP 10组合及其参数列表
    """
    # 检查第一阶段是否有结果
    if len(first_stage_study.trials) == 0:
        logger.error("第一阶段没有完成任何试验，无法继续")
        return None, None, None, []

    # 获取第一阶段最佳结果
    best_params = first_stage_study.best_params
    best_value = first_stage_study.best_value

    logger.info(f"\n第一阶段最佳CAGR: {best_value:.6f}")

    # 获取TOP 10组合及其参数
    top_combinations_with_params = []
    if len(first_stage_study.trials) > 0:
        # 按CAGR值排序获取TOP 10
        valid_trials = [t for t in first_stage_study.trials if t.value is not None]
        sorted_trials = sorted(valid_trials, key=lambda t: t.value, reverse=True)
        top_trials = sorted_trials[:min(10, len(sorted_trials))]
        
        logger.info(f"\n第一阶段TOP {len(top_trials)} 组合:")
        for idx, trial in enumerate(top_trials):
            if "combination_idx" in trial.params:
                combo_idx = trial.params["combination_idx"]
                combination = first_stage_combinations[combo_idx]
                
                # 收集组合及其参数信息
                combination_info = {
                    'combination': combination,
                    'params': trial.params,
                    'value': trial.value,
                    'user_attrs': trial.user_attrs
                }
                top_combinations_with_params.append(combination_info)
                
                # 打印基本信息
                logger.info(f"  {idx + 1}. CAGR: {trial.value:.6f}, 组合: {combination}")
                
                # 打印详细的因子权重和排序方向信息
                logger.info(f"     详细配置:")
                for i, factor in enumerate(combination):
                    weight_param = f"factor{i}_weight"
                    asc_param = f"factor{i}_ascending"
                    
                    weight = trial.params.get(weight_param, 1)
                    ascending = trial.params.get(asc_param, True)
                    direction = "升序" if ascending else "降序"
                    
                    logger.info(f"       - {factor}: 权重={weight}, 方向={direction}")

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

        return best_params, best_value, best_combination, top_combinations_with_params
    else:
        logger.warning("无法获取第一阶段最佳因子组合")
        return None, None, None, top_combinations_with_params


def _prepare_second_stage_combinations_enhanced(factors, num_factors, top_combinations_with_params, max_combinations, args):
    """增强的第二阶段因子组合准备
    
    基于TOP 10组合的多策略生成：
    1. 添加TOP 10原始组合
    2. 对TOP 10进行替换1个因子
    3. 对TOP 10进行权重调整 (±1)
    4. 控制总数不超过max_combinations/2

    Args:
        factors: 因子列表
        num_factors: 因子数量  
        top_combinations_with_params: TOP 10组合及其参数信息
        max_combinations: 最大组合数量
        args: 参数

    Returns:
        second_stage_combinations: 第二阶段因子组合列表
        second_stage_combination_details: 组合详细信息（包含权重等）
    """
    logger.info("准备增强的第二阶段因子组合...")
    
    second_stage_combinations = []
    second_stage_combination_details = []
    combination_set = set()  # 用于去重
    
    # 配置限制
    max_second_stage = max_combinations // 2  # 50,000
    available_factors = [f for f in factors]  # 所有可用因子
    
    logger.info(f"目标组合数量上限: {max_second_stage}")
    logger.info(f"可用因子总数: {len(available_factors)}")
    logger.info(f"TOP组合数量: {len(top_combinations_with_params)}")

    # ========== 策略1: 添加TOP 10原始组合 ==========
    logger.info("策略1: 添加TOP组合...")
    for combo_info in top_combinations_with_params:
        combination = combo_info['combination']
        combination_key = tuple(sorted(combination))
        
        if combination_key not in combination_set:
            second_stage_combinations.append(combination)
            second_stage_combination_details.append({
                'combination': combination,
                'source': 'top_original',
                'base_params': combo_info['params']
            })
            combination_set.add(combination_key)
    
    logger.info(f"策略1完成，当前组合数: {len(second_stage_combinations)}")

    # ========== 策略2: 对TOP 10进行替换1个因子 ==========
    logger.info("策略2: 替换1个因子...")
    for combo_info in top_combinations_with_params:
        if len(second_stage_combinations) >= max_second_stage:
            break
            
        base_combination = combo_info['combination']
        base_params = combo_info['params']
        
        # 对每个位置尝试替换
        for i in range(num_factors):
            if len(second_stage_combinations) >= max_second_stage:
                break
                
            for factor in available_factors:
                if factor not in base_combination:  # 避免替换成相同因子
                    new_combination = list(base_combination)
                    new_combination[i] = factor
                    new_combination = tuple(new_combination)
                    combination_key = tuple(sorted(new_combination))
                    
                    if combination_key not in combination_set:
                        second_stage_combinations.append(new_combination)
                        second_stage_combination_details.append({
                            'combination': new_combination,
                            'source': 'factor_replacement',
                            'base_params': base_params,
                            'replaced_position': i,
                            'original_factor': base_combination[i],
                            'new_factor': factor
                        })
                        combination_set.add(combination_key)
    
    logger.info(f"策略2完成，当前组合数: {len(second_stage_combinations)}")

    # ========== 策略3: 权重调整变体 ==========  
    logger.info("策略3: 权重调整变体...")
    weight_variants = []
    
    for combo_info in top_combinations_with_params:
        if len(weight_variants) >= max_second_stage // 4:  # 限制权重变体数量
            break
            
        base_combination = combo_info['combination'] 
        base_params = combo_info['params']
        
        # 策略3A: 系统性权重调整 - 对每个因子都尝试±1
        for i in range(num_factors):
            weight_param = f"factor{i}_weight"
            original_weight = base_params.get(weight_param, 1)
            
            # +1 变体
            if original_weight < 5:
                new_params = base_params.copy()
                new_params[weight_param] = original_weight + 1
                weight_variants.append({
                    'combination': base_combination,
                    'source': 'weight_systematic',
                    'base_params': new_params,
                    'adjustment': f"factor{i}_weight: {original_weight} -> {original_weight + 1}"
                })
            
            # -1 变体  
            if original_weight > 1:
                new_params = base_params.copy()
                new_params[weight_param] = original_weight - 1
                weight_variants.append({
                    'combination': base_combination,
                    'source': 'weight_systematic', 
                    'base_params': new_params,
                    'adjustment': f"factor{i}_weight: {original_weight} -> {original_weight - 1}"
                })
        
        # 策略3B: 随机权重调整 - 随机选择1个因子进行±1调整
        # 确保可重复性，使用安全的种子值
        combo_hash = abs(hash(str(base_combination))) % (2**32 - 1)
        np.random.seed((args.seed + combo_hash) % (2**32 - 1))
        
        # 生成多个随机权重变体（每个TOP组合生成3-5个随机变体）
        num_random_variants = np.random.randint(3, 6)  # 随机3-5个变体
        
        for _ in range(num_random_variants):
            if len(weight_variants) >= max_second_stage // 4:
                break
                
            # 随机选择一个因子位置
            random_factor_idx = np.random.randint(0, num_factors)
            weight_param = f"factor{random_factor_idx}_weight"
            original_weight = base_params.get(weight_param, 1)
            
            # 随机选择+1或-1
            adjustment = np.random.choice([+1, -1])
            new_weight = original_weight + adjustment
            
            # 检查权重范围合法性
            if 1 <= new_weight <= 5:
                new_params = base_params.copy()
                new_params[weight_param] = new_weight
                weight_variants.append({
                    'combination': base_combination,
                    'source': 'weight_random',
                    'base_params': new_params,
                    'adjustment': f"factor{random_factor_idx}_weight: {original_weight} -> {new_weight} (random)"
                })
    
    # 添加权重变体到最终列表
    for variant in weight_variants:
        if len(second_stage_combinations) >= max_second_stage:
            break
        second_stage_combinations.append(variant['combination'])
        second_stage_combination_details.append(variant)
    
    logger.info(f"策略3完成，当前组合数: {len(second_stage_combinations)}")

    # ========== 最终控制：确保不超过上限 ==========
    if len(second_stage_combinations) > max_second_stage:
        logger.info(f"组合数量({len(second_stage_combinations)})超过上限({max_second_stage})，进行随机采样...")
        np.random.seed(args.seed)
        indices = np.random.choice(len(second_stage_combinations), max_second_stage, replace=False)
        second_stage_combinations = [second_stage_combinations[i] for i in indices]
        second_stage_combination_details = [second_stage_combination_details[i] for i in indices]

    logger.info(f"第二阶段最终将探索 {len(second_stage_combinations)} 个因子组合")
    
    # 统计各策略贡献
    strategy_counts = {}
    for detail in second_stage_combination_details:
        source = detail['source']
        strategy_counts[source] = strategy_counts.get(source, 0) + 1
    
    logger.info("各策略贡献统计:")
    for strategy, count in strategy_counts.items():
        logger.info(f"  {strategy}: {count} 个组合")

    return second_stage_combinations, second_stage_combination_details


def _add_first_stage_best_to_second_stage(
        second_stage_study, first_stage_study, first_stage_best_params, first_stage_best_value, second_stage_combinations, num_factors
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

        # 🎯 复制排除因子相关参数
        for param_name, param_value in first_stage_best_params.items():
            if param_name.startswith("num_filter_conditions") or param_name.startswith("filter_condition_") or param_name == "filter_combo_idx":
                new_params[param_name] = param_value

        # 创建分布字典
        distributions = {}
        distributions["combination_idx"] = optuna.distributions.IntDistribution(0, len(second_stage_combinations) - 1)
        for i in range(num_factors):
            weight_param = f"factor{i}_weight"
            asc_param = f"factor{i}_ascending"
            distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
            distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

        # 🎯 修复方案：为排除因子参数创建固定的分布 - 避免动态调整破坏参数空间一致性
        from lude.utils.filter_generator_optimized import OptimizedFilterFactorGenerator
        generator = OptimizedFilterFactorGenerator()
        for param_name in new_params:
            if param_name.startswith("filter_condition_") and param_name.endswith("_idx"):
                # 需要获取all_filter_conditions的长度，但这个函数没有传入该参数
                # 重新生成来获取正确的范围
                config_factors = generator.get_available_factors()
                all_filter_conditions = []
                for factor_name in config_factors:
                    conditions = generator.generate_single_factor_conditions(factor_name)
                    all_filter_conditions.extend(conditions)
                
                if all_filter_conditions:
                    distributions[param_name] = optuna.distributions.IntDistribution(0, len(all_filter_conditions) - 1)
                else:
                    distributions[param_name] = optuna.distributions.IntDistribution(0, 0)
            elif param_name == "filter_combo_idx":
                # 简洁处理：filter_combo_idx在objective函数中动态建议，无需预设复杂分布
                distributions[param_name] = optuna.distributions.IntDistribution(0, max(100, param_value))

        # 获取第一阶段最佳trial的user_attrs，确保filter_conditions被正确传递
        first_stage_user_attrs = first_stage_study.best_trial.user_attrs
        logger.info(f"调试：第一阶段最佳trial的user_attrs: {first_stage_user_attrs}")
        
        # 创建trial并添加到研究中，保留第一阶段的user_attrs
        trial = optuna.trial.create_trial(
            params=new_params, 
            distributions=distributions, 
            value=first_stage_best_value,
            user_attrs=first_stage_user_attrs
        )
        second_stage_study.add_trial(trial)
        logger.info("成功将第一阶段最佳参数（包括user_attrs）添加到第二阶段研究中")
    except Exception as e:
        logger.error(f"添加第一阶段最佳参数到第二阶段时出错: {e}")
        logger.warning("继续执行第二阶段...")


def _run_second_stage_optimization(
        df,
        factors,
        num_factors,
        args,
        first_stage_study,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_combinations,
        top_combinations_with_params,
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

    # 使用增强的第二阶段组合准备（基于TOP 10组合）
    second_stage_combinations, second_stage_combination_details = _prepare_second_stage_combinations_enhanced(
        factors, num_factors, top_combinations_with_params, max_combinations, args
    )

    # 创建第二阶段研究  
    # 包含所有关键参数避免数据混合，使用相同时间戳保持一致性
    filter_suffix = "filter" if getattr(args, 'enable_filter_opt', False) else "nofilter"
    # 使用与第一阶段相同的时间戳，保持多阶段研究的关联性
    timestamp = getattr(args, '_optimization_timestamp', int(time.time()))
    study_name = f"second_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{filter_suffix}_{args.seed}_{timestamp}"
    second_stage_study = _create_study(study_name, args, args.method)

    # 将第一阶段最佳结果添加到第二阶段
    _add_first_stage_best_to_second_stage(
        second_stage_study, first_stage_study, first_stage_best_params, first_stage_best_value, second_stage_combinations, num_factors
    )

    # 获取max_filter_factors配置（复用第一阶段的配置，避免重复加载）
    from lude.utils.filter_generator_optimized import OptimizedFilterFactorGenerator
    generator = OptimizedFilterFactorGenerator()
    max_filter_factors = generator.config.get('combination_rules', {}).get('max_factors', 6)

    # 创建目标函数（使用所有可能的排除因子条件）
    objective_func = create_optimized_objective_function(df, second_stage_combinations, args, all_filter_conditions,
                                                         max_filter_factors)

    # 执行第二阶段优化
    n_trials_first_stage = min(args.n_trials // 2, 2000)
    n_trials_second_stage = args.n_trials - n_trials_first_stage
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
        all_filter_conditions=None,
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
        all_filter_conditions: 所有排除因子条件列表

    Returns:
        final_study: 最终研究
        all_combinations: 所有组合
    """
    # 创建最终研究
    # 包含所有关键参数避免数据混合，使用相同时间戳保持一致性
    filter_suffix = "filter" if getattr(args, 'enable_filter_opt', False) else "nofilter"
    # 使用与前两阶段相同的时间戳
    timestamp = getattr(args, '_optimization_timestamp', int(time.time()))
    study_name = f"final_{args.strategy}_{args.method}_{args.n_factors}factors_{args.start_date}_{args.end_date}_{args.price_min}_{args.price_max}_{args.hold_num}_{args.n_trials}trials_{filter_suffix}_{args.seed}_{timestamp}"
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

        # 创建分布字典，完全匹配best_params中的参数
        distributions = {}
        for param_name, param_value in best_params.items():
            if param_name == "combination_idx":
                distributions[param_name] = optuna.distributions.IntDistribution(0, len(best_combinations) - 1)
            elif param_name.endswith("_weight"):
                distributions[param_name] = optuna.distributions.IntDistribution(1, 5)
            elif param_name.endswith("_ascending"):
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            elif param_name == "use_filter":
                distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
            elif param_name.startswith("filter_condition_") and param_name.endswith("_idx"):
                # 🎯 关键修复：使用固定的分布范围，不根据参数值动态调整
                if all_filter_conditions:
                    # 使用固定的分布范围，保持参数空间一致性
                    distributions[param_name] = optuna.distributions.IntDistribution(0, len(all_filter_conditions) - 1)
                else:
                    distributions[param_name] = optuna.distributions.IntDistribution(0, 0)
            elif param_name == "filter_combo_idx":
                # 简洁处理：filter_combo_idx在objective函数中动态建议，无需预设复杂分布
                distributions[param_name] = optuna.distributions.IntDistribution(0, max(100, param_value))
            else:
                # 其他参数类型处理
                if isinstance(param_value, int):
                    # 🚨 安全修复：确保范围包含当前参数值
                    max_range = max(100, param_value)
                    distributions[param_name] = optuna.distributions.IntDistribution(0, max_range)
                elif isinstance(param_value, bool):
                    distributions[param_name] = optuna.distributions.CategoricalDistribution([True, False])
                else:
                    logger.warning(f"未知参数类型: {param_name} = {param_value}")

        # 获取原始trial的filter_conditions
        original_filter_conditions = best_study.best_trial.user_attrs.get('filter_conditions', [])
        logger.info(f"调试：从原始trial获取的filter_conditions: {original_filter_conditions}")
        
        # 创建最终trial，保存完整的user_attrs
        user_attrs = {
            "rank_factors": rank_factors,
            "filter_conditions": original_filter_conditions
        }
        trial = optuna.trial.create_trial(
            params=best_params, distributions=distributions, value=best_value, user_attrs=user_attrs
        )
        final_study.add_trial(trial)

        # 直接添加属性确保能被获取到（备用机制）
        setattr(final_study, "best_rank_factors", rank_factors)
        setattr(final_study, "best_filter_conditions", original_filter_conditions)

        # 打印最佳结果
        logger.info(f"\n最佳因子组合 (CAGR: {best_value:.6f}):")
        logger.info("📊 打分因子:")
        for i, factor in enumerate(rank_factors):
            logger.info(f"  {i + 1}. {factor['name']}")
            logger.info(f"     - 权重: {factor['weight']}")
            logger.info(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")

        # 打印排除因子信息
        try:
            # 调试信息：查看final_study最佳trial的所有user_attrs
            logger.info(f"调试：final_study最佳trial的所有user_attrs: {final_study.best_trial.user_attrs}")
            
            best_filter_conditions = final_study.best_trial.user_attrs.get('filter_conditions', [])
            logger.info(f"调试：从final_study获取到的best_filter_conditions: {best_filter_conditions}")
            
            if best_filter_conditions:
                logger.info("🚫 排除因子:")
                for i, condition in enumerate(best_filter_conditions):
                    logger.info(f"  {i + 1}. {condition['factor']} {condition['operator']} {condition['value']}")
            else:
                logger.info("🚫 排除因子: 无")
        except Exception as filter_e:
            logger.warning(f"获取排除因子信息时出错: {filter_e}")
            logger.info("\n🚫 排除因子: 无法获取")

    except Exception as e:
        logger.error(f"创建最终研究时出错: {e}")
        raise e

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
    
    # 🚨 内存监控：记录优化开始时的内存状态
    logger.info("开始多阶段优化，记录初始内存状态:")
    log_memory_stats()

    # 预处理阶段：生成所有可能的排除因子条件
    logger.info("\n===== 预处理阶段：生成所有可能的排除因子条件 =====")
    all_filter_conditions = _prepare_all_filter_conditions(df, enable_filter_opt)

    # 第一阶段：专注因子组合探索
    first_stage_study, first_stage_combinations = _run_first_stage_optimization(
        df, factors, num_factors, args, max_combinations, all_filter_conditions
    )

    # 获取第一阶段结果，包括TOP 10组合
    first_stage_best_params, first_stage_best_value, _, top_combinations_with_params = _get_first_stage_results(
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
        first_stage_study,
        first_stage_best_params,
        first_stage_best_value,
        first_stage_combinations,
        top_combinations_with_params,
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
        all_filter_conditions,
    )

    return factors, all_combinations, final_study
