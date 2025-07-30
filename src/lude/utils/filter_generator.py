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
    
    def generate_single_factor_conditions(self, factor_name: str, trial=None) -> List[Dict[str, Any]]:
        """
        为单个因子生成过滤条件
        
        Args:
            factor_name: 因子名称
            trial: Optuna trial对象，用于参数建议
            
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
        
        # 根据最大条件数生成条件
        if trial is not None:
            # 使用Optuna建议参数
            num_conditions = trial.suggest_int(f"{factor_name}_num_conditions", 1, max_conditions)
            
            for i in range(num_conditions):
                # 选择操作符
                operator = trial.suggest_categorical(f"{factor_name}_op_{i}", operators)
                # 选择数值
                value = trial.suggest_categorical(f"{factor_name}_val_{i}", value_options)
                
                conditions.append({
                    'factor': factor_name,
                    'operator': self._convert_operator(operator),
                    'value': value
                })
        else:
            # 使用默认范围
            default_range = factor_config.get('default_range', {})
            
            if default_range.get('min_op') and default_range.get('min_val') is not None:
                conditions.append({
                    'factor': factor_name,
                    'operator': self._convert_operator(default_range['min_op']),
                    'value': default_range['min_val']
                })
            
            if default_range.get('max_op') and default_range.get('max_val') is not None:
                conditions.append({
                    'factor': factor_name,
                    'operator': self._convert_operator(default_range['max_op']),
                    'value': default_range['max_val']
                })
        
        return conditions

    def generate_filter_conditions_with_trial(self, trial, selected_factors: Optional[List[str]] = None) -> List[
        Dict[str, Any]]:
        """
        使用Optuna trial生成过滤条件（仅优化每个因子的具体条件值）
        
        Args:
            trial: Optuna trial对象
            selected_factors: 指定的因子列表，如果None则使用配置中的所有因子
            
        Returns:
            过滤条件列表
        """
        # 确定要使用的因子 - 完全由配置文件驱动
        if selected_factors is None:
            selected_factors = self.get_available_factors()
            if not selected_factors:
                logger.warning("没有可用的过滤因子")
                return []

        # 为每个选中的因子生成条件（只优化具体的条件值，不优化因子选择）
        all_conditions = []
        for factor_name in selected_factors:
            factor_conditions = self.generate_single_factor_conditions(factor_name, trial)
            all_conditions.extend(factor_conditions)
        
        logger.debug(f"生成了 {len(all_conditions)} 个过滤条件，涉及因子: {selected_factors}")
        return all_conditions

    def generate_default_filter_conditions(self, selected_factors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        生成默认的过滤条件组合（不依赖trial）
        
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

        # 为每个选中的因子生成默认条件
        all_conditions = []
        for factor_name in selected_factors:
            factor_conditions = self.generate_single_factor_conditions(factor_name, trial=None)
            all_conditions.extend(factor_conditions)

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
                    if min_gte > max_lte:
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