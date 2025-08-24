"""
语义化目标函数实现 v1 - 动态参数空间版本
将无意义的索引选择转换为有业务含义的投资策略选择

注意：此版本使用动态参数空间，存在Optuna兼容性问题
推荐使用v2版本（固定参数空间）
"""

import optuna
from typing import Dict, List, Any, Optional, Callable
from .config import StrategyConfig
from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.utils.logger import setup_logger

logger = setup_logger(__name__)


def create_semantic_objective_function(
    df,
    args,
    config: Optional[StrategyConfig] = None
) -> Callable:
    """创建语义化的目标函数
    
    Args:
        df: 数据框
        args: 参数
        config: 策略配置对象
    
    Returns:
        objective: 目标函数
    """
    if config is None:
        config = StrategyConfig()
    
    def objective(trial):
        """语义化目标函数"""
        
        # ========== 1. 选择投资策略 ==========
        primary_strategy = trial.suggest_categorical(
            "primary_strategy",
            list(config.investment_strategies.keys())
        )
        
        primary_config = config.get_strategy(primary_strategy)
        logger.debug(f"选择主策略: {primary_strategy} - {primary_config.get('name', '')}")
        
        # ========== 2. 决定是否使用混合策略 ==========
        use_mixed_strategy = trial.suggest_categorical("use_mixed_strategy", [False, True])
        
        secondary_strategy = None
        secondary_config = None
        
        if use_mixed_strategy:
            # 使用固定的策略列表，然后检查是否与主策略相同
            all_strategies = list(config.investment_strategies.keys())
            
            secondary_strategy = trial.suggest_categorical(
                "secondary_strategy",
                all_strategies
            )
            
            # 如果与主策略相同，跳过此试验
            if secondary_strategy == primary_strategy:
                logger.debug(f"次要策略与主策略相同: {secondary_strategy}，跳过试验")
                raise optuna.exceptions.TrialPruned()
            
            # 检查策略组合是否有效
            if not config.is_valid_combination(primary_strategy, secondary_strategy):
                logger.debug(f"跳过不建议的策略组合: {primary_strategy} + {secondary_strategy}")
                raise optuna.exceptions.TrialPruned()
            
            secondary_config = config.get_strategy(secondary_strategy)
            logger.debug(f"选择次要策略: {secondary_strategy} - {secondary_config.get('name', '')}")
        
        # ========== 3. 构建打分因子集合 ==========
        rank_factors = []
        used_factors = set()  # 避免重复因子
        
        # 添加主策略核心因子
        core_factors = primary_config.get('core_factors', [])
        weight_range = primary_config.get('weight_range', [1.0, 3.0])
        preferred_directions = primary_config.get('preferred_directions', {})
        
        for factor in core_factors:
            if factor not in used_factors:
                # 使用整数权重参数(1-5)，保持配置范围不受混合比例影响
                weight = trial.suggest_int(
                    f"weight_{factor}",
                    int(weight_range[0]),
                    int(weight_range[1])
                )
                
                # 使用偏好方向或让Optuna选择
                if factor in preferred_directions:
                    ascending = preferred_directions[factor]
                else:
                    ascending = trial.suggest_categorical(
                        f"ascending_{factor}",
                        [True, False]
                    )
                
                rank_factors.append({
                    "name": factor,
                    "weight": weight,
                    "ascending": ascending,
                    "source": primary_strategy
                })
                used_factors.add(factor)
        
        # 添加次要策略因子（如果有）
        if secondary_strategy and secondary_config:
            secondary_core = secondary_config.get('core_factors', [])
            secondary_weight_range = secondary_config.get('weight_range', [1.0, 3.0])
            secondary_directions = secondary_config.get('preferred_directions', {})
            
            # 为所有次要策略因子创建参数（固定参数空间）
            secondary_factor_count = 0
            max_secondary = min(3, len(secondary_core))
            
            for factor in secondary_core:
                if factor not in used_factors and secondary_factor_count < max_secondary:
                    # 使用enable开关控制是否启用此因子
                    enable_factor = trial.suggest_categorical(f"enable_secondary_{factor}", [True, False])
                    
                    if enable_factor:
                        weight = trial.suggest_int(
                            f"weight_{factor}",
                            int(secondary_weight_range[0]),
                            int(secondary_weight_range[1])
                        )
                        
                        if factor in secondary_directions:
                            ascending = secondary_directions[factor]
                        else:
                            ascending = trial.suggest_categorical(
                                f"ascending_{factor}",
                                [True, False]
                            )
                        
                        rank_factors.append({
                            "name": factor,
                            "weight": weight,
                            "ascending": ascending,
                            "source": secondary_strategy
                        })
                        used_factors.add(factor)
                        secondary_factor_count += 1
        
        # ========== 4. 添加辅助因子（可选）==========
        enable_auxiliary = trial.suggest_categorical("enable_auxiliary", [False, True])
        
        if enable_auxiliary:
            auxiliary_pool = primary_config.get('auxiliary_pool', [])
            aux_weight_range = primary_config.get('aux_weight_range', [1, 3])
            max_auxiliary = min(config.combination_rules.get('max_auxiliary_factors', 4), len(auxiliary_pool))
            
            # 为所有辅助因子创建参数（固定参数空间）
            auxiliary_factor_count = 0
            
            for factor in auxiliary_pool:
                if factor not in used_factors and auxiliary_factor_count < max_auxiliary:
                    # 使用enable开关控制是否启用此因子
                    enable_factor = trial.suggest_categorical(f"enable_aux_{factor}", [True, False])
                    
                    if enable_factor:
                        weight = trial.suggest_int(
                            f"aux_weight_{factor}",
                            max(1, int(aux_weight_range[0])),
                            min(3, int(aux_weight_range[1]))
                        )
                        
                        ascending = trial.suggest_categorical(
                            f"aux_ascending_{factor}",
                            [True, False]
                        )
                        
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
                df,
                start_date=args.start_date if args else "20220729",
                end_date=args.end_date if args else "20250328",
                hold_num=args.hold_num if args else 5,
                threshold_num=None,
                min_price=args.price_min if args else 100,
                max_price=args.price_max if args else 150,
                rank_factors=rank_factors,
                filter_conditions=filter_conditions,
                check_overfitting=True,
                verbose_overfitting=False
            )
            
            # 保存试验信息
            trial.set_user_attr("primary_strategy", primary_strategy)
            trial.set_user_attr("secondary_strategy", secondary_strategy)
            trial.set_user_attr("rank_factors", rank_factors)
            trial.set_user_attr("n_factors", len(rank_factors))
            
            logger.info(f"Trial {trial.number}: CAGR={cagr:.4f}, "
                       f"策略={primary_strategy}+{secondary_strategy if secondary_strategy else 'None'}, "
                       f"因子数={len(rank_factors)}")
            
            return cagr
            
        except ValueError as e:
            if "过拟合" in str(e) or "无符合条件" in str(e):
                logger.debug(f"跳过无效参数组合: {e}")
                raise optuna.exceptions.TrialPruned()
            else:
                raise
        except Exception as e:
            import traceback
            logger.error(f"计算CAGR时出现未预期错误: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise optuna.exceptions.TrialPruned()
    
    return objective


def create_refined_objective_function(
    df,
    best_strategies: List[Dict],
    args,
    config: Optional[StrategyConfig] = None
) -> Callable:
    """创建精调阶段的目标函数
    
    采用平衡的精调策略，避免过度约束损害贝叶斯优化效率：
    1. 软约束：使用概率权重而非硬性限制
    2. 探索保留：30%的trial保持完全探索，70%进行指导性精调
    3. 渐进精调：根据trial进展动态调整约束强度
    4. 鲁棒性验证：对第一阶段发现进行稳健性检验
    
    Args:
        df: 数据框
        best_strategies: 第一阶段的最佳策略列表
        args: 参数
        config: 策略配置对象
    
    Returns:
        objective: 平衡的精调目标函数
    """
    if config is None:
        config = StrategyConfig()
    
    # 分析第一阶段的发现，但不过度依赖
    from collections import Counter, defaultdict
    import numpy as np
    
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
    
    if len(best_strategies) >= min_samples_for_inference:
        weight_patterns = defaultdict(list)
        
        for strategy in best_strategies:
            params = strategy.get('params', {})
            for param_name, param_value in params.items():
                if param_name.startswith('weight_') and isinstance(param_value, (int, float)):
                    factor_name = param_name.replace('weight_', '')
                    weight_patterns[factor_name].append(param_value)
        
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
    
    logger.info(f"第二阶段平衡精调参数:")
    logger.info(f"  策略倾向: {strategy_preferences}")
    logger.info(f"  混合策略倾向: {mixed_tendency:.2f}")
    logger.info(f"  权重指导: {len(weight_guidance)}个因子有指导信息")
    logger.info(f"  保留探索比例: 30%")
    
    def objective(trial):
        """平衡的精调目标函数 - 在指导和探索之间平衡"""
        
        # ========== 0. 决定是否进行指导性优化 ==========
        # 30%的trial保持完全探索，70%进行软指导
        use_guidance = trial.suggest_categorical(
            "use_first_stage_guidance", 
            [True, True, True, False, False, False, False]  # 70% vs 30%
        )
        
        # 根据是否使用指导设置不同的策略选择逻辑
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
            
            # ========== 1. 软策略指导：使用概率权重而非硬性限制 ==========
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
            import random
            random.seed(trial.number)
            primary_strategy = random.choices(all_strategies, weights=strategy_probs)[0]
        
        primary_config = config.get_strategy(primary_strategy)
        logger.debug(f"选择主策略: {primary_strategy}")
        
        # ========== 2. 混合策略选择 ==========
        if not use_guidance:
            # 探索模式：标准混合策略选择
            use_mixed_strategy = trial.suggest_categorical("use_mixed_strategy", [False, True])
        else:
            # 指导模式：基于第一阶段发现调整混合策略概率
            if mixed_tendency > 0.6:
                # 混合策略效果好，提高使用概率
                mixed_choices = [True, True, False]  # 67%概率
            elif mixed_tendency < 0.4:
                # 混合策略效果一般，降低使用概率
                mixed_choices = [True, False, False]  # 33%概率
            else:
                # 不确定，保持平衡
                mixed_choices = [True, False]  # 50%概率
            
            use_mixed_strategy = trial.suggest_categorical("use_mixed_strategy", mixed_choices)
        
        secondary_strategy = None
        secondary_config = None
        
        if use_mixed_strategy:
            # 选择次要策略（排除主策略）
            available_secondary = [
                s for s in config.investment_strategies.keys()
                if s != primary_strategy
            ]
            
            if available_secondary:
                secondary_strategy = trial.suggest_categorical(
                    "secondary_strategy",
                    available_secondary
                )
                
                # 验证策略组合有效性
                if not config.is_valid_combination(primary_strategy, secondary_strategy):
                    logger.debug(f"跳过不建议的策略组合: {primary_strategy} + {secondary_strategy}")
                    raise optuna.exceptions.TrialPruned()
                
                secondary_config = config.get_strategy(secondary_strategy)
                logger.debug(f"指导性次策略: {secondary_strategy}")
        
        # ========== 3. 软权重指导与因子选择 ==========
        rank_factors = []
        used_factors = set()
        
        # 3A. 主策略核心因子（保持正常选择机制）
        core_factors = primary_config.get('core_factors', [])
        weight_range = primary_config.get('weight_range', [1, 5])
        preferred_directions = primary_config.get('preferred_directions', {})
        
        for factor in core_factors:
            if factor not in used_factors:
                # 权重选择：探索模式vs指导模式
                if not use_guidance or factor not in weight_guidance:
                    # 探索模式或无指导信息：正常采样
                    weight = trial.suggest_int(
                        f"weight_{factor}",
                        int(weight_range[0]),
                        int(weight_range[1])
                    )
                else:
                    # 指导模式且有权重指导：软指导权重
                    guidance = weight_guidance[factor]
                    preferred_weight = guidance['preferred_weight']
                    confidence = guidance['confidence']
                    
                    # 根据信心度调整偏向强度
                    if confidence > 0.7:  # 高信心度：在最佳权重附近采样
                        center = int(round(preferred_weight))
                        min_w = max(1, center - 1)
                        max_w = min(5, center + 1)
                        weight = trial.suggest_int(f"weight_{factor}", min_w, max_w)
                    elif confidence > 0.4:  # 中等信心度：较宽范围
                        center = int(round(preferred_weight))
                        min_w = max(1, center - 2)
                        max_w = min(5, center + 2)
                        weight = trial.suggest_int(f"weight_{factor}", min_w, max_w)
                    else:  # 低信心度：正常范围
                        weight = trial.suggest_int(
                            f"weight_{factor}",
                            int(weight_range[0]),
                            int(weight_range[1])
                        )
                
                # 方向选择：探索模式vs指导模式
                if not use_guidance or factor not in preferred_directions:
                    # 探索模式或无偏好方向：标准选择
                    ascending = trial.suggest_categorical(
                        f"ascending_{factor}",
                        [True, False]
                    )
                else:
                    # 指导模式且有偏好方向：70%概率使用偏好方向
                    preferred_dir = preferred_directions[factor]
                    ascending = trial.suggest_categorical(
                        f"ascending_{factor}",
                        [preferred_dir, preferred_dir, not preferred_dir]
                    )
                
                rank_factors.append({
                    "name": factor,
                    "weight": weight,
                    "ascending": ascending,
                    "source": primary_strategy
                })
                used_factors.add(factor)
        
        # 3B. 次策略因子（如果有）
        if secondary_strategy and secondary_config:
            secondary_core = secondary_config.get('core_factors', [])
            n_secondary = trial.suggest_int("n_secondary_factors", 2, min(4, len(secondary_core)))
            
            available_secondary_factors = [f for f in secondary_core if f not in used_factors]
            
            if available_secondary_factors:
                import random
                random.seed(trial.number + 2000)
                selected_secondary = random.sample(
                    available_secondary_factors,
                    min(n_secondary, len(available_secondary_factors))
                )
                
                secondary_weight_range = secondary_config.get('weight_range', [1, 3])
                secondary_directions = secondary_config.get('preferred_directions', {})
                
                for factor in selected_secondary:
                    # 次策略因子使用适中的权重范围
                    weight = trial.suggest_int(
                        f"weight_{factor}",
                        int(secondary_weight_range[0]),
                        int(secondary_weight_range[1])
                    )
                    
                    if factor in secondary_directions:
                        ascending = secondary_directions[factor]
                    else:
                        ascending = trial.suggest_categorical(
                            f"ascending_{factor}",
                            [True, False]
                        )
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": secondary_strategy
                    })
                    used_factors.add(factor)
        
        # 3C. 辅助因子可选添加（正常概率）
        enable_auxiliary = trial.suggest_categorical("enable_auxiliary", [False, True])
        
        if enable_auxiliary:
            auxiliary_pool = primary_config.get('auxiliary_pool', [])
            available_aux = [f for f in auxiliary_pool if f not in used_factors]
            
            if available_aux:
                n_auxiliary = trial.suggest_int(
                    "n_auxiliary_factors",
                    1,
                    min(config.combination_rules.get('max_auxiliary_factors', 4), len(available_aux))
                )
                
                import random
                random.seed(trial.number + 3000)
                selected_aux = random.sample(available_aux, min(n_auxiliary, len(available_aux)))
                
                aux_weight_range = primary_config.get('aux_weight_range', [1, 3])
                
                for factor in selected_aux:
                    weight = trial.suggest_int(
                        f"aux_weight_{factor}",
                        max(1, int(aux_weight_range[0])),
                        min(3, int(aux_weight_range[1]))
                    )
                    
                    ascending = trial.suggest_categorical(
                        f"aux_ascending_{factor}",
                        [True, False]
                    )
                    
                    rank_factors.append({
                        "name": factor,
                        "weight": weight,
                        "ascending": ascending,
                        "source": "auxiliary"
                    })
                    used_factors.add(factor)
        
        # ========== 4. 正常参数验证 ==========
        min_factors = config.combination_rules.get('min_core_factors', 6)
        max_factors = config.combination_rules.get('max_mixed_factors', 12)
        
        if len(rank_factors) < min_factors:
            logger.debug(f"因子数量不足: {len(rank_factors)} < {min_factors}")
            raise optuna.exceptions.TrialPruned()
        
        if len(rank_factors) > max_factors:
            logger.debug(f"因子数量过多: {len(rank_factors)} > {max_factors}")
            raise optuna.exceptions.TrialPruned()
        
        # 检查因子冲突
        if not config.check_factor_conflicts(rank_factors):
            logger.debug(f"精调阶段存在因子冲突，跳过试验")
            raise optuna.exceptions.TrialPruned()
        
        # ========== 5. 暂不使用过滤策略 ==========
        filter_conditions = []
        
        # ========== 6. 计算CAGR ==========
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
                filter_conditions=filter_conditions,
                check_overfitting=True,
                verbose_overfitting=False
            )
            
            # 保存试验信息
            trial.set_user_attr("primary_strategy", primary_strategy)
            trial.set_user_attr("secondary_strategy", secondary_strategy)
            trial.set_user_attr("rank_factors", rank_factors)
            trial.set_user_attr("n_factors", len(rank_factors))
            trial.set_user_attr("refinement_stage", True)  # 标记为精调阶段
            trial.set_user_attr("used_guidance", use_guidance)  # 记录是否使用指导
            
            guidance_info = "指导" if use_guidance else "探索"
            logger.info(f"精调Trial {trial.number} ({guidance_info}): CAGR={cagr:.4f}, "
                       f"策略={primary_strategy}+{secondary_strategy if secondary_strategy else 'None'}, "
                       f"因子数={len(rank_factors)}")
            
            return cagr
            
        except ValueError as e:
            if "过拟合" in str(e) or "无符合条件" in str(e):
                logger.debug(f"跳过无效参数组合: {e}")
                raise optuna.exceptions.TrialPruned()
            else:
                raise
        except Exception as e:
            import traceback
            logger.error(f"计算CAGR时出现未预期错误: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise optuna.exceptions.TrialPruned()
    
    return objective


def analyze_best_strategies(study: optuna.Study, top_n: int = 10) -> List[Dict]:
    """分析最佳策略
    
    Args:
        study: Optuna研究对象
        top_n: 取前n个最佳试验
    
    Returns:
        best_strategies: 最佳策略列表
    """
    best_trials = sorted(
        study.trials,
        key=lambda t: t.value if t.value is not None else -float('inf'),
        reverse=True
    )[:top_n]
    
    best_strategies = []
    for trial in best_trials:
        strategy_info = {
            'primary_strategy': trial.user_attrs.get('primary_strategy'),
            'secondary_strategy': trial.user_attrs.get('secondary_strategy'),
            'cagr': trial.value,
            'n_factors': trial.user_attrs.get('n_factors'),
            'params': trial.params
        }
        best_strategies.append(strategy_info)
    
    return best_strategies