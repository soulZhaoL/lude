#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略配置管理器
独立的配置管理模块，用于多阶段优化策略
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from lude.utils.logger import setup_logger

logger = setup_logger(__name__)


class StrategyConfig:
    """策略配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化策略配置
        
        Args:
            config_path: 配置文件路径，默认使用strategy_config.yaml
        """
        if config_path is None:
            # 调整路径，因为现在在multistage子目录下
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "strategy_config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.investment_strategies = self.config['investment_strategies']
        self.combination_rules = self.config['strategy_combination_rules']
        self.optimization_params = self.config['optimization_params']
        self.conflict_rules = self.config.get('factor_conflict_rules', {})
    
    def get_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """获取投资策略配置"""
        return self.investment_strategies.get(strategy_name, {})
    
    def is_valid_combination(self, primary: str, secondary: str) -> bool:
        """检查策略组合是否有效"""
        combo = sorted([primary, secondary])
        
        # 检查是否在允许列表中
        for allowed in self.combination_rules['allowed_combinations']:
            if sorted(allowed) == combo:
                return True
        
        # 检查是否在不建议列表中
        for discouraged in self.combination_rules['discouraged_combinations']:
            if sorted(discouraged) == combo:
                logger.warning(f"策略组合 {primary} + {secondary} 不建议使用")
                return False
        
        # 默认允许
        return True
    
    def check_factor_conflicts(self, rank_factors: List[Dict[str, Any]]) -> bool:
        """检查因子组合是否存在冲突
        
        Args:
            rank_factors: 因子列表，每个元素包含name, weight, ascending等信息
            
        Returns:
            bool: True表示无冲突，False表示存在冲突
        """
        if not self.conflict_rules:
            return True
            
        factor_dict = {f['name']: f for f in rank_factors}
        factor_names = set(factor_dict.keys())
        
        # 检查相关因子组内方向一致性
        related_groups = self.conflict_rules.get('related_groups', {})
        for group_name, group_factors in related_groups.items():
            group_factors_in_selection = [f for f in group_factors if f in factor_names]
            
            if len(group_factors_in_selection) >= 2:
                # 检查同组因子方向是否一致
                directions = [factor_dict[f]['ascending'] for f in group_factors_in_selection]
                if len(set(directions)) > 1:
                    logger.debug(f"因子冲突: {group_name}组内因子方向不一致: {group_factors_in_selection}")
                    return False
        
        # 检查互斥因子对
        exclusive_pairs = self.conflict_rules.get('exclusive_pairs', [])
        for pair in exclusive_pairs:
            if len(pair) == 2 and pair[0] in factor_names and pair[1] in factor_names:
                factor1_asc = factor_dict[pair[0]]['ascending']
                factor2_asc = factor_dict[pair[1]]['ascending']
                
                # 如果互斥因子方向相反，可能存在冲突
                if factor1_asc != factor2_asc:
                    logger.debug(f"因子冲突: 互斥因子对 {pair[0]}({factor1_asc}) vs {pair[1]}({factor2_asc})")
                    return False
        
        return True