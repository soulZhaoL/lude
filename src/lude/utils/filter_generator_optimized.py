#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化过滤因子生成器模块
支持简化的配置结构：
1. lower: 下限约束，设置最小值（原normal中的gte约束）
2. upper: 上限约束，设置最大值（原normal中的lte约束）
移除normal概念，统一使用lower/upper，语义更清晰
"""

import yaml
import itertools
import os
from typing import List, Dict, Any, Optional, Set

from lude.utils.logger import optimization_logger as logger
from lude.config.paths import CONFIG_DIR


class OptimizedFilterFactorGenerator:
    """简化过滤因子生成器类（移除normal，只使用lower/upper）"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化过滤因子生成器
        
        Args:
            config_path: 配置文件路径，默认使用filter_factors_optimized_config.yaml
        """
        if config_path is None:
            config_path = os.path.join(CONFIG_DIR, 'filter_factors_optimized_config.yaml')
        
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载过滤因子配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载统一格式过滤因子配置: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"加载过滤因子配置文件失败: {e}")
            return {'filter_factors': {}, 'combination_rules': {}}
    
    def get_available_factors(self) -> List[str]:
        """获取所有可用的配置因子名称（展开约束结构）"""
        factor_configs = []
        for factor_name, factor_config in self.config.get('filter_factors', {}).items():
            # 只检查lower和upper约束
            if 'lower' in factor_config:
                factor_configs.append(f"{factor_name}_lower")
            if 'upper' in factor_config:
                factor_configs.append(f"{factor_name}_upper")
        return factor_configs
    
    def get_original_factors(self) -> Set[str]:
        """获取所有原始因子名称（直接从配置key获取）"""
        return set(self.config.get('filter_factors', {}).keys())
    
    def get_factor_groups(self) -> Dict[str, List[str]]:
        """
        获取因子分组信息（展开约束结构）
        
        Returns:
            字典，key为原始因子名，value为相关的配置选项列表
        """
        factor_groups = {}
        
        for factor_name, factor_config in self.config.get('filter_factors', {}).items():
            factor_groups[factor_name] = []
            
            # 只检查lower和upper约束
            if 'lower' in factor_config:
                factor_groups[factor_name].append(f"{factor_name}_lower")
            if 'upper' in factor_config:
                factor_groups[factor_name].append(f"{factor_name}_upper")
        
        return factor_groups
    
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

    def generate_single_factor_conditions(self, config_factor_name: str) -> List[Dict[str, Any]]:
        """
        为单个配置因子生成过滤条件（支持lower/upper约束）
        
        Args:
            config_factor_name: 配置因子名称（如 pure_value_lower, turnover_upper等）
            
        Returns:
            过滤条件列表
        """
        # 解析配置因子名称
        if not config_factor_name.endswith(('_lower', '_upper')):
            logger.warning(f"配置因子名称格式错误: {config_factor_name}")
            return []
        
        # 提取原始因子名和约束类型
        for suffix in ['_lower', '_upper']:
            if config_factor_name.endswith(suffix):
                original_factor = config_factor_name[:-len(suffix)]
                constraint_type = suffix[1:]  # 去掉下划线
                break
        
        if original_factor not in self.config['filter_factors']:
            logger.warning(f"原始因子 {original_factor} 不在配置中")
            return []
        
        factor_config = self.config['filter_factors'][original_factor]
        
        if constraint_type not in factor_config:
            logger.warning(f"因子 {original_factor} 没有 {constraint_type} 约束配置")
            return []
        
        constraint_config = factor_config[constraint_type]
        conditions = []
        
        # 获取配置参数
        operators = constraint_config.get('operators', ['gte'])
        value_options = constraint_config.get('value_options', [])
        
        if not value_options:
            logger.warning(f"因子 {original_factor}.{constraint_type} 没有配置可选值")
            return []

        # 生成所有可能的条件组合
        for operator in operators:
            for value in value_options:
                conditions.append({
                    'factor': original_factor,  # 使用原始因子名
                    'config_factor': config_factor_name,  # 完整的配置因子名
                    'constraint_type': constraint_type,  # 约束类型
                    'operator': self._convert_operator(operator),
                    'value': value,
                    'desc': factor_config.get('desc', '')
                })
        
        return conditions

    def generate_factor_combinations(self, max_factors: int = 2) -> List[List[str]]:
        """
        生成因子组合，确保同一原始因子的上下限配置组不会同时选择
        
        Args:
            max_factors: 最大因子数量
            
        Returns:
            因子组合列表
        """
        available_factors = self.get_available_factors()
        factor_groups = self.get_factor_groups()
        
        # 生成所有可能的组合
        valid_combinations = []
        
        for r in range(1, max_factors + 1):
            for combination in itertools.combinations(available_factors, r):
                # 检查组合是否有效（同一原始因子的配置组不能同时出现）
                if self._is_valid_combination(combination, factor_groups):
                    valid_combinations.append(list(combination))
        
        return valid_combinations
    
    def _is_valid_combination(self, combination: tuple, factor_groups: Dict[str, List[str]]) -> bool:
        """
        检查因子组合是否有效（确保同一原始因子的lower和upper不能同时选择）
        
        Args:
            combination: 因子组合
            factor_groups: 因子分组信息（为了向前兼容性保留）
            
        Returns:
            是否有效
        """
        # 检查是否有同一原始因子的lower和upper同时出现
        original_factors_used = set()
        
        for config_factor in combination:
            # 解析原始因子名
            for suffix in ['_lower', '_upper']:
                if config_factor.endswith(suffix):
                    original_factor = config_factor[:-len(suffix)]
                    break
            else:
                logger.warning(f"无法解析配置因子名称: {config_factor}")
                return False
            
            if original_factor in original_factors_used:
                # 同一原始因子不能有多个约束
                return False
            original_factors_used.add(original_factor)
        
        return True

    def generate_default_filter_conditions(self, selected_factors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        生成默认的过滤条件组合
        
        Args:
            selected_factors: 指定的因子列表，如果None则智能选择
            
        Returns:
            过滤条件列表
        """
        # 如果没有指定因子，智能选择一些代表性因子
        if selected_factors is None:
            selected_factors = self._select_representative_factors()
        
        if not selected_factors:
            logger.warning("没有可用的过滤因子")
            return []

        # 为每个选中的因子生成一个默认条件
        all_conditions = []
        for factor_name in selected_factors:
            # 解析原始因子名和约束类型
            parts = factor_name.split('_')
            if len(parts) < 2:
                logger.warning(f"因子名格式错误: {factor_name}")
                continue
            
            constraint_type = parts[-1]
            original_factor = '_'.join(parts[:-1])
            
            if original_factor not in self.config['filter_factors']:
                logger.warning(f"原始因子 {original_factor} 不在配置中")
                continue
            
            factor_config = self.config['filter_factors'][original_factor]
            if constraint_type not in factor_config:
                logger.warning(f"因子 {original_factor} 没有 {constraint_type} 约束类型")
                continue
            
            constraint_config = factor_config[constraint_type]
            operators = constraint_config.get('operators', ['gte'])
            value_options = constraint_config.get('value_options', [])

            if not value_options:
                continue

            # 使用第一个操作符和中位数值作为默认条件
            default_operator = operators[0] if operators else 'gte'
            default_value = value_options[len(value_options) // 2] if value_options else value_options[0]

            condition = {
                'factor': original_factor,
                'config_factor': factor_name,
                'constraint_type': constraint_type,
                'operator': self._convert_operator(default_operator),
                'value': default_value,
                'desc': factor_config.get('desc', '')
            }
            all_conditions.append(condition)

        logger.info(f"生成了 {len(all_conditions)} 个默认过滤条件，涉及因子: {selected_factors}")
        return all_conditions
    
    def _select_representative_factors(self) -> List[str]:
        """
        智能选择代表性因子，确保不同类型都有覆盖且不冲突
        
        Returns:
            选中的因子列表
        """
        available_factors = self.get_available_factors()
        
        # 按类型选择代表性因子
        representative_factors = []
        
        # 优先选择核心因子（使用lower/upper约束）
        priority_factors = [
            'pure_value_lower',           # 价值类下限
            'theory_conv_prem_upper',     # 成本类上限
            'issue_size_lower',           # 规模类下限
        ]
        
        for factor in priority_factors:
            if factor in available_factors:
                representative_factors.append(factor)
        
        # 如果还有空间，选择一些风险控制因子（避免冲突）
        if len(representative_factors) < 2:
            risk_factors = ['turnover_lower', 'pct_chg_upper']
            for factor in risk_factors:
                if factor in available_factors and len(representative_factors) < 2:
                    representative_factors.append(factor)
        
        return representative_factors
    
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
        
        # 按原始因子分组检查条件的逻辑合理性
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
                gte_vals = [c['value'] for c in conds if c['operator'] == '>=']
                lte_vals = [c['value'] for c in conds if c['operator'] == '<=']
                
                if gte_vals and lte_vals:
                    min_gte = min(gte_vals)
                    max_lte = max(lte_vals)
                    if min_gte >= max_lte:
                        logger.warning(f"因子 {factor} 的条件存在逻辑矛盾: >= {min_gte} 和 <= {max_lte}")
                        return False
        
        return True

    def get_factor_info(self, config_factor_name: str) -> Dict[str, Any]:
        """
        获取配置因子的详细信息
        
        Args:
            config_factor_name: 配置因子名称（如 pure_value_normal）
            
        Returns:
            因子信息字典
        """
        # 解析配置因子名称
        constraint_type = None
        original_factor = None
        
        for suffix in ['_lower', '_upper']:
            if config_factor_name.endswith(suffix):
                original_factor = config_factor_name[:-len(suffix)]
                constraint_type = suffix[1:]
                break
        
        if not original_factor or original_factor not in self.config['filter_factors']:
            return {}
        
        factor_config = self.config['filter_factors'][original_factor]
        
        if not constraint_type or constraint_type not in factor_config:
            return {}
        
        constraint_config = factor_config[constraint_type]
        
        return {
            'name': factor_config.get('name', original_factor),
            'desc': factor_config.get('desc', ''),
            'constraint_type': constraint_type,
            'operators': constraint_config.get('operators', []),
            'value_options': constraint_config.get('value_options', []),
            'original_factor': original_factor,
            'data_type': factor_config.get('data_type', 'numeric'),
            'max_conditions': constraint_config.get('max_conditions', 1)
        }


def create_optimized_filter_conditions() -> List[Dict[str, Any]]:
    """
    创建简化格式默认过滤条件的便捷函数
    
    Returns:
        过滤条件列表
    """
    generator = OptimizedFilterFactorGenerator()
    
    # 生成默认过滤条件
    conditions = generator.generate_default_filter_conditions()
    
    # 验证条件合理性
    if not generator.validate_conditions(conditions):
        logger.warning("生成的过滤条件不合理，返回空条件")
        return []
    
    return conditions


if __name__ == "__main__":
    # 测试简化格式过滤因子生成器
    generator = OptimizedFilterFactorGenerator()
    
    print("🎯 简化格式过滤因子生成器测试")
    print("=" * 60)
    
    print("\n📊 可用的配置因子:", len(generator.get_available_factors()))
    for factor in generator.get_available_factors()[:10]:  # 显示前10个
        info = generator.get_factor_info(factor)
        if info:
            print(f"  {factor}: {info['name']} ({info['constraint_type']}) - {info['desc'][:50]}...")
    
    print("\n📊 因子分组信息:")
    factor_groups = generator.get_factor_groups()
    for original_factor, config_factors in list(factor_groups.items())[:5]:  # 显示前5个
        print(f"  {original_factor}: {config_factors}")
    
    print("\n📊 有效因子组合示例:")
    combinations = generator.generate_factor_combinations(max_factors=2)
    for combo in combinations[:10]:  # 显示前10个
        print(f"  {combo}")
    
    # 测试生成默认条件
    print("\n📊 默认过滤条件:")
    conditions = generator.generate_default_filter_conditions()
    for condition in conditions:
        constraint_info = f"({condition.get('constraint_type', 'unknown')})" if 'constraint_type' in condition else ""
        print(f"  {condition['factor']} {condition['operator']} {condition['value']} {constraint_info} - {condition['desc'][:30]}...")
    
    # 验证条件
    is_valid = generator.validate_conditions(conditions)
    print(f"\n✅ 条件验证结果: {'有效' if is_valid else '无效'}")