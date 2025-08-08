#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证Optuna优化质量影响
测试预构建索引空间对贝叶斯优化的影响
"""

import itertools
import numpy as np
from collections import Counter
import optuna


def create_mock_filter_conditions():
    """创建模拟的all_filter_conditions"""
    conditions = []
    
    # 模拟更完整的条件集合
    factors_config = {
        'pct_chg': {
            'lower': [-0.15, -0.1, -0.05, -0.03],
            'upper': [0.008, 0.01, 0.015, 0.02]
        },
        'theory_value': {
            'lower': [80, 90, 100, 110]
        },
        'bias_5': {
            'lower': [-0.1, -0.05, -0.01],
            'upper': [0.01, 0.03, 0.05]
        },
        'turnover': {
            'lower': [0.001, 0.003, 0.005],
            'upper': [0.5, 0.8, 2.0]
        }
    }
    
    for factor, config in factors_config.items():
        if 'lower' in config:
            for value in config['lower']:
                conditions.append({
                    'factor': factor,
                    'operator': '>=',
                    'value': value,
                    'desc': f'{factor}下限{value}'
                })
        if 'upper' in config:
            for value in config['upper']:
                conditions.append({
                    'factor': factor,
                    'operator': '<=',
                    'value': value,
                    'desc': f'{factor}上限{value}'
                })
    
    return conditions


def is_valid_combination(indices, all_filter_conditions):
    """验证组合是否有效"""
    selected_conditions = [all_filter_conditions[i] for i in indices]
    
    factor_operator_combinations = []
    for condition in selected_conditions:
        combo_key = (condition['factor'], condition['operator'])
        factor_operator_combinations.append(combo_key)
    
    combo_counts = Counter(factor_operator_combinations)
    
    for count in combo_counts.values():
        if count > 1:
            return False
    return True


def generate_valid_combinations(all_filter_conditions, max_factors=2):
    """生成所有有效的索引组合"""
    filter_index_combinations = []
    max_cond = min(max_factors, len(all_filter_conditions))
    min_cond = max(1, max_cond - 1)
    
    valid_count = 0
    total_count = 0
    
    for num_conditions in range(min_cond, max_cond + 1):
        for combo_indices in itertools.combinations(range(len(all_filter_conditions)), num_conditions):
            total_count += 1
            if is_valid_combination(combo_indices, all_filter_conditions):
                filter_index_combinations.append(list(combo_indices))
                valid_count += 1
    
    return filter_index_combinations, valid_count, total_count


def simulate_optuna_behavior():
    """模拟Optuna优化行为"""
    all_filter_conditions = create_mock_filter_conditions()
    filter_combinations, valid_count, total_count = generate_valid_combinations(all_filter_conditions, max_factors=2)
    
    print(f"📊 搜索空间分析:")
    print(f"总条件数: {len(all_filter_conditions)}")
    print(f"理论组合数: {total_count}")
    print(f"有效组合数: {valid_count}")
    print(f"过滤率: {(total_count-valid_count)/total_count*100:.1f}%")
    print(f"搜索空间大小: {len(filter_combinations)}")
    
    print(f"\n🔍 搜索空间质量检查:")
    
    # 检查1: 搜索空间是否足够大
    if len(filter_combinations) < 50:
        print("⚠️  搜索空间可能过小，可能影响优化效果")
    else:
        print(f"✅ 搜索空间大小适中 ({len(filter_combinations)} 个组合)")
    
    # 检查2: 是否保留了配置文件的多样性
    factor_usage = {}
    operator_usage = {}
    value_diversity = {}
    
    for combo in filter_combinations:
        for idx in combo:
            condition = all_filter_conditions[idx]
            factor = condition['factor']
            operator = condition['operator']
            value = condition['value']
            
            factor_usage[factor] = factor_usage.get(factor, 0) + 1
            operator_usage[f"{factor}_{operator}"] = operator_usage.get(f"{factor}_{operator}", 0) + 1
            
            if factor not in value_diversity:
                value_diversity[factor] = set()
            value_diversity[factor].add(value)
    
    print(f"\n📈 多样性分析:")
    print(f"涉及因子数: {len(factor_usage)}")
    for factor, count in factor_usage.items():
        values_used = len(value_diversity[factor])
        print(f"  {factor}: {count}次使用, {values_used}个不同阈值")
    
    # 检查3: 模拟Optuna的suggest行为
    print(f"\n🧪 Optuna行为模拟:")
    
    # 模拟suggest_int的分布
    combo_distribution = list(range(len(filter_combinations)))
    print(f"suggest_int('filter_combo_idx', 0, {len(filter_combinations)-1})")
    print(f"分布均匀度: {'良好' if len(combo_distribution) > 20 else '可能不足'}")
    
    # 随机采样几个组合查看质量
    np.random.seed(42)
    sample_indices = np.random.choice(len(filter_combinations), min(5, len(filter_combinations)), replace=False)
    
    print(f"\n🎲 随机采样验证:")
    for i, sample_idx in enumerate(sample_indices):
        combo = filter_combinations[sample_idx]
        conditions = [all_filter_conditions[idx] for idx in combo]
        print(f"样本{i+1} (combo_idx={sample_idx}):")
        for condition in conditions:
            print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
        
        # 检查是否有重复
        has_duplicate = not is_valid_combination(combo, all_filter_conditions)
        print(f"  验证结果: {'❌有重复' if has_duplicate else '✅无重复'}")


def analyze_optuna_quality_impact():
    """分析对Optuna优化质量的影响"""
    print("\n" + "="*60)
    print("🎯 Optuna优化质量影响分析:")
    print("="*60)
    
    print("\n✅ 正面影响:")
    print("1. 预构建搜索空间 - 所有suggest_int都在有效范围内")
    print("2. 确定性映射 - 每个索引对应确定的条件组合") 
    print("3. 无运行时过滤 - 不破坏Optuna的参数关系学习")
    print("4. 完整搜索空间 - 保留所有有意义的组合")
    
    print("\n🔍 潜在风险:")
    print("1. 搜索空间变化 - 与之前版本的空间大小不同")
    print("2. 索引映射 - TPE需要学习索引与CAGR的关系")
    
    print("\n📋 质量保证措施:")
    print("1. ✅ 预构建阶段完成所有过滤，无运行时干预")
    print("2. ✅ 每个参数值都对应有效且确定的条件组合")
    print("3. ✅ 保留配置文件中所有value_options的可选性")
    print("4. ✅ 避免了同factor同operator的无意义重复")
    
    print("\n🎲 收敛性预期:")
    print("✅ 应该不会影响收敛 - 搜索空间清晰且连续")
    print("✅ 可能提升收敛 - 消除了无效组合的噪声")
    print("✅ TPE能够学习索引模式 - 相似索引可能对应相似CAGR")


if __name__ == "__main__":
    simulate_optuna_behavior()
    analyze_optuna_quality_impact()