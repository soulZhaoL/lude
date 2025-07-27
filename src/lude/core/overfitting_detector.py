#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
过拟合检测器模块

本模块提供策略过拟合检测功能，支持多维度的过拟合评估。
从cagr_calculator.py中拆分出来，保持职责分离。
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


def check_overfitting(df: pd.DataFrame, 
                     daily_selected_bonds: pd.DataFrame, 
                     res: pd.DataFrame, 
                     hold_num: int, 
                     min_trading_days_ratio: float = 0.95,
                     verbose: bool = True) -> Dict:
    """
    检测策略是否存在过拟合问题
    
    参数：
        df: 原始数据DataFrame（包含所有交易日）
        daily_selected_bonds: 每日选中的可转债DataFrame
        res: 每日收益率DataFrame
        hold_num: 持有数量
        min_trading_days_ratio: 最小交易日占比阈值
        verbose: 是否打印详细检查结果
    
    返回：
        dict: 检查结果字典，包含各维度检查结果和总体判断
    """
    
    # 获取所有交易日
    all_trading_days = df.index.get_level_values('trade_date').unique()
    total_trading_days = len(all_trading_days)
    
    # 1. 交易日覆盖率检查 - 修正：统计有充足候选债的交易日（而非有选中债的交易日）
    days_with_sufficient_candidates = 0
    days_with_no_candidates = 0
    days_with_insufficient_candidates = 0
    
    for trade_date in all_trading_days:
        # 每日未被过滤的候选标的数量
        daily_data = df[df.index.get_level_values('trade_date') == trade_date]
        available_candidates = len(daily_data[daily_data['filter'] == False])
        
        if available_candidates == 0:
            days_with_no_candidates += 1
        elif available_candidates < hold_num:
            days_with_insufficient_candidates += 1
        else:
            days_with_sufficient_candidates += 1
    
    # 真实的交易日覆盖率 = 有充足候选债的交易日数 / 总交易日数
    trading_days_ratio = days_with_sufficient_candidates / total_trading_days if total_trading_days > 0 else 0
    
    # 2. 候选池充足性检查 - 基于上面已计算的数据进行统计
    daily_available_candidates = []
    daily_selected_count = []
    
    for trade_date in all_trading_days:
        # 重新计算每日候选数量用于统计
        daily_data = df[df.index.get_level_values('trade_date') == trade_date]
        available_candidates = len(daily_data[daily_data['filter'] == False])
        daily_available_candidates.append(available_candidates)
        
        # 每日实际选中的标的数量
        if not daily_selected_bonds.empty:
            selected_on_date = len(daily_selected_bonds[daily_selected_bonds['trade_date'] == trade_date])
        else:
            selected_on_date = 0
        daily_selected_count.append(selected_on_date)
    
    avg_candidates = np.mean(daily_available_candidates) if daily_available_candidates else 0
    min_candidates = np.min(daily_available_candidates) if daily_available_candidates else 0
    
    # 使用已计算好的不足天数
    insufficient_days = days_with_insufficient_candidates + days_with_no_candidates
    insufficient_ratio = insufficient_days / total_trading_days if total_trading_days > 0 else 0
    
    # 3. 选股集中度检查
    stock_concentration = {}
    if not daily_selected_bonds.empty and 'code' in daily_selected_bonds.columns:
        # 计算每只标的被选中的频率
        stock_counts = daily_selected_bonds['code'].value_counts()
        total_selections = len(daily_selected_bonds)
        
        # 最高频标的占比
        top_stock_ratio = stock_counts.iloc[0] / total_selections if len(stock_counts) > 0 else 0
        # 前5只标的占比
        top5_ratio = stock_counts.head(5).sum() / total_selections if len(stock_counts) > 0 else 0
        
        stock_concentration = {
            'total_unique_stocks': len(stock_counts),
            'top_stock_ratio': top_stock_ratio,
            'top5_stocks_ratio': top5_ratio,
            'stock_counts': stock_counts.head(10).to_dict()  # 前10只股票的选择次数
        }
    
    # 4. 时间段稳定性检查
    time_stability = {}
    if res is not None and len(res) > 20:  # 至少20个交易日才进行时间段检查
        # 将数据分为4个时间段
        quarter_size = len(res) // 4
        quarters_cagr = []
        
        for i in range(4):
            start_idx = i * quarter_size
            end_idx = (i + 1) * quarter_size if i < 3 else len(res)
            quarter_data = res.iloc[start_idx:end_idx]
            
            if len(quarter_data) > 0:
                quarter_cagr = (quarter_data['daily_return'] + 1).prod() ** (252 / len(quarter_data)) - 1
                quarters_cagr.append(quarter_cagr)
        
        if quarters_cagr:
            time_stability = {
                'quarters_cagr': quarters_cagr,
                'cagr_std': np.std(quarters_cagr),
                'cagr_mean': np.mean(quarters_cagr),
                'cagr_cv': np.std(quarters_cagr) / np.mean(quarters_cagr) if np.mean(quarters_cagr) != 0 else float('inf')
            }
    
    # 5. 极端收益贡献检查 - 增强版
    extreme_return_check = {}
    if res is not None and len(res) > 0:
        daily_returns = res['daily_return']
        total_return = daily_returns.sum()
        
        # 找出收益率最高的前5%交易日
        top_5pct_threshold = daily_returns.quantile(0.95)
        top_5pct_days = daily_returns[daily_returns >= top_5pct_threshold]
        top_days_return = top_5pct_days.sum()
        
        # 额外分析：按排名前5%计算（更准确）
        top_5pct_count_by_rank = max(1, int(len(daily_returns) * 0.05))
        top_days_by_rank = daily_returns.nlargest(top_5pct_count_by_rank)
        top_days_by_rank_return = top_days_by_rank.sum()
        
        # 分析收益分布
        positive_days = len(daily_returns[daily_returns > 0])
        negative_days = len(daily_returns[daily_returns < 0])
        zero_days = len(daily_returns[daily_returns == 0])
        
        extreme_return_check = {
            # 基本统计
            'total_trading_days': len(daily_returns),
            'total_return': total_return,
            'avg_daily_return': daily_returns.mean(),
            'median_daily_return': daily_returns.median(),
            'return_std': daily_returns.std(),
            'max_daily_return': daily_returns.max(),
            'min_daily_return': daily_returns.min(),
            
            # 收益分布
            'positive_days': positive_days,
            'negative_days': negative_days,
            'zero_days': zero_days,
            'positive_ratio': positive_days / len(daily_returns),
            
            # 前5%分析（按分位数）
            'top_5pct_threshold': top_5pct_threshold,
            'top_5pct_days_count': len(top_5pct_days),
            'top_5pct_days_contribution': top_days_return / total_return if total_return != 0 else 0,
            'top_5pct_returns': top_5pct_days.tolist(),
            
            # 前5%分析（按排名）
            'top_5pct_count_by_rank': top_5pct_count_by_rank,
            'top_5pct_by_rank_contribution': top_days_by_rank_return / total_return if total_return != 0 else 0,
            'top_5pct_by_rank_returns': top_days_by_rank.tolist(),
            
            # 极端值分析
            'top_1_day_contribution': daily_returns.max() / total_return if total_return != 0 else 0,
            'top_3_days_contribution': daily_returns.nlargest(3).sum() / total_return if total_return != 0 else 0,
        }
    
    # 汇总检查结果
    check_results = {
        # 1. 交易日覆盖率 - 修正后的逻辑
        'trading_days_coverage': {
            'total_trading_days': total_trading_days,
            'days_with_sufficient_candidates': days_with_sufficient_candidates,
            'days_with_insufficient_candidates': days_with_insufficient_candidates,
            'days_with_no_candidates': days_with_no_candidates,
            'coverage_ratio': trading_days_ratio,
            'passed': trading_days_ratio >= min_trading_days_ratio
        },
        
        # 2. 候选池充足性
        'candidate_pool_sufficiency': {
            'avg_daily_candidates': avg_candidates,
            'min_daily_candidates': min_candidates,
            'insufficient_days_count': insufficient_days,
            'insufficient_days_ratio': insufficient_ratio,
            'passed': insufficient_ratio <= 0.1  # 不足候选池的天数不超过10%
        },
        
        # 3. 选股集中度
        'stock_concentration': stock_concentration,
        
        # 4. 时间段稳定性
        'time_stability': time_stability,
        
        # 5. 极端收益贡献
        'extreme_return_contribution': extreme_return_check
    }
    
    # 总体判断
    overfitting_detected = False
    warning_messages = []
    
    if not check_results['trading_days_coverage']['passed']:
        overfitting_detected = True
        warning_messages.append(f"交易日覆盖率过低: {trading_days_ratio:.2%} < {min_trading_days_ratio:.2%}")
    
    if not check_results['candidate_pool_sufficiency']['passed']:
        overfitting_detected = True
        warning_messages.append(f"候选池不足天数过多: {insufficient_ratio:.2%} > 10%")
    
    if stock_concentration and stock_concentration.get('top_stock_ratio', 0) > 0.5:
        overfitting_detected = True
        warning_messages.append(f"选股过度集中: 最高频标的占比 {stock_concentration['top_stock_ratio']:.2%} > 50%")
    
    if time_stability and time_stability.get('cagr_cv', 0) > 2.0:
        overfitting_detected = True
        warning_messages.append(f"时间段表现不稳定: 变异系数 {time_stability['cagr_cv']:.2f} > 2.0")
    
    if extreme_return_check and extreme_return_check.get('top_5pct_days_contribution', 0) > 0.9:
        overfitting_detected = True
        warning_messages.append(f"极端收益贡献过高: 前5%交易日贡献 {extreme_return_check['top_5pct_days_contribution']:.2%} > 90%")
    
    check_results['overall'] = {
        'overfitting_detected': overfitting_detected,
        'warning_messages': warning_messages,
        'passed': not overfitting_detected
    }
    
    # 打印详细检查结果（如果启用verbose）
    if verbose:
        print_overfitting_report(check_results)
    
    return check_results


def print_overfitting_report(check_results: Dict) -> None:
    """
    打印过拟合检查报告
    
    参数：
        check_results: 检查结果字典
    """
    print("=" * 60)
    print("过拟合检查结果:")
    print("=" * 60)
    
    # 1. 交易日覆盖率 - 修正后的显示
    coverage = check_results['trading_days_coverage']
    print(f"1. 交易日覆盖率: {coverage['coverage_ratio']:.2%} ({coverage['days_with_sufficient_candidates']}/{coverage['total_trading_days']})")
    print(f"   有充足候选债: {coverage['days_with_sufficient_candidates']} 天")
    print(f"   候选债不足:   {coverage['days_with_insufficient_candidates']} 天")
    print(f"   完全无候选债: {coverage['days_with_no_candidates']} 天")
    print(f"   状态: {'✓ 通过' if coverage['passed'] else '✗ 未通过'}")
    
    # 2. 候选池充足性
    pool = check_results['candidate_pool_sufficiency']
    print(f"2. 候选池充足性:")
    print(f"   平均每日候选数: {pool['avg_daily_candidates']:.1f}")
    print(f"   最少单日候选数: {pool['min_daily_candidates']}")
    print(f"   候选不足天数: {pool['insufficient_days_count']} ({pool['insufficient_days_ratio']:.2%})")
    print(f"   状态: {'✓ 通过' if pool['passed'] else '✗ 未通过'}")
    
    # 3. 选股集中度
    if check_results['stock_concentration']:
        conc = check_results['stock_concentration']
        print(f"3. 选股集中度:")
        print(f"   总选择标的数: {conc['total_unique_stocks']}")
        print(f"   最高频标的占比: {conc['top_stock_ratio']:.2%}")
        print(f"   前5标的占比: {conc['top5_stocks_ratio']:.2%}")
    else:
        print("3. 选股集中度: 无数据")
    
    # 4. 时间段稳定性
    if check_results['time_stability']:
        stab = check_results['time_stability']
        print(f"4. 时间段稳定性:")
        print(f"   各季度CAGR: {[f'{x:.2%}' for x in stab['quarters_cagr']]}")
        print(f"   变异系数: {stab['cagr_cv']:.2f}")
    else:
        print("4. 时间段稳定性: 数据不足")
    
    # 5. 极端收益贡献 - 详细版
    if check_results['extreme_return_contribution']:
        extreme = check_results['extreme_return_contribution']
        print(f"5. 极端收益贡献:")
        print(f"   总交易日数: {extreme['total_trading_days']}")
        print(f"   平均日收益: {extreme['avg_daily_return']:.4f} ({extreme['avg_daily_return']*100:.2f}%)")
        print(f"   收益中位数: {extreme['median_daily_return']:.4f} ({extreme['median_daily_return']*100:.2f}%)")
        print(f"   最大日收益: {extreme['max_daily_return']:.4f} ({extreme['max_daily_return']*100:.2f}%)")
        print(f"   最小日收益: {extreme['min_daily_return']:.4f} ({extreme['min_daily_return']*100:.2f}%)")
        print(f"   总收益: {extreme['total_return']:.4f} ({extreme['total_return']*100:.2f}%)")
        print(f"   ")
        print(f"   收益分布: 正收益{extreme['positive_days']}天, 负收益{extreme['negative_days']}天, 零收益{extreme['zero_days']}天")
        print(f"   ")
        print(f"   前5%分析 (按分位数95%):")
        print(f"     阈值: {extreme['top_5pct_threshold']:.4f} ({extreme['top_5pct_threshold']*100:.2f}%)")
        print(f"     天数: {extreme['top_5pct_days_count']} 天")
        print(f"     贡献: {extreme['top_5pct_days_contribution']:.2%}")
        print(f"   ")
        print(f"   前5%分析 (按排名):")
        print(f"     天数: {extreme['top_5pct_count_by_rank']} 天")
        print(f"     贡献: {extreme['top_5pct_by_rank_contribution']:.2%}")
        print(f"   ")
        print(f"   极端分析:")
        print(f"     最高1天贡献: {extreme['top_1_day_contribution']:.2%}")
        print(f"     最高3天贡献: {extreme['top_3_days_contribution']:.2%}")
        
        # 显示具体的前5%收益值
        if len(extreme.get('top_5pct_by_rank_returns', [])) > 0:
            print(f"   ")
            print(f"   前5%交易日收益明细:")
            for i, ret in enumerate(extreme['top_5pct_by_rank_returns'][:10]):  # 最多显示10个
                print(f"     第{i+1}名: {ret:.4f} ({ret*100:.2f}%)")
    else:
        print("5. 极端收益贡献: 无数据")
    
    # 总体结果
    overall = check_results['overall']
    print("=" * 60)
    print(f"总体检查结果: {'✓ 通过' if overall['passed'] else '✗ 检测到过拟合'}")
    if overall['warning_messages']:
        print("警告信息:")
        for msg in overall['warning_messages']:
            print(f"  - {msg}")
    print("=" * 60)


def get_overfitting_penalty_value() -> float:
    """
    获取过拟合惩罚值
    
    返回极小的负值，确保过拟合的策略在优化过程中被排除
    
    Returns:
        float: 极小的惩罚值
    """
    return -999.0  # 返回极小的负值作为惩罚


def is_strategy_overfitted(df: pd.DataFrame, 
                          daily_selected_bonds: pd.DataFrame, 
                          res: pd.DataFrame, 
                          hold_num: int, 
                          min_trading_days_ratio: float = 0.95,
                          verbose: bool = False) -> bool:
    """
    简化的过拟合检测函数，只返回是否过拟合的布尔值
    
    参数：
        df: 原始数据DataFrame
        daily_selected_bonds: 每日选中的可转债DataFrame  
        res: 每日收益率DataFrame
        hold_num: 持有数量
        min_trading_days_ratio: 最小交易日占比阈值
        verbose: 是否打印详细信息
    
    Returns:
        bool: True表示检测到过拟合，False表示未检测到过拟合
    """
    check_results = check_overfitting(df, daily_selected_bonds, res, hold_num, 
                                     min_trading_days_ratio, verbose)
    return check_results['overall']['overfitting_detected']