#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多阶段优化策略模块
实现多阶段优化的核心逻辑
"""

import itertools
import os
import sys

import numpy as np
import optuna

from optuna_search.new_test.cagr_calculator import calculate_bonds_cagr
from optuna_search.new_test.common_utils import RESULTS_DIR  # 导入结果目录常量


def multistage_optimization(df, factors, num_factors, args, max_combinations=50000):
    """多阶段优化策略
    
    第一阶段：广泛探索不同的因子组合
    第二阶段：聚焦于最佳因子组合，优化权重和排序方向
    
    Args:
        df: 数据框
        factors: 因子列表
        num_factors: 因子数量
        args: 参数
        max_combinations: 最大组合数量
        
    Returns:
        factors: 因子列表
        combinations: 所有探索过的因子组合
        final_study: 最终的优化研究
    """
    print(f"执行多阶段优化策略...")

    # 生成所有可能的组合
    all_combinations = []
    for combo in itertools.combinations(range(len(factors)), num_factors):
        all_combinations.append(tuple(sorted(combo)))

    # 如果组合数量过多，随机采样
    if len(all_combinations) > max_combinations:
        np.random.seed(args.seed)
        indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
        all_combinations = [all_combinations[i] for i in indices]

    print(f"生成了 {len(all_combinations)} 个因子组合")

    # 将索引组合转换为实际因子组合
    first_stage_combinations = []
    for combo in all_combinations:
        factor_combo = tuple(factors[i] for i in combo)
        first_stage_combinations.append(factor_combo)

    # 第一阶段：探索不同的因子组合
    print("\n===== 第一阶段：探索因子组合 =====")

    # 创建第一阶段研究
    first_stage_study_name = f"first_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
    # 将数据库文件放在结果目录下
    db_path = os.path.join(RESULTS_DIR, f"{first_stage_study_name}.db")
    storage_name = f"sqlite:///{db_path}"

    try:
        # 尝试加载已有的研究
        first_stage_study = optuna.load_study(study_name=first_stage_study_name, storage=storage_name)
        print(f"加载已有的第一阶段研究，已完成 {len(first_stage_study.trials)} 次试验")
    except:
        # 创建新的研究
        first_stage_study = optuna.create_study(
            study_name=first_stage_study_name,
            storage=storage_name,
            direction="maximize",
            sampler=optuna.samplers.RandomSampler(seed=args.seed),
            load_if_exists=True
        )
        print("创建新的第一阶段研究")

    # 定义第一阶段目标函数
    def first_stage_objective(trial):
        # 选择因子组合
        combination_idx = trial.suggest_int("combination_idx", 0, len(first_stage_combinations) - 1)
        combination = first_stage_combinations[combination_idx]

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
            )

            # 保存rank_factors到trial
            trial.set_user_attr("rank_factors", rank_factors)

            return cagr
        except Exception as e:
            print(f"计算CAGR时出错: {e}")
            raise optuna.exceptions.TrialPruned()

    # 执行第一阶段优化
    n_trials_first_stage = min(args.n_trials // 2, 1000)  # 第一阶段使用一半的试验次数，最多1000次

    # 降低并行度，避免竞争条件
    adjusted_n_jobs = max(1, min(args.n_jobs // 2, 5))  # 降低并行度，最多5个并行任务

    try:
        first_stage_study.optimize(
            first_stage_objective,
            n_trials=n_trials_first_stage,
            n_jobs=adjusted_n_jobs,
            gc_after_trial=True
        )
    except KeyboardInterrupt:
        print("用户中断了第一阶段优化")
    except Exception as e:
        print(f"第一阶段优化出错: {e}")

    # 检查第一阶段是否有结果
    if len(first_stage_study.trials) == 0:
        print("第一阶段没有完成任何试验，无法继续")
        return factors, first_stage_combinations, first_stage_study

    # 获取第一阶段最佳结果
    first_stage_best_params = first_stage_study.best_params
    first_stage_best_value = first_stage_study.best_value

    print(f"\n第一阶段最佳CAGR: {first_stage_best_value:.6f}")

    # 提取最佳因子组合
    if 'combination_idx' in first_stage_best_params:
        best_combination_idx = first_stage_best_params['combination_idx']
        best_combination = first_stage_combinations[best_combination_idx]

        print(f"第一阶段最佳因子组合 (CAGR: {first_stage_best_value:.6f}):")
        for i, factor in enumerate(best_combination):
            weight_param = f'factor{i}_weight'
            asc_param = f'factor{i}_ascending'

            weight = first_stage_best_params.get(weight_param, 1)
            ascending = first_stage_best_params.get(asc_param, True)

            direction = "升序" if ascending else "降序"
            print(f"  {i + 1}. {factor}")
            print(f"     - 权重: {weight}")
            print(f"     - 排序方向: {direction}")
    else:
        print("无法获取第一阶段最佳因子组合")
        return factors, first_stage_combinations, first_stage_study

    # 第二阶段：聚焦于最佳因子组合周围
    print("\n===== 第二阶段：优化权重和排序方向 =====")

    # 创建第二阶段研究
    second_stage_study_name = f"second_stage_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
    # 将数据库文件放在结果目录下
    db_path = os.path.join(RESULTS_DIR, f"{second_stage_study_name}.db")
    second_storage_name = f"sqlite:///{db_path}"

    try:
        # 尝试加载已有的研究
        second_stage_study = optuna.load_study(study_name=second_stage_study_name, storage=second_storage_name)
        print(f"加载已有的第二阶段研究，已完成 {len(second_stage_study.trials)} 次试验")
    except:
        # 创建新的研究
        second_stage_study = optuna.create_study(
            study_name=second_stage_study_name,
            storage=second_storage_name,
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=args.seed),
            load_if_exists=True
        )
        print("创建新的第二阶段研究")

    # 生成第二阶段的因子组合
    # 策略：从最佳组合开始，替换1-2个因子生成新组合
    second_stage_combinations = []

    # 添加第一阶段最佳组合
    if 'combination_idx' in first_stage_best_params:
        best_combination_idx = first_stage_best_params['combination_idx']
        best_combination = first_stage_combinations[best_combination_idx]
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

    print(f"第二阶段将探索 {len(second_stage_combinations)} 个因子组合")

    # 将第一阶段的最佳组合添加到第二阶段组合中(如果不存在)
    if len(first_stage_study.trials) > 0 and first_stage_study.best_trial and 'combination_idx' in first_stage_best_params:
        # 获取第一阶段最佳组合的因子索引
        combination_idx = first_stage_best_params['combination_idx']
        if combination_idx < len(first_stage_combinations):
            first_best_combination = first_stage_combinations[combination_idx]

            # 检查这个组合是否已经在第二阶段组合中
            if first_best_combination not in second_stage_combinations:
                # 如果不在，将其添加到第二阶段组合列表的开头
                second_stage_combinations.insert(0, first_best_combination)

            # 创建一个新的参数集合，使用相同的因子权重和排序方向，但新的combination_idx
            new_params = {}
            first_best_combination_idx = second_stage_combinations.index(first_best_combination)
            new_params['combination_idx'] = first_best_combination_idx

            # 复制所有因子参数
            for i in range(num_factors):
                weight_param = f'factor{i}_weight'
                asc_param = f'factor{i}_ascending'
                if weight_param in first_stage_best_params:
                    new_params[weight_param] = first_stage_best_params[weight_param]
                if asc_param in first_stage_best_params:
                    new_params[asc_param] = first_stage_best_params[asc_param]

            # 将这个参数组合添加到第二阶段研究中
            try:
                # 创建分布字典
                distributions = {}
                # 为每个参数创建适当的分布
                distributions['combination_idx'] = optuna.distributions.IntDistribution(0,
                                                                                        len(second_stage_combinations) - 1)

                # 为因子权重和排序方向添加分布
                for i in range(num_factors):
                    weight_param = f'factor{i}_weight'
                    asc_param = f'factor{i}_ascending'
                    distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
                    distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

                # 使用固定的trial_id，避免并行冲突
                trial = optuna.trial.create_trial(
                    params=new_params,
                    distributions=distributions,
                    value=first_stage_best_value
                )
                second_stage_study.add_trial(trial)
                print("成功将第一阶段最佳参数添加到第二阶段研究中")
            except Exception as e:
                print(f"添加第一阶段最佳参数到第二阶段时出错: {e}")
                print("继续执行第二阶段...")

    # 定义第二阶段目标函数
    def second_stage_objective(trial):
        # 选择因子组合
        combination_idx = trial.suggest_int("combination_idx", 0, len(second_stage_combinations) - 1)
        combination = second_stage_combinations[combination_idx]

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
            )

            # 保存rank_factors到trial
            trial.set_user_attr("rank_factors", rank_factors)

            return cagr
        except Exception as e:
            print(f"计算CAGR时出错: {e}")
            raise optuna.exceptions.TrialPruned()

    # 执行第二阶段优化
    n_trials_second_stage = args.n_trials - n_trials_first_stage

    try:
        second_stage_study.optimize(
            second_stage_objective,
            n_trials=n_trials_second_stage,
            n_jobs=adjusted_n_jobs,
            gc_after_trial=True
        )
    except KeyboardInterrupt:
        print("用户中断了第二阶段优化")
    except optuna.exceptions.TrialPruned as e:
        print(f"第二阶段优化中有试验被剪枝: {e}")
    except optuna.exceptions.DuplicatedStudyError as e:
        print(f"第二阶段优化中出现重复研究错误: {e}")
    except Exception as e:
        print(f"第二阶段优化出错: {e}")

    # 创建最终研究，合并两个阶段的结果
    final_study_name = f"final_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
    # 将数据库文件放在结果目录下
    db_path = os.path.join(RESULTS_DIR, f"{final_study_name}.db")
    final_storage_name = f"sqlite:///{db_path}"

    try:
        # 尝试加载已有的研究
        final_study = optuna.load_study(study_name=final_study_name, storage=final_storage_name)
        print(f"加载已有的最终研究，已完成 {len(final_study.trials)} 次试验")
    except:
        # 创建新的研究
        final_study = optuna.create_study(
            study_name=final_study_name,
            storage=final_storage_name,
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=args.seed),
            load_if_exists=True
        )
        print("创建新的最终研究")

    # 比较两个阶段的结果，取最好的
    second_stage_best_value = second_stage_study.best_value if len(second_stage_study.trials) > 0 else -float('inf')

    # 计算差异，用于判断是否真的有提升
    value_diff = second_stage_best_value - first_stage_best_value

    # 如果差异极小（小于0.0001），视为相等，使用第二阶段结果（可能更稳定）
    if abs(value_diff) < 0.0001:
        print(f"第二阶段结果 ({second_stage_best_value:.6f}) 与第一阶段 ({first_stage_best_value:.6f}) 基本相同")
        print(f"差值: {value_diff:.6f} (小于阈值0.0001)")
        print("使用第二阶段的最佳结果")

        # 使用第二阶段的最佳结果
        use_second_stage = True
    elif value_diff < 0:  # 第一阶段明显更好
        print(f"注意：第一阶段结果 ({first_stage_best_value:.6f}) 优于第二阶段 ({second_stage_best_value:.6f})")
        print(f"提升差值: {-value_diff:.6f}")
        print("使用第一阶段的最佳结果")

        # 将第一阶段的最佳参数作为一个试验点添加到最终研究中
        try:
            # 创建分布字典
            distributions = {}

            # 为每个参数创建适当的分布
            if 'combination_idx' in first_stage_best_params:
                distributions['combination_idx'] = optuna.distributions.IntDistribution(0,
                                                                                        len(first_stage_combinations) - 1)

            # 为因子权重和排序方向添加分布
            for i in range(num_factors):
                weight_param = f'factor{i}_weight'
                asc_param = f'factor{i}_ascending'
                if weight_param in first_stage_best_params:
                    distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
                if asc_param in first_stage_best_params:
                    distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

            trial = optuna.trial.create_trial(
                params=first_stage_best_params,
                distributions=distributions,
                value=first_stage_best_value
            )
            final_study.add_trial(trial)
        except Exception as e:
            print(f"添加第一阶段结果到最终研究时出错: {e}")

        # 返回第一阶段的最佳组合和所有组合
        return factors, list(set(first_stage_combinations + second_stage_combinations)), final_study
    else:
        print(f"第二阶段结果 ({second_stage_best_value:.6f}) 优于第一阶段 ({first_stage_best_value:.6f})")
        print(f"提升差值: {value_diff:.6f}")
        print("使用第二阶段的最佳结果")
        use_second_stage = True

    # 如果使用第二阶段结果，执行下面的代码
    if use_second_stage:
        # 重建best_trial的rank_factors
        best_rank_factors = []
        best_params = second_stage_study.best_params

        try:
            if hasattr(second_stage_study.best_trial,
                       'user_attrs') and 'rank_factors' in second_stage_study.best_trial.user_attrs:
                # 直接从user_attrs获取
                best_rank_factors = second_stage_study.best_trial.user_attrs['rank_factors']
            else:
                # 从参数重建
                combination_idx = best_params['combination_idx']
                combination = second_stage_combinations[combination_idx]

                for i, factor in enumerate(combination):
                    weight_param = f'factor{i}_weight'
                    asc_param = f'factor{i}_ascending'

                    factor_info = {
                        'name': factor,
                        'weight': best_params.get(weight_param, 1),
                        'ascending': best_params.get(asc_param, True)
                    }
                    best_rank_factors.append(factor_info)
                print(f"成功从第二阶段最佳参数中重建了{len(best_rank_factors)}个因子配置")

            # 打印第二阶段最佳因子组合和CAGR
            print(f"\n第二阶段最佳因子组合 (CAGR: {second_stage_best_value:.6f}):")
            for i, factor in enumerate(best_rank_factors):
                print(f"  {i + 1}. {factor['name']}")
                print(f"     - 权重: {factor['weight']}")
                print(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
            print()  # 添加空行

        except Exception as e:
            print(f"重建rank_factors时出错: {e}")

        # 将第二阶段的最佳参数作为一个试验点添加到最终研究中
        try:
            # 创建分布字典
            distributions = {}

            # 为每个参数创建适当的分布
            if 'combination_idx' in best_params:
                distributions['combination_idx'] = optuna.distributions.IntDistribution(0,
                                                                                        len(second_stage_combinations) - 1)

            # 为因子权重和排序方向添加分布
            for i in range(num_factors):
                weight_param = f'factor{i}_weight'
                asc_param = f'factor{i}_ascending'
                if weight_param in best_params:
                    distributions[weight_param] = optuna.distributions.IntDistribution(1, 5)
                if asc_param in best_params:
                    distributions[asc_param] = optuna.distributions.CategoricalDistribution([True, False])

            # 创建trial并添加到研究中
            trial = optuna.trial.create_trial(
                params=best_params,
                distributions=distributions,
                value=second_stage_best_value,
                user_attrs={'rank_factors': best_rank_factors}  # 添加用户属性
            )
            final_study.add_trial(trial)

            # 确保最佳试验的索引被正确更新
            if final_study.best_trial.number != len(
                    final_study.trials) - 1 and final_study.best_value <= second_stage_best_value:
                print("更新最终研究的最佳试验索引")
                # 由于无法直接修改best_trial，我们创建一个新的study并复制所有试验
                temp_study_name = f"temp_{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
                temp_storage_name = f"sqlite:///{temp_study_name}.db"
                try:
                    optuna.delete_study(study_name=temp_study_name, storage=temp_storage_name)
                except:
                    pass

                temp_study = optuna.create_study(
                    study_name=temp_study_name,
                    storage=temp_storage_name,
                    direction="maximize",
                    sampler=optuna.samplers.TPESampler(seed=args.seed)
                )

                # 复制所有试验到新研究
                for t in final_study.trials:
                    try:
                        attrs = t.user_attrs if hasattr(t, 'user_attrs') else {}
                        temp_trial = optuna.trial.create_trial(
                            params=t.params,
                            distributions={k: v for k, v in distributions.items() if k in t.params},
                            value=t.value,
                            user_attrs=attrs
                        )
                        temp_study.add_trial(temp_trial)
                    except Exception as e:
                        print(f"复制试验时出错: {e}")

                # 使用新研究替代旧研究
                final_study = temp_study
                print(f"最终研究现在包含 {len(final_study.trials)} 个试验，最佳值: {final_study.best_value:.6f}")

                # 验证最佳试验是否包含rank_factors
                if hasattr(final_study.best_trial,
                           'user_attrs') and 'rank_factors' in final_study.best_trial.user_attrs:
                    print("最终研究的最佳试验已包含因子配置")
                else:
                    print("警告: 最终研究的最佳试验没有包含因子配置")
                    # 强制添加因子配置
                    for t in final_study.trials:
                        if t.value == final_study.best_value:
                            if not hasattr(t, 'user_attrs') or 'rank_factors' not in t.user_attrs:
                                t._user_attrs['rank_factors'] = best_rank_factors
                                print("已强制添加因子配置到最佳试验")
                            break
        except Exception as e:
            print(f"添加第二阶段结果到最终研究时出错: {e}")
            # 直接在返回的final_study上添加属性，确保能被optimization_engine.py获取到
            if not hasattr(final_study, 'best_rank_factors'):
                setattr(final_study, 'best_rank_factors', best_rank_factors)
                print("已直接添加最佳因子配置到最终研究对象")

    # 直接在返回的final_study上添加属性，确保一定能被optimization_engine.py获取到
    if use_second_stage and best_rank_factors:
        if not hasattr(final_study, 'best_rank_factors'):
            setattr(final_study, 'best_rank_factors', best_rank_factors)
            print("已直接添加第二阶段最佳因子配置到最终研究对象")

    # 返回所有探索过的因子组合
    all_combinations = list(set(first_stage_combinations + second_stage_combinations))
    return factors, all_combinations, final_study


def objective(trial, df, factors, factor_combinations, args):
    """优化目标函数
    
    Args:
        trial: optuna trial对象
        df: 数据框
        factors: 因子列表
        factor_combinations: 因子组合列表
        args: 参数
        
    Returns:
        cagr: 年化收益率
    """
    # 选择因子组合
    combination_idx = trial.suggest_int("combination_idx", 0, len(factor_combinations) - 1)
    combination_indices = factor_combinations[combination_idx]

    # 将索引转换为实际因子
    combination = [factors[i] for i in combination_indices] if isinstance(combination_indices[0],
                                                                          int) else combination_indices

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
        )

        # 保存rank_factors到trial
        trial.set_user_attr("rank_factors", rank_factors)

        return cagr
    except Exception as e:
        print(f"计算CAGR时出错: {e}")
        raise optuna.exceptions.TrialPruned()
