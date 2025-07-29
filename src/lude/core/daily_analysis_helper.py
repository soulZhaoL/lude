#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日分析助手模块

内嵌到CAGR计算器中的每日可选债分析功能
避免复杂的路径导入问题
"""

from lude.utils.logger import optimization_logger as logger

def analyze_daily_candidates_inline(df, filter_conditions, hold_num, start_date, end_date, verbose=True):
    """
    内联版每日可选债分析
    
    直接集成到CAGR计算器中使用，避免导入路径问题
    """
    
    # 数据筛选 - 按日期范围
    df_filtered = df[(df.index.get_level_values('trade_date') >= start_date) &
                     (df.index.get_level_values('trade_date') <= end_date)].copy()
    
    # 初始化过滤器
    df_filtered['filter'] = False
    
    # 应用基础过滤条件
    df_filtered.loc[df_filtered.list_days <= 3, 'filter'] = True  # 排除新债
    df_filtered.loc[df_filtered.is_call.isin(['已公告强赎', '公告到期赎回', '公告实施强赎',
                                              '公告提示强赎', '已满足强赎条件']), 'filter'] = True  # 排除赎回状态
    
    # 应用动态过滤条件（简化实现，排除因子功能已移除）
    if filter_conditions and verbose:
        logger.warning("⚠️ 排除因子功能已移除，跳过动态过滤条件")
    
    # 获取所有交易日
    all_trading_days = sorted(df_filtered.index.get_level_values('trade_date').unique())
    total_trading_days = len(all_trading_days)
    
    if verbose:
        logger.info(f"📊 分析期间: {start_date} 至 {end_date}")
        logger.info(f"📊 总交易日数: {total_trading_days}")
        logger.info(f"📊 需要持仓数: {hold_num}")
    
    # 分析每日情况
    daily_stats = []
    
    days_with_no_candidates = 0
    days_with_insufficient_candidates = 0  
    days_with_sufficient_candidates = 0
    
    candidate_counts = []
    sample_problem_days = []  # 记录问题日期样例
    
    for trade_date in all_trading_days:
        # 获取当日数据
        daily_data = df_filtered[df_filtered.index.get_level_values('trade_date') == trade_date]
        
        # 统计各种情况
        total_bonds_today = len(daily_data)
        filtered_out_bonds = len(daily_data[daily_data['filter'] == True])
        available_candidates = len(daily_data[daily_data['filter'] == False])
        
        candidate_counts.append(available_candidates)
        
        # 分类
        if available_candidates == 0:
            days_with_no_candidates += 1
            status = "无可选债"
            if len(sample_problem_days) < 5:  # 记录前5个样例
                sample_problem_days.append({
                    'date': trade_date,
                    'type': 'no_candidates',
                    'total': total_bonds_today,
                    'filtered': filtered_out_bonds,
                    'available': available_candidates
                })
        elif available_candidates < hold_num:
            days_with_insufficient_candidates += 1
            status = f"候选不足({available_candidates}<{hold_num})"
            if len([d for d in sample_problem_days if d['type'] == 'insufficient']) < 5:
                sample_problem_days.append({
                    'date': trade_date,
                    'type': 'insufficient',
                    'total': total_bonds_today,
                    'filtered': filtered_out_bonds,
                    'available': available_candidates
                })
        else:
            days_with_sufficient_candidates += 1
            status = f"候选充足({available_candidates}>={hold_num})"
        
        # 记录详细信息
        daily_stats.append({
            'trade_date': trade_date,
            'total_bonds': total_bonds_today,
            'filtered_out': filtered_out_bonds,
            'available_candidates': available_candidates,
            'status': status,
            'can_trade': available_candidates >= hold_num
        })
    
    # 计算统计指标
    import numpy as np
    
    coverage_ratio = days_with_sufficient_candidates / total_trading_days
    avg_candidates = np.mean(candidate_counts)
    median_candidates = np.median(candidate_counts)
    
    if verbose:
        logger.info(f"\n{'='*70}")
        logger.info(f"🔍 每日可选债深度分析结果:")
        logger.info(f"{'='*70}")
        logger.info(f"📊 交易日分类统计:")
        logger.info(f"  ❌ 完全无可选债: {days_with_no_candidates:3d} 天 ({days_with_no_candidates/total_trading_days*100:5.1f}%)")
        logger.info(f"  ⚠️  候选债不足:   {days_with_insufficient_candidates:3d} 天 ({days_with_insufficient_candidates/total_trading_days*100:5.1f}%)")
        logger.info(f"  ✅ 候选债充足:   {days_with_sufficient_candidates:3d} 天 ({days_with_sufficient_candidates/total_trading_days*100:5.1f}%)")
        logger.info("")
        logger.info(f"📈 关键指标:")
        logger.info(f"  ✅ 真实可交易覆盖率: {coverage_ratio*100:5.1f}% ({days_with_sufficient_candidates}/{total_trading_days})")
        logger.info(f"     (修正逻辑: 统计有充足候选债的交易日)")
        logger.info(f"  📊 平均每日候选数:   {avg_candidates:5.1f} 只")
        logger.info(f"  📊 候选数中位数:     {median_candidates:5.1f} 只")
        logger.info(f"  📊 候选数范围:       {min(candidate_counts)} - {max(candidate_counts)} 只")
        logger.info("")
        
        # 显示问题日期样例
        no_candidate_samples = [d for d in sample_problem_days if d['type'] == 'no_candidates']
        insufficient_samples = [d for d in sample_problem_days if d['type'] == 'insufficient']
        
        if no_candidate_samples:
            logger.info(f"🔍 完全无候选债的日期样例 (共{days_with_no_candidates}天):")
            for day in no_candidate_samples:
                logger.info(f"  {day['date']}: {day['total']}只债 → {day['filtered']}只被过滤 → {day['available']}只可选")
            if days_with_no_candidates > len(no_candidate_samples):
                logger.info(f"  ... 还有{days_with_no_candidates - len(no_candidate_samples)}天类似情况")
            logger.info("")
        
        if insufficient_samples:
            logger.info(f"🔍 候选不足的日期样例 (共{days_with_insufficient_candidates}天):")
            for day in insufficient_samples:
                logger.info(f"  {day['date']}: {day['total']}只债 → {day['filtered']}只被过滤 → {day['available']}只可选 (需要{hold_num}只)")
            if days_with_insufficient_candidates > len(insufficient_samples):
                logger.info(f"  ... 还有{days_with_insufficient_candidates - len(insufficient_samples)}天类似情况")
            logger.info("")
        
        # 诊断建议
        logger.info(f"💡 诊断建议:")
        total_problematic = days_with_no_candidates + days_with_insufficient_candidates
        
        if coverage_ratio < 0.1:
            logger.warning(f"  🚨 严重过拟合: 可交易覆盖率仅{coverage_ratio*100:.1f}%，请大幅放宽过滤条件")
        elif coverage_ratio < 0.3:
            logger.warning(f"  ⚠️  中度过拟合: 可交易覆盖率{coverage_ratio*100:.1f}%，建议适当放宽过滤条件") 
        elif coverage_ratio < 0.7:
            logger.info(f"  ⚡ 轻度过拟合: 可交易覆盖率{coverage_ratio*100:.1f}%，可考虑微调过滤条件")
        else:
            logger.info(f"  ✅ 覆盖率良好: {coverage_ratio*100:.1f}%，过滤条件基本合理")
        
        no_candidate_ratio = days_with_no_candidates / total_trading_days
        if no_candidate_ratio > 0.5:
            logger.warning(f"  🔴 {no_candidate_ratio*100:.1f}%的天数完全无候选债，过滤条件过于严格")
        elif no_candidate_ratio > 0.2:
            logger.info(f"  🟡 {no_candidate_ratio*100:.1f}%的天数无候选债，需要注意")
        
        if avg_candidates < hold_num * 1.5:
            logger.warning(f"  📉 平均候选数({avg_candidates:.1f})接近持仓需求({hold_num})，选择余地不足")
        
        logger.info(f"{'='*70}")
    
    # 构建结果
    result = {
        'total_trading_days': total_trading_days,
        'days_with_no_candidates': days_with_no_candidates,
        'days_with_insufficient_candidates': days_with_insufficient_candidates,
        'days_with_sufficient_candidates': days_with_sufficient_candidates,
        'coverage_ratio': coverage_ratio,
        'avg_candidates': avg_candidates,
        'median_candidates': median_candidates,
        'max_candidates': max(candidate_counts),
        'min_candidates': min(candidate_counts),
        'daily_stats': daily_stats,
        'candidate_counts': candidate_counts,
        'sample_problem_days': sample_problem_days
    }
    
    return result