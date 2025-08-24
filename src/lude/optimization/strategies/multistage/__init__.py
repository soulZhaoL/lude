#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多阶段优化策略模块
包含语义化目标函数的v1和v2版本实现
"""

from .config import StrategyConfig
from .semantic_objective_v1 import (
    create_semantic_objective_function,
    create_refined_objective_function as create_refined_objective_function_v1,
    analyze_best_strategies as analyze_best_strategies_v1
)
from .semantic_objective_v2 import (
    create_fixed_semantic_objective_function,
    create_fixed_refined_objective_function,
    analyze_best_strategies,
    ALL_FACTORS
)
from .coordinator import (
    multistage_optimization,
    create_optimized_objective_function
)

__all__ = [
    'StrategyConfig',
    # v1 exports (动态参数空间)
    'create_semantic_objective_function',
    'create_refined_objective_function_v1',
    'analyze_best_strategies_v1',
    # v2 exports (固定参数空间)
    'create_fixed_semantic_objective_function',
    'create_fixed_refined_objective_function',
    'analyze_best_strategies',
    'ALL_FACTORS',
    # coordinator exports
    'multistage_optimization',
    'create_optimized_objective_function'
]