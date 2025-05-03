#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化引擎模块
负责执行优化过程的核心逻辑
"""

import optuna
import pandas as pd
import numpy as np
import json
import time
import os
from datetime import datetime

# 导入常量和工具函数
from common_utils import create_sampler, save_optimization_result, RESULTS_DIR

def run_optimization(df, args):
    """运行优化过程
    
    Args:
        df: 数据框
        args: 参数
        
    Returns:
        model_path: 保存的模型路径
    """
    print(f"\n===== 开始优化 =====")
    print(f"策略: {args.strategy}")
    print(f"方法: {args.method}")
    print(f"因子数量: {args.n_factors}")
    print(f"回测日期: {args.start_date} 至 {args.end_date}")
    print(f"价格范围: {args.price_min} - {args.price_max}")
    print(f"持仓数量: {args.hold_num}")
    print(f"并行任务数: {args.n_jobs}")
    print(f"随机种子: {args.seed}")
    
    # 添加自定义因子
    # df = add_custom_factors(df)
    
    # 获取所有可用因子
    factors = [col for col in df.columns if col not in ['date', 'bond_id', 'bond_nm', 'stock_id']]
    print(f"数据中共有 {len(factors)} 个因子")
    
    # 根据策略生成因子组合
    from strategies.factor_strategies import choose_strategy
    factors, factor_combinations = choose_strategy(
        args.strategy, df, factors, args.n_factors, args, max_combinations=50000
    )
    
    # 如果使用多阶段优化策略，执行多阶段优化
    if args.strategy == 'multistage':
        from strategies.multistage_optimizer import multistage_optimization
        factors, factor_combinations, study = multistage_optimization(
            df, factors, args.n_factors, args, max_combinations=50000
        )
    else:
        # 创建研究
        study_name = f"{args.strategy}_{args.method}_{args.n_factors}factors_{args.seed}"
        # 将数据库文件保存到optimization_results目录
        db_path = os.path.join(RESULTS_DIR, f"{study_name}.db")
        storage_name = f"sqlite:///{db_path}"
        
        try:
            # 尝试加载已有的研究
            study = optuna.load_study(study_name=study_name, storage=storage_name)
            print(f"加载已有的研究，已完成 {len(study.trials)} 次试验")
        except:
            # 创建新的研究
            study = optuna.create_study(
                study_name=study_name,
                storage=storage_name,
                direction="maximize",
                sampler=create_sampler(args.method, args.seed),
                load_if_exists=True
            )
            print("创建新的研究")
        
        # 定义目标函数
        from strategies.multistage_optimizer import objective
        
        # 执行优化
        try:
            study.optimize(
                lambda trial: objective(trial, df, factors, factor_combinations, args),
                n_trials=args.n_trials,
                n_jobs=args.n_jobs,
                gc_after_trial=True
            )
        except KeyboardInterrupt:
            print("用户中断了优化")
        except Exception as e:
            print(f"优化过程出错: {e}")
    
    # 打印最佳结果
    if len(study.trials) > 0:
        print(f"\n===== 优化结果 =====")
        print(f"最佳CAGR: {study.best_value:.6f}")
        
        # 提取最佳因子组合
        best_rank_factors = None
        
        # 首先检查study对象本身是否直接保存了best_rank_factors属性（由多阶段优化器设置的备选方案）
        if hasattr(study, 'best_rank_factors'):
            best_rank_factors = study.best_rank_factors
            print("从study对象的属性中获取最佳因子配置")
        # 然后尝试从best_trial的user_attrs中获取
        elif hasattr(study.best_trial, 'user_attrs') and 'rank_factors' in study.best_trial.user_attrs:
            best_rank_factors = study.best_trial.user_attrs['rank_factors']
            print("从best_trial的user_attrs中获取最佳因子配置")
        
        if best_rank_factors:
            print(f"\n最佳因子组合:")
            for i, factor in enumerate(best_rank_factors):
                print(f"  {i+1}. {factor['name']}")
                print(f"     - 权重: {factor['weight']}")
                print(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
        else:
            print("无法获取最佳因子组合详情")
            
            # 尝试从best_trial的参数重建rank_factors（最后的备选方案）
            try:
                if 'combination_idx' in study.best_params:
                    combination_idx = study.best_params['combination_idx']
                    
                    # 根据策略获取正确的组合
                    if args.strategy == 'multistage':
                        from strategies.multistage_optimizer import multistage_optimization
                        # 使用一个很小的dummy函数绕过完整优化过程获取组合
                        def dummy_objective(*args, **kwargs):
                            return 0
                        # 伪造一个study对象防止覆盖原始数据
                        dummy_study = optuna.create_study()
                        # 绕过优化过程直接获取第二阶段组合
                        _, second_stage_combinations, _ = multistage_optimization(
                            df, factors, args.n_factors, args, max_combinations=1
                        )
                        if combination_idx < len(second_stage_combinations):
                            combination = second_stage_combinations[combination_idx]
                        else:
                            print(f"警告: combination_idx={combination_idx}超出组合范围")
                            combination = None
                    else:
                        # 从factor_combinations获取组合
                        if combination_idx < len(factor_combinations):
                            combination_indices = factor_combinations[combination_idx]
                            combination = [factors[i] for i in combination_indices] if isinstance(combination_indices[0], int) else combination_indices
                        else:
                            print(f"警告: combination_idx={combination_idx}超出组合范围")
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
                        
                        print("\n已从参数重建最佳因子组合:")
                        for i, factor in enumerate(best_rank_factors):
                            print(f"  {i+1}. {factor['name']}")
                            print(f"     - 权重: {factor['weight']}")
                            print(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
            except Exception as e:
                print(f"尝试重建最佳因子组合时出错: {e}")
        
        # 保存最佳模型
        model_path = save_optimization_result(study, factors, factor_combinations, args, best_rank_factors)
        
        # 发送优化结果到钉钉
        try:
            from notification.dingtalk_notifier import send_optimization_result_to_dingtalk
            send_optimization_result_to_dingtalk(
                study.best_value, 
                best_rank_factors,
                n_factors=args.n_factors,
                start_date=args.start_date,
                end_date=args.end_date,
                price_range=(args.price_min, args.price_max),
                hold_num=args.hold_num
            )
        except Exception as e:
            print(f"发送优化结果到钉钉时出错: {e}")
        
        return model_path
    else:
        print("没有完成任何试验，无法获取结果")
        return None
