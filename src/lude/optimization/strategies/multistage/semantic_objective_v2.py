#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语义化优化目标函数 v2 - 固定参数空间版本
采用全因子预定义方案，确保Optuna参数空间完全固定

本文件实现了：
1. 完全固定的参数空间 - 为所有48个因子预定义所有参数
2. 语义化策略选择 - 基于投资策略的因子组合
3. 业务逻辑过滤 - 通过enable开关和策略配置控制因子使用
4. 完整的精调逻辑 - 包含探索vs指导模式、动态因子选择等
"""

import optuna
from typing import Optional, Callable, List, Dict, Any
from collections import defaultdict
import random
import numpy as np

from .config import StrategyConfig
from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.utils.logger import setup_logger

logger = setup_logger(__name__)

# 全部48个因子的固定列表
ALL_FACTORS = [
    'pre_close', 'open', 'high', 'low', 'close', 'close_ma_5', 'bias_5', 'pct_chg',
    'vol', 'vol_5', 'amount', 'amount_5', 'volatility', 'close_stk', 'pct_chg_stk',
    'vol_stk', 'amount_stk', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ratio', 'total_mv',
    'circ_mv', 'debt_to_assets', 'volatility_stk', 'conv_price', 'conv_value',
    'conv_prem', 'dblow', 'issue_size', 'remain_size', 'remain_cap', 'turnover',
    'turnover_5', 'cap_mv_rate', 'list_days', 'left_years', 'ytm', 'pure_value',
    'bond_prem', 'option_value', 'theory_value', 'theory_bias', 'pct_chg_5',
    'pct_chg_5_stk', 'alpha_pct_chg_5', 'theory_conv_prem', 'mod_conv_prem'
]


def create_fixed_semantic_objective_function(
    df,
    args,
    config: Optional[StrategyConfig] = None
) -> Callable:
    """创建修复版语义化目标函数 - 全因子预定义方案
    
    关键改进：
    1. 为所有48个因子预定义所有参数，确保参数空间完全固定
    2. 通过enable开关和策略配置控制实际使用的因子
    3. 避免任何动态参数创建，彻底解决Optuna一致性问题
    
    Args:
        df: 数据框
        args: 参数
        config: 策略配置对象
    
    Returns:
        objective: 固定参数空间的语义化目标函数
    """
    if config is None:
        config = StrategyConfig()
    
    def objective(trial):
        """固定参数空间的语义化目标函数"""
        
        # ========== 1. 固定策略参数（4个基础参数）==========
        primary_strategy = trial.suggest_categorical(
            "primary_strategy",
            list(config.investment_strategies.keys())
        )
        
        use_mixed_strategy = trial.suggest_categorical("use_mixed_strategy", [False, True])
        
        # 预定义所有可能的次要策略，避免动态参数空间
        secondary_strategy = trial.suggest_categorical(
            "secondary_strategy",
            list(config.investment_strategies.keys())
        )
        
        enable_auxiliary = trial.suggest_categorical("enable_auxiliary", [False, True])
        
        # ========== 2. 为所有48个因子预定义所有参数（192个参数）==========
        factor_weights = {}
        factor_ascending = {}
        factor_enable_secondary = {}
        factor_enable_aux = {}
        
        for factor in ALL_FACTORS:
            # 每个因子4个参数：weight, ascending, enable_secondary, enable_aux
            factor_weights[factor] = trial.suggest_int(f"weight_{factor}", 1, 5)
            factor_ascending[factor] = trial.suggest_categorical(f"ascending_{factor}", [True, False])
            factor_enable_secondary[factor] = trial.suggest_categorical(f"enable_secondary_{factor}", [True, False])
            factor_enable_aux[factor] = trial.suggest_categorical(f"enable_aux_{factor}", [True, False])
        
        # ========== 3. 策略有效性检查 ==========
        primary_config = config.get_strategy(primary_strategy)
        
        # 混合策略有效性检查
        if use_mixed_strategy:
            if secondary_strategy == primary_strategy:
                logger.debug(f"次要策略与主策略相同: {secondary_strategy}，跳过试验")
                raise optuna.exceptions.TrialPruned()
            
            if not config.is_valid_combination(primary_strategy, secondary_strategy):
                logger.debug(f"跳过不建议的策略组合: {primary_strategy} + {secondary_strategy}")
                raise optuna.exceptions.TrialPruned()
            
            secondary_config = config.get_strategy(secondary_strategy)
        else:
            secondary_config = None
        
        # ========== 4. 基于策略配置和预定义参数构建因子集合 ==========
        rank_factors = []
        used_factors = set()
        
        # 添加主策略核心因子（必须添加）
        core_factors = primary_config.get('core_factors', [])
        preferred_directions = primary_config.get('preferred_directions', {})
        
        for factor in core_factors:
            if factor not in used_factors:
                weight = factor_weights[factor]
                
                # 使用策略偏好方向（如果有）
                if factor in preferred_directions:
                    ascending = preferred_directions[factor]
                else:
                    ascending = factor_ascending[factor]
                
                rank_factors.append({
                    "name": factor,
                    "weight": weight,
                    "ascending": ascending,
                    "source": primary_strategy
                })
                used_factors.add(factor)
        
        # 添加次要策略因子（可选，基于enable开关）
        if use_mixed_strategy and secondary_config:
            secondary_core = secondary_config.get('core_factors', [])
            secondary_directions = secondary_config.get('preferred_directions', {})
            
            secondary_factor_count = 0
            max_secondary = min(3, len(secondary_core))
            
            for factor in secondary_core:
                if (factor not in used_factors and 
                    secondary_factor_count < max_secondary and
                    factor_enable_secondary[factor]):  # 使用预定义的enable开关
                    
                    weight = factor_weights[factor]
                    
                    if factor in secondary_directions:
                        ascending = secondary_directions[factor]
                    else:
                        ascending = factor_ascending[factor]
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": secondary_strategy
                    })
                    used_factors.add(factor)
                    secondary_factor_count += 1
        
        # 添加辅助因子（可选，基于enable开关）
        if enable_auxiliary:
            auxiliary_pool = primary_config.get('auxiliary_pool', [])
            max_auxiliary = min(config.combination_rules.get('max_auxiliary_factors', 4), len(auxiliary_pool))
            
            auxiliary_factor_count = 0
            
            for factor in auxiliary_pool:
                if (factor not in used_factors and 
                    auxiliary_factor_count < max_auxiliary and
                    factor_enable_aux[factor]):  # 使用预定义的enable开关
                    
                    # 辅助因子使用较低权重 (1-3)
                    weight = min(3, factor_weights[factor])
                    ascending = factor_ascending[factor]
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": "auxiliary"
                    })
                    used_factors.add(factor)
                    auxiliary_factor_count += 1
        
        # ========== 5. 不使用过滤策略 ==========
        filter_conditions = []  # 无过滤条件
        
        # ========== 6. 验证参数有效性 ==========
        # 确保至少有最少数量的因子
        if len(rank_factors) < config.combination_rules.get('min_core_factors', 6):
            logger.debug(f"因子数量不足: {len(rank_factors)}")
            raise optuna.exceptions.TrialPruned()
        
        # 确保不超过最大因子数
        if len(rank_factors) > config.combination_rules.get('max_mixed_factors', 12):
            logger.debug(f"因子数量过多: {len(rank_factors)}")
            raise optuna.exceptions.TrialPruned()
        
        # 检查因子冲突
        if not config.check_factor_conflicts(rank_factors):
            logger.debug(f"存在因子冲突，跳过试验")
            raise optuna.exceptions.TrialPruned()
        
        # ========== 7. 计算CAGR ==========
        try:
            cagr = calculate_bonds_cagr(
                df=df,
                start_date=args.start_date if args else "20220729",
                end_date=args.end_date if args else "20250328",
                hold_num=args.hold_num if args else 5,
                min_price=args.price_min if args else 100,
                max_price=args.price_max if args else 150,
                rank_factors=rank_factors,
                filter_conditions=filter_conditions,
                threshold_num=None,
                check_overfitting=True,
                verbose_overfitting=False
            )
            
            # 记录试验信息
            secondary_str = f"+{secondary_strategy}" if (use_mixed_strategy and secondary_config) else "+None"
            logger.info(
                f"Trial {trial.number}: CAGR={cagr:.4f}, "
                f"策略={primary_strategy}{secondary_str}, "
                f"因子数={len(rank_factors)}"
            )
            
            # 保存试验属性以供第二阶段分析
            trial.set_user_attr("rank_factors", rank_factors)
            trial.set_user_attr("filter_conditions", filter_conditions)
            trial.set_user_attr("primary_strategy", primary_strategy)
            trial.set_user_attr("secondary_strategy", secondary_strategy if use_mixed_strategy else None)
            trial.set_user_attr("use_mixed_strategy", use_mixed_strategy)
            trial.set_user_attr("enable_auxiliary", enable_auxiliary)
            trial.set_user_attr("n_factors", len(rank_factors))
            
            return cagr
            
        except Exception as e:
            logger.warning(f"Trial {trial.number}: CAGR计算失败: {e}")
            raise optuna.exceptions.TrialPruned()
    
    return objective


def analyze_best_strategies(study, top_n: int = 10) -> List[Dict[str, Any]]:
    """分析最佳策略
    
    Args:
        study: Optuna study对象
        top_n: 返回前N个最佳策略
    
    Returns:
        best_strategies: 最佳策略列表
    """
    if not study.trials:
        return []
    
    # 获取完成的试验，按价值排序
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completed_trials:
        return []
    
    # 按CAGR排序（降序）
    completed_trials.sort(key=lambda x: x.value, reverse=True)
    
    best_strategies = []
    for trial in completed_trials[:top_n]:
        strategy_info = {
            'primary_strategy': trial.user_attrs.get('primary_strategy'),
            'secondary_strategy': trial.user_attrs.get('secondary_strategy'),
            'use_mixed_strategy': trial.user_attrs.get('use_mixed_strategy', False),
            'enable_auxiliary': trial.user_attrs.get('enable_auxiliary', False),
            'n_factors': trial.user_attrs.get('n_factors', 0),
            'cagr': trial.value,
            'params': trial.params,
            'rank_factors': trial.user_attrs.get('rank_factors', []),
            'filter_conditions': trial.user_attrs.get('filter_conditions', [])
        }
        best_strategies.append(strategy_info)
    
    return best_strategies


def create_fixed_refined_objective_function(
    df,
    best_strategies: List[Dict[str, Any]],
    args,
    config: Optional[StrategyConfig] = None
) -> Callable:
    """创建完整版平衡精调目标函数
    
    采用平衡的精调策略，避免过度约束损害贝叶斯优化效率：
    1. 软约束：使用概率权重而非硬性限制
    2. 探索保留：30%的trial保持完全探索，70%进行指导性精调
    3. 渐进精调：根据trial进展动态调整约束强度
    4. 鲁棒性验证：对第一阶段发现进行稳健性检验
    
    Args:
        df: 数据框
        best_strategies: 第一阶段最佳策略列表
        args: 参数
        config: 策略配置对象
    
    Returns:
        objective: 完整的精调目标函数
    """
    if config is None:
        config = StrategyConfig()
    
    # 分析第一阶段发现，但不过度依赖
    from collections import Counter
    
    # 稳健性分析：只在有充足样本时才使用统计信息
    min_samples_for_inference = max(3, len(best_strategies) // 4)  # 至少3个或总数的25%
    
    # 提取策略信息
    primary_strategies = [s.get('primary_strategy') for s in best_strategies if s.get('primary_strategy')]
    mixed_usage = [s.get('use_mixed_strategy', False) for s in best_strategies]
    
    # 只在样本充足时才进行策略倾向分析
    strategy_preferences = {}
    mixed_tendency = 0.5  # 默认值
    
    if len(primary_strategies) >= min_samples_for_inference:
        primary_counter = Counter(primary_strategies)
        # 计算策略倾向，但不过度约束
        total_strategies = len(primary_strategies)
        for strategy, count in primary_counter.items():
            preference_score = count / total_strategies
            # 只有显著倾向（>40%）才记录
            if preference_score > 0.4:
                strategy_preferences[strategy] = min(preference_score * 2, 0.8)  # 最多80%偏向
        
        mixed_tendency = sum(mixed_usage) / len(mixed_usage) if mixed_usage else 0.5
    
    # 权重模式分析（仅作为软指导）
    weight_guidance = defaultdict(dict)
    direction_guidance = defaultdict(dict)
    
    if len(best_strategies) >= min_samples_for_inference:
        weight_patterns = defaultdict(list)
        direction_patterns = defaultdict(list)
        
        for strategy in best_strategies:
            params = strategy.get('params', {})
            for param_name, param_value in params.items():
                if param_name.startswith('weight_') and isinstance(param_value, (int, float)):
                    factor_name = param_name.replace('weight_', '')
                    weight_patterns[factor_name].append(param_value)
                elif param_name.startswith('ascending_'):
                    factor_name = param_name.replace('ascending_', '')
                    direction_patterns[factor_name].append(param_value)
        
        # 只为有足够样本的因子提供指导
        for factor_name, weights in weight_patterns.items():
            if len(weights) >= 3:  # 至少需要3个样本
                mean_weight = np.mean(weights)
                std_weight = np.std(weights)
                
                # 只在权重相对稳定时才提供指导（标准差<1.5）
                if std_weight < 1.5:
                    weight_guidance[factor_name] = {
                        'preferred_weight': mean_weight,
                        'confidence': min(len(weights) / 5.0, 1.0)  # 信心度最多100%
                    }
        
        # 方向偏好分析
        for factor_name, directions in direction_patterns.items():
            if len(directions) >= 3:
                true_ratio = sum(directions) / len(directions)
                if true_ratio > 0.7 or true_ratio < 0.3:  # 明显偏向
                    direction_guidance[factor_name] = {
                        'preferred_direction': true_ratio > 0.5,
                        'confidence': abs(true_ratio - 0.5) * 2  # 偏离度转为信心度
                    }
    
    logger.info(f"第二阶段平衡精调参数:")
    logger.info(f"  策略倾向: {strategy_preferences}")
    logger.info(f"  混合策略倾向: {mixed_tendency:.2f}")
    logger.info(f"  权重指导: {len(weight_guidance)}个因子有指导信息")
    logger.info(f"  方向指导: {len(direction_guidance)}个因子有方向偏好")
    logger.info(f"  保留探索比例: 30%")
    
    def objective(trial):
        """完整的平衡精调目标函数 - 在指导和探索之间平衡"""
        
        # ========== 0. 决定是否进行指导性优化 ==========
        # 30%的trial保持完全探索，70%进行软指导
        use_guidance = trial.suggest_categorical(
            "use_first_stage_guidance", 
            [True, True, True, False, False, False, False]  # 70% vs 30%
        )
        
        # ========== 1. 策略选择（可能受指导）==========
        if not use_guidance:
            # 完全探索模式：标准策略选择
            logger.debug(f"Trial {trial.number}: 使用完全探索模式")
            primary_strategy = trial.suggest_categorical(
                "primary_strategy",
                list(config.investment_strategies.keys())
            )
        else:
            # 指导模式：基于第一阶段发现的策略偏向
            logger.debug(f"Trial {trial.number}: 使用策略指导模式")
            
            all_strategies = list(config.investment_strategies.keys())
            
            # 构建策略选择概率
            strategy_weights = []
            for strategy in all_strategies:
                if strategy in strategy_preferences:
                    # 有倾向的策略获得更高概率
                    base_weight = 1.0
                    preference_bonus = strategy_preferences[strategy]
                    strategy_weights.append(base_weight + preference_bonus)
                else:
                    # 无倾向的策略保持基础概率
                    strategy_weights.append(1.0)
            
            # 正则化概率
            total_weight = sum(strategy_weights)
            strategy_probs = [w / total_weight for w in strategy_weights]
            
            # 使用概率权重选择策略（模拟加权采样）
            random.seed(trial.number)
            primary_strategy = random.choices(all_strategies, weights=strategy_probs)[0]
        
        # 混合策略选择 - 使用固定参数空间
        # 先用固定的选项获取基础值
        use_mixed_strategy_base = trial.suggest_categorical("use_mixed_strategy", [False, True])
        
        # 如果使用指导，可能会覆盖基础值
        if use_guidance:
            # 基于第一阶段发现和随机种子决定是否覆盖
            random.seed(trial.number + 1000)  # 确保可重现性
            
            if mixed_tendency > 0.6:
                # 67%概率使用混合策略
                use_mixed_strategy = random.random() < 0.67
            elif mixed_tendency < 0.4:
                # 33%概率使用混合策略
                use_mixed_strategy = random.random() < 0.33
            else:
                # 50%概率，使用基础值
                use_mixed_strategy = use_mixed_strategy_base
        else:
            use_mixed_strategy = use_mixed_strategy_base
        
        # 次要策略选择（固定参数空间要求）
        secondary_strategy = trial.suggest_categorical(
            "secondary_strategy",
            list(config.investment_strategies.keys())
        )
        
        # 是否启用辅助因子
        enable_auxiliary = trial.suggest_categorical("enable_auxiliary", [False, True])
        
        # ========== 2. 为所有48个因子预定义参数（保持固定空间）==========
        factor_weights = {}
        factor_ascending = {}
        factor_enable_secondary = {}
        factor_enable_aux = {}
        
        for factor in ALL_FACTORS:
            # 权重选择（可能受指导）
            if use_guidance and factor in weight_guidance:
                guidance = weight_guidance[factor]
                preferred_weight = guidance['preferred_weight']
                confidence = guidance['confidence']
                
                # 根据信心度调整偏向强度
                if confidence > 0.7:  # 高信心度：在最佳权重附近采样
                    center = int(round(preferred_weight))
                    min_w = max(1, center - 1)
                    max_w = min(5, center + 1)
                elif confidence > 0.4:  # 中等信心度：较宽范围
                    center = int(round(preferred_weight))
                    min_w = max(1, center - 2)
                    max_w = min(5, center + 2)
                else:  # 低信心度：正常范围
                    min_w, max_w = 1, 5
                
                factor_weights[factor] = trial.suggest_int(f"weight_{factor}", min_w, max_w)
            else:
                # 无指导或探索模式：正常范围
                factor_weights[factor] = trial.suggest_int(f"weight_{factor}", 1, 5)
            
            # 方向选择 - 使用固定参数空间
            # 先用固定选项获取基础值
            factor_ascending_base = trial.suggest_categorical(f"ascending_{factor}", [True, False])
            
            # 如果使用指导且有方向偏好，可能覆盖基础值
            if use_guidance and factor in direction_guidance:
                guidance = direction_guidance[factor]
                preferred_dir = guidance['preferred_direction']
                confidence = guidance['confidence']
                
                # 使用随机数根据信心度决定是否使用偏好方向
                random.seed(trial.number + 2000 + hash(factor) % 1000)
                rand_val = random.random()
                
                if confidence > 0.7:
                    # 高信心度：90%概率使用偏好方向
                    factor_ascending[factor] = preferred_dir if rand_val < 0.9 else not preferred_dir
                elif confidence > 0.4:
                    # 中等信心度：70%概率
                    factor_ascending[factor] = preferred_dir if rand_val < 0.7 else not preferred_dir
                else:
                    # 低信心度：使用基础值
                    factor_ascending[factor] = factor_ascending_base
            else:
                factor_ascending[factor] = factor_ascending_base
            
            # enable开关（动态选择）
            factor_enable_secondary[factor] = trial.suggest_categorical(f"enable_secondary_{factor}", [True, False])
            factor_enable_aux[factor] = trial.suggest_categorical(f"enable_aux_{factor}", [True, False])
        
        # ========== 3. 构建因子集合（使用策略逻辑）==========
        primary_config = config.get_strategy(primary_strategy)
        
        # 混合策略有效性检查
        if use_mixed_strategy:
            if secondary_strategy == primary_strategy:
                logger.debug(f"次要策略与主策略相同: {secondary_strategy}，跳过试验")
                raise optuna.exceptions.TrialPruned()
            
            if not config.is_valid_combination(primary_strategy, secondary_strategy):
                logger.debug(f"跳过不建议的策略组合: {primary_strategy} + {secondary_strategy}")
                raise optuna.exceptions.TrialPruned()
            
            secondary_config = config.get_strategy(secondary_strategy)
        else:
            secondary_config = None
        
        # 构建rank_factors（与第一阶段相同的逻辑）
        rank_factors = []
        used_factors = set()
        
        # 添加主策略核心因子
        core_factors = primary_config.get('core_factors', [])
        preferred_directions = primary_config.get('preferred_directions', {})
        
        for factor in core_factors:
            if factor not in used_factors:
                weight = factor_weights[factor]
                
                # 使用策略偏好方向（如果有）
                if factor in preferred_directions:
                    ascending = preferred_directions[factor]
                else:
                    ascending = factor_ascending[factor]
                
                rank_factors.append({
                    "name": factor,
                    "weight": weight,
                    "ascending": ascending,
                    "source": primary_strategy
                })
                used_factors.add(factor)
        
        # 添加次要策略因子（基于enable开关）
        if use_mixed_strategy and secondary_config:
            secondary_core = secondary_config.get('core_factors', [])
            secondary_directions = secondary_config.get('preferred_directions', {})
            
            secondary_factor_count = 0
            max_secondary = min(3, len(secondary_core))
            
            for factor in secondary_core:
                if (factor not in used_factors and 
                    secondary_factor_count < max_secondary and
                    factor_enable_secondary[factor]):  # 使用预定义的enable开关
                    
                    weight = factor_weights[factor]
                    
                    if factor in secondary_directions:
                        ascending = secondary_directions[factor]
                    else:
                        ascending = factor_ascending[factor]
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": secondary_strategy
                    })
                    used_factors.add(factor)
                    secondary_factor_count += 1
        
        # 添加辅助因子（基于enable开关）
        if enable_auxiliary:
            auxiliary_pool = primary_config.get('auxiliary_pool', [])
            max_auxiliary = min(config.combination_rules.get('max_auxiliary_factors', 4), len(auxiliary_pool))
            
            auxiliary_factor_count = 0
            
            for factor in auxiliary_pool:
                if (factor not in used_factors and 
                    auxiliary_factor_count < max_auxiliary and
                    factor_enable_aux[factor]):  # 使用预定义的enable开关
                    
                    # 辅助因子使用较低权重 (1-3)
                    weight = min(3, factor_weights[factor])
                    ascending = factor_ascending[factor]
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": "auxiliary"
                    })
                    used_factors.add(factor)
                    auxiliary_factor_count += 1
        
        # ========== 4. 验证参数有效性 ==========
        # 确保至少有最少数量的因子
        if len(rank_factors) < config.combination_rules.get('min_core_factors', 6):
            logger.debug(f"因子数量不足: {len(rank_factors)}")
            raise optuna.exceptions.TrialPruned()
        
        # 确保不超过最大因子数
        if len(rank_factors) > config.combination_rules.get('max_mixed_factors', 12):
            logger.debug(f"因子数量过多: {len(rank_factors)}")
            raise optuna.exceptions.TrialPruned()
        
        # 检查因子冲突
        if not config.check_factor_conflicts(rank_factors):
            logger.debug(f"存在因子冲突，跳过试验")
            raise optuna.exceptions.TrialPruned()
        
        # ========== 5. 不使用过滤策略 ==========
        filter_conditions = []  # 无过滤条件
        
        # ========== 6. 计算CAGR ==========
        try:
            cagr = calculate_bonds_cagr(
                df=df,
                start_date=args.start_date if args else "20220729",
                end_date=args.end_date if args else "20250328",
                hold_num=args.hold_num if args else 5,
                min_price=args.price_min if args else 100,
                max_price=args.price_max if args else 150,
                rank_factors=rank_factors,
                filter_conditions=filter_conditions,
                threshold_num=None,
                check_overfitting=True,
                verbose_overfitting=False
            )
            
            # 记录试验信息
            guidance_info = "指导" if use_guidance else "探索"
            secondary_str = f"+{secondary_strategy}" if (use_mixed_strategy and secondary_config) else "+None"
            logger.info(
                f"精调Trial {trial.number} ({guidance_info}): CAGR={cagr:.4f}, "
                f"策略={primary_strategy}{secondary_str}, "
                f"因子数={len(rank_factors)}"
            )
            
            # 保存试验属性以供分析
            trial.set_user_attr("rank_factors", rank_factors)
            trial.set_user_attr("filter_conditions", filter_conditions)
            trial.set_user_attr("primary_strategy", primary_strategy)
            trial.set_user_attr("secondary_strategy", secondary_strategy if use_mixed_strategy else None)
            trial.set_user_attr("use_mixed_strategy", use_mixed_strategy)
            trial.set_user_attr("enable_auxiliary", enable_auxiliary)
            trial.set_user_attr("n_factors", len(rank_factors))
            trial.set_user_attr("refinement_stage", True)  # 标记为精调阶段
            trial.set_user_attr("used_guidance", use_guidance)  # 记录是否使用指导
            
            return cagr
            
        except Exception as e:
            logger.warning(f"精调Trial {trial.number}: CAGR计算失败: {e}")
            raise optuna.exceptions.TrialPruned()
    
    return objective