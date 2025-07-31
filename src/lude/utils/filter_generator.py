#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
过滤因子生成器模块
根据filter_factors_config.yaml配置生成排除因子条件组合
"""

import yaml
import itertools
import os
from typing import List, Dict, Any, Optional

from lude.utils.logger import optimization_logger as logger
from lude.config.paths import CONFIG_DIR


class FilterFactorGenerator:
    """过滤因子生成器类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化过滤因子生成器
        
        Args:
            config_path: 配置文件路径，默认使用filter_factors_config.yaml
        """
        if config_path is None:
            config_path = os.path.join(CONFIG_DIR, 'filter_factors_config.yaml')
        
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载过滤因子配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载过滤因子配置: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"加载过滤因子配置文件失败: {e}")
            return {'filter_factors': {}, 'combination_rules': {}}
    
    def get_available_factors(self) -> List[str]:
        """获取所有可用的过滤因子名称"""
        return list(self.config.get('filter_factors', {}).keys())
    
    def _convert_operator(self, op: str) -> str:
        """
        转换操作符格式
        
        Args:
            op: 配置文件中的操作符 (gte, lte, gt, lt, eq, ne)
            
        Returns:
            计算器识别的操作符 (>=, <=, >, <, ==, !=)
        """
        operator_map = {
            'gte': '>=',
            'lte': '<=', 
            'gt': '>',
            'lt': '<',
            'eq': '==',
            'ne': '!='
        }
        return operator_map.get(op, op)

    def generate_single_factor_conditions(self, factor_name: str) -> List[Dict[str, Any]]:
        """
        为单个因子生成过滤条件
        
        Args:
            factor_name: 因子名称
            
        Returns:
            过滤条件列表
        """
        if factor_name not in self.config['filter_factors']:
            logger.warning(f"因子 {factor_name} 不在配置中")
            return []
        
        factor_config = self.config['filter_factors'][factor_name]
        conditions = []
        
        # 获取配置参数
        operators = factor_config.get('operators', ['gte', 'lte'])
        value_options = factor_config.get('value_options', [])
        max_conditions = factor_config.get('max_conditions', 1)
        
        if not value_options:
            logger.warning(f"因子 {factor_name} 没有配置可选值")
            return []

        # 根据max_conditions生成条件组合
        if max_conditions == 1:
            # 单条件：从operators和value_options中各选一个
            # 这里生成所有可能的单条件组合，供Optuna选择
            for operator in operators:
                for value in value_options:
                    conditions.append({
                        'factor': factor_name,
                        'operator': self._convert_operator(operator),
                        'value': value
                    })
        else:
            # 多条件：生成逻辑合理的范围条件
            # 确保生成的条件数量不超过max_conditions
            sorted_values = sorted(value_options)

            # 生成范围条件：一个>=和一个<=
            if len(sorted_values) >= 2 and max_conditions >= 2:
                for i in range(len(sorted_values)):
                    for j in range(i + 1, len(sorted_values)):
                        range_conditions = [
                            {
                                'factor': factor_name,
                                'operator': '>=',
                                'value': sorted_values[i]
                            },
                            {
                                'factor': factor_name,
                                'operator': '<=',
                                'value': sorted_values[j]
                            }
                        ]
                        conditions.extend(range_conditions)
        
        return conditions

    def generate_default_filter_conditions(self, selected_factors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        生成默认的过滤条件组合（使用配置中的第一个值作为默认值）
        
        Args:
            selected_factors: 指定的因子列表，如果None则使用配置中的所有因子
            
        Returns:
            过滤条件列表
        """
        # 确定要使用的因子
        if selected_factors is None:
            selected_factors = self.get_available_factors()
            if not selected_factors:
                logger.warning("没有可用的过滤因子")
                return []

        # 为每个选中的因子生成一个默认条件
        all_conditions = []
        for factor_name in selected_factors:
            factor_config = self.config['filter_factors'][factor_name]
            operators = factor_config.get('operators', ['gte', 'lte'])
            value_options = factor_config.get('value_options', [])
            # max_conditions 在新逻辑中不需要了，因为每个因子只生成一个默认条件

            if not value_options:
                continue

            # 使用第一个操作符和中位数值作为默认条件
            default_operator = operators[0] if operators else 'gte'
            default_value = value_options[len(value_options) // 2] if value_options else value_options[0]

            condition = {
                'factor': factor_name,
                'operator': self._convert_operator(default_operator),
                'value': default_value
            }
            all_conditions.append(condition)

        logger.info(f"生成了 {len(all_conditions)} 个默认过滤条件，涉及因子: {selected_factors}")
        return all_conditions
    
    def validate_conditions(self, conditions: List[Dict[str, Any]]) -> bool:
        """
        验证过滤条件的合理性
        
        Args:
            conditions: 过滤条件列表
            
        Returns:
            是否有效
        """
        if not conditions:
            return True
        
        # 按因子分组检查条件的逻辑合理性
        factor_conditions = {}
        for condition in conditions:
            factor = condition['factor']
            if factor not in factor_conditions:
                factor_conditions[factor] = []
            factor_conditions[factor].append(condition)
        
        # 检查每个因子的条件是否合理
        for factor, conds in factor_conditions.items():
            if len(conds) > 1:
                # 检查是否有互相矛盾的条件
                # 例如: x >= 10 和 x <= 5
                gte_vals = [c['value'] for c in conds if c['operator'] == '>=']
                lte_vals = [c['value'] for c in conds if c['operator'] == '<=']
                
                if gte_vals and lte_vals:
                    min_gte = min(gte_vals)
                    max_lte = max(lte_vals)
                    if min_gte >= max_lte:  # 修改为>=，因为相等也是矛盾的
                        logger.warning(f"因子 {factor} 的条件存在逻辑矛盾: >= {min_gte} 和 <= {max_lte}")
                        return False
        
        return True


def create_default_filter_conditions() -> List[Dict[str, Any]]:
    """
    创建默认过滤条件的便捷函数（不依赖trial）
    
    Args:
        available_factors_in_data: 数据中实际可用的因子列表
        
    Returns:
        过滤条件列表
    """
    generator = FilterFactorGenerator()
    
    # 只使用数据中实际存在的因子
    config_factors = generator.get_available_factors()

    # 生成默认过滤条件
    conditions = generator.generate_default_filter_conditions(config_factors)
    
    # 验证条件合理性
    if not generator.validate_conditions(conditions):
        logger.warning("生成的过滤条件不合理，返回空条件")
        return []
    
    return conditions


if __name__ == "__main__":
    # 测试过滤因子生成器
    generator = FilterFactorGenerator()
    
    print("可用的过滤因子:", generator.get_available_factors())
    
    # 测试生成默认条件
    conditions = generator.generate_default_filter_conditions()
    print(f"生成的默认过滤条件 ({len(conditions)} 个):")
    for condition in conditions:
        print(f"  {condition}")
    
    # 验证条件
    is_valid = generator.validate_conditions(conditions)
    print(f"条件验证结果: {'有效' if is_valid else '无效'}")