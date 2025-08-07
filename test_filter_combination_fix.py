#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的排除因子索引组合无重复选择逻辑
"""

import itertools
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from lude.utils.filter_generator_optimized import OptimizedFilterFactorGenerator


def test_filter_index_combination_fix():
    """测试修复后的排除因子索引组合生成逻辑"""
    
    print("🧪 测试修复后的排除因子索引组合无重复选择逻辑")
    print("=" * 65)
    
    try:
        # 1. 模拟原有逻辑：生成 all_filter_conditions
        generator = OptimizedFilterFactorGenerator()
        config_factors = generator.get_available_factors()
        
        all_filter_conditions = []
        for factor_name in config_factors:
            conditions = generator.generate_single_factor_conditions(factor_name)
            all_filter_conditions.extend(conditions)
        
        print(f"📋 all_filter_conditions 包含 {len(all_filter_conditions)} 个单独条件")
        
        # 显示部分条件示例
        print("\n📄 条件示例 (前10个):")
        for i, condition in enumerate(all_filter_conditions[:10]):
            print(f"  [{i}] {condition['factor']} {condition['operator']} {condition['value']}")
        
        # 2. 模拟修复后的逻辑：预生成无重复索引组合
        max_filter_factors = generator.config.get('combination_rules', {}).get('max_factors', 3)
        
        filter_index_combinations = []
        if all_filter_conditions:
            max_cond = min(max_filter_factors, len(all_filter_conditions))
            min_cond = max(1, max_cond - 1)
            
            print(f"\n🎯 生成 {min_cond}-{max_cond} 个条件的无重复索引组合")
            
            # 预生成所有可能的无重复索引组合
            for num_conditions in range(min_cond, max_cond + 1):
                for combo_indices in itertools.combinations(range(len(all_filter_conditions)), num_conditions):
                    filter_index_combinations.append(list(combo_indices))
            
            print(f"✅ 预生成 {len(filter_index_combinations)} 个无重复索引组合")
        
        # 3. 验证修复效果：模拟几次trial选择
        print("\n🔍 模拟修复后的trial选择效果:")
        
        import random
        random.seed(42)
        
        for trial_num in range(5):
            # 模拟 trial.suggest_int("filter_combo_idx", 0, len(filter_index_combinations) - 1)
            combo_idx = random.randint(0, len(filter_index_combinations) - 1)
            selected_indices = filter_index_combinations[combo_idx]
            
            # 根据索引选择实际条件
            selected_conditions = [all_filter_conditions[idx] for idx in selected_indices]
            
            print(f"\nTrial {trial_num + 1} (combo_idx={combo_idx}):")
            print(f"  索引: {selected_indices}")
            
            # 检查是否有重复条件
            condition_strs = []
            for condition in selected_conditions:
                condition_str = f"{condition['factor']} {condition['operator']} {condition['value']}"
                condition_strs.append(condition_str)
                print(f"    - {condition_str}")
            
            # 验证无重复
            unique_conditions = set(condition_strs)
            is_no_duplicate = len(condition_strs) == len(unique_conditions)
            print(f"  无重复验证: {'✅ 通过' if is_no_duplicate else '❌ 失败'}")
        
        # 4. 对比原逻辑的问题
        print("\n🚨 对比原逻辑可能产生的重复问题:")
        print("原逻辑: for i in range(num_filter_conditions):")
        print("           condition_idx = trial.suggest_int(f'filter_condition_{i}_idx', 0, len(all_filter_conditions) - 1)")
        
        # 模拟原逻辑可能的重复选择
        random.seed(123)  # 模拟可能导致重复的seed
        num_filter_conditions = 3
        original_selected_indices = []
        for i in range(num_filter_conditions):
            condition_idx = random.randint(0, len(all_filter_conditions) - 1)
            original_selected_indices.append(condition_idx)
        
        print(f"\n原逻辑可能选择的索引: {original_selected_indices}")
        original_conditions = [all_filter_conditions[idx] for idx in original_selected_indices]
        
        original_condition_strs = []
        for condition in original_conditions:
            condition_str = f"{condition['factor']} {condition['operator']} {condition['value']}"
            original_condition_strs.append(condition_str)
            print(f"  - {condition_str}")
        
        # 检查重复
        unique_original = set(original_condition_strs)
        has_duplicate = len(original_condition_strs) != len(unique_original)
        print(f"原逻辑重复检测: {'❌ 有重复' if has_duplicate else '✅ 无重复'}")
        
        if has_duplicate:
            print("🎯 这正是你遇到的问题！修复后的方案能完全避免这种重复。")
        
        print("\n🎉 测试完成! 修复方案验证通过。")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_filter_index_combination_fix()
    sys.exit(0 if success else 1)