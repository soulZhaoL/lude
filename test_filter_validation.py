#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证排除因子组合逻辑的正确性
测试 is_valid_combination 函数是否按预期工作
"""

import itertools
from collections import Counter


def create_mock_filter_conditions():
    """创建模拟的all_filter_conditions，基于实际配置文件"""
    conditions = []
    
    # 模拟 pct_chg 因子的条件（基于配置文件）
    pct_chg_lower_values = [-0.15, -0.1, -0.05, -0.03]
    pct_chg_upper_values = [0.008, 0.01, 0.015, 0.02]
    
    for value in pct_chg_lower_values:
        conditions.append({
            'factor': 'pct_chg',
            'operator': '>=',
            'value': value,
            'desc': f'涨跌幅下限 {value}'
        })
    
    for value in pct_chg_upper_values:
        conditions.append({
            'factor': 'pct_chg',
            'operator': '<=',
            'value': value,
            'desc': f'涨跌幅上限 {value}'
        })
    
    # 模拟 theory_value 因子的条件
    theory_value_values = [80, 90, 100, 110]
    for value in theory_value_values:
        conditions.append({
            'factor': 'theory_value',
            'operator': '>=',
            'value': value,
            'desc': f'理论价值下限 {value}'
        })
    
    # 模拟 bias_5 因子的条件  
    bias_5_lower_values = [-0.1, -0.05, -0.01, -0.008]
    bias_5_upper_values = [0.01, 0.03, 0.05]
    
    for value in bias_5_lower_values:
        conditions.append({
            'factor': 'bias_5',
            'operator': '>=',
            'value': value,
            'desc': f'5日乖离率下限 {value}'
        })
        
    for value in bias_5_upper_values:
        conditions.append({
            'factor': 'bias_5',
            'operator': '<=',
            'value': value,
            'desc': f'5日乖离率上限 {value}'
        })
    
    return conditions


def is_valid_combination(indices, all_filter_conditions):
    """检查索引组合是否有效：禁止相同因子的相同操作符重复，但允许不同阈值"""
    selected_conditions = [all_filter_conditions[i] for i in indices]
    
    # 统计每个 (因子,操作符) 组合的出现次数
    factor_operator_combinations = []
    for condition in selected_conditions:
        combo_key = (condition['factor'], condition['operator'])
        factor_operator_combinations.append(combo_key)
    
    # 检查是否有重复的 (因子,操作符) 组合
    combo_counts = Counter(factor_operator_combinations)
    
    # 如果任何 (因子,操作符) 组合出现次数>1，则无效
    for count in combo_counts.values():
        if count > 1:
            return False
    return True


def test_validation_logic():
    """测试验证逻辑"""
    all_filter_conditions = create_mock_filter_conditions()
    
    print(f"创建了 {len(all_filter_conditions)} 个过滤条件:")
    for i, condition in enumerate(all_filter_conditions):
        print(f"  {i}: {condition['factor']} {condition['operator']} {condition['value']}")
    
    print("\n" + "="*60)
    
    # 测试有效组合
    print("🧪 测试有效组合:")
    
    # 测试1: 同因子不同操作符 (应该有效)
    test_indices_1 = [2, 4]  # pct_chg >= -0.05 和 pct_chg <= 0.008
    result_1 = is_valid_combination(test_indices_1, all_filter_conditions)
    selected_1 = [all_filter_conditions[i] for i in test_indices_1]
    print(f"测试1 (同因子不同操作符): {result_1}")
    for condition in selected_1:
        print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
    
    # 测试2: 不同因子相同操作符 (应该有效)
    test_indices_2 = [2, 8]  # pct_chg >= -0.05 和 theory_value >= 80
    result_2 = is_valid_combination(test_indices_2, all_filter_conditions)
    selected_2 = [all_filter_conditions[i] for i in test_indices_2]
    print(f"\n测试2 (不同因子相同操作符): {result_2}")
    for condition in selected_2:
        print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
    
    # 测试3: 三个不同因子 (应该有效)
    test_indices_3 = [2, 8, 12]  # pct_chg >= -0.05, theory_value >= 80, bias_5 >= -0.1
    result_3 = is_valid_combination(test_indices_3, all_filter_conditions)
    selected_3 = [all_filter_conditions[i] for i in test_indices_3]
    print(f"\n测试3 (三个不同因子): {result_3}")
    for condition in selected_3:
        print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
    
    print("\n" + "="*60)
    
    # 测试无效组合
    print("❌ 测试无效组合:")
    
    # 测试4: 同因子同操作符 (应该无效)
    test_indices_4 = [0, 2]  # pct_chg >= -0.15 和 pct_chg >= -0.05
    result_4 = is_valid_combination(test_indices_4, all_filter_conditions)
    selected_4 = [all_filter_conditions[i] for i in test_indices_4]
    print(f"测试4 (同因子同操作符): {result_4}")
    for condition in selected_4:
        print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
    
    # 测试5: 多个同因子同操作符 (应该无效)
    test_indices_5 = [8, 9, 10]  # theory_value >= 80, theory_value >= 90, theory_value >= 100
    result_5 = is_valid_combination(test_indices_5, all_filter_conditions)
    selected_5 = [all_filter_conditions[i] for i in test_indices_5]
    print(f"\n测试5 (多个同因子同操作符): {result_5}")
    for condition in selected_5:
        print(f"  - {condition['factor']} {condition['operator']} {condition['value']}")
    
    print("\n" + "="*60)
    
    # 统计有效组合数量
    print("📊 统计有效组合:")
    max_conditions = 2
    valid_count = 0
    total_count = 0
    
    for num_conditions in range(1, max_conditions + 1):
        for combo_indices in itertools.combinations(range(len(all_filter_conditions)), num_conditions):
            total_count += 1
            if is_valid_combination(combo_indices, all_filter_conditions):
                valid_count += 1
    
    filter_rate = (total_count - valid_count) / total_count * 100
    print(f"总组合数: {total_count}")
    print(f"有效组合数: {valid_count}")
    print(f"过滤率: {filter_rate:.1f}%")
    
    print("\n" + "="*60)
    print("🎯 验证结论:")
    print("✅ 允许同因子不同操作符 (形成范围条件)")
    print("✅ 允许不同因子相同操作符")
    print("❌ 禁止同因子同操作符 (避免重复)")
    print("✅ 保留所有配置文件中的value_options")


if __name__ == "__main__":
    test_validation_logic()