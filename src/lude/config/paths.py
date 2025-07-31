#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路径配置模块
统一管理项目中使用的各种路径
"""

import os
from pathlib import Path


def get_project_root():
    """
    获取项目根目录，使用多种方法确保稳健性
    
    优先级：
    1. 环境变量 LUDE_PROJECT_ROOT（最高优先级）
    2. 从标志文件查找（pyproject.toml 或 setup.py）
    3. 从包结构推导（备用方案）
    
    Returns:
        str: 项目根目录的绝对路径
    """
    # 方法1：使用环境变量（推荐用于生产环境）
    if 'LUDE_PROJECT_ROOT' in os.environ:
        root = os.environ['LUDE_PROJECT_ROOT']
        if os.path.exists(root):
            return os.path.abspath(root)

    # 方法2：通过标志文件查找项目根目录
    current_path = Path(__file__).resolve()

    # 向上查找包含项目标志文件的目录
    for parent in current_path.parents:
        # 检查常见的项目根标志文件
        markers = ['pyproject.toml', 'setup.py', 'requirements.txt', '.git']
        if any(parent.joinpath(marker).exists() for marker in markers):
            return str(parent)

    # 方法3：基于包结构推导（备用方案）
    # 假设当前文件在 src/lude/config/paths.py
    fallback_root = current_path.parent.parent.parent.parent
    if fallback_root.name != 'src':  # 验证结构合理性
        return str(fallback_root)

    # 最后的备用方案
    return str(current_path.parent.parent.parent.parent)

# 项目根目录
PROJECT_ROOT = get_project_root()


# 添加路径验证和调试功能
def validate_project_paths():
    """验证项目路径配置是否正确"""
    issues = []

    # 验证项目根目录
    if not os.path.exists(PROJECT_ROOT):
        issues.append(f"项目根目录不存在: {PROJECT_ROOT}")

    # 验证关键目录
    key_dirs = {
        'src目录': os.path.join(PROJECT_ROOT, 'src'),
        'lude包目录': os.path.join(PROJECT_ROOT, 'src', 'lude'),
        'config目录': CONFIG_DIR,
        'data目录': DATA_DIR,
        'results目录': RESULTS_DIR,
        'logs目录': LOGS_DIR
    }

    for name, path in key_dirs.items():
        if not os.path.exists(path):
            issues.append(f"{name}不存在: {path}")

    return issues


def get_path_info():
    """获取路径配置信息，用于调试"""
    return {
        'PROJECT_ROOT': PROJECT_ROOT,
        'CONFIG_DIR': CONFIG_DIR,
        'DATA_DIR': DATA_DIR,
        'RESULTS_DIR': RESULTS_DIR,
        'LOGS_DIR': LOGS_DIR,
        'current_file': __file__,
        'validation_issues': validate_project_paths()
    }

# 资源文件目录
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'src', 'lude', 'config')

# 数据目录
DATA_DIR = os.path.join(PROJECT_ROOT, 'src', 'lude', 'data')

# 结果目录
RESULTS_DIR = os.path.join(PROJECT_ROOT, "optimization_results")

# 日志目录
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

# 配置文件路径
FACTOR_MAPPING_PATH = os.path.join(CONFIG_DIR, 'factor_mapping.json')
OPTIMIZATION_CONFIG_PATH = os.path.join(CONFIG_DIR, 'optimization_config.yaml')

# 高收益因子组合文件路径
HIGH_PERFORMANCE_FACTORS_PATH = os.path.join(DATA_DIR, 'high_performance_factors.json')
DINGDING_OPT_RESULT_PATH = os.path.join(DATA_DIR, 'dd_opt.txt')
DINGDING_OPT_RESULT_PATH_TEST = os.path.join(DATA_DIR, 'dd_opt_test.txt')
HIGH_PERFORMANCE_FACTORS4_1_PATH = os.path.join(DATA_DIR, 'fac4_1/merged_factors.json')
HIGH_PERFORMANCE_FACTORS4_2_PATH = os.path.join(DATA_DIR, 'fac4_2/merged_factors.json')
HIGH_PERFORMANCE_FACTORS4_3_PATH = os.path.join(DATA_DIR, 'fac4_3/merged_factors.json')
HIGH_PERFORMANCE_FACTORS4_4_PATH = os.path.join(DATA_DIR, 'fac4_4/merged_factors.json')

HIGH_PERFORMANCE_FACTORS5_1_PATH = os.path.join(DATA_DIR, 'fac5_1/merged_factors.json')
HIGH_PERFORMANCE_FACTORS5_2_PATH = os.path.join(DATA_DIR, 'fac5_2/merged_factors.json')

HIGH_PERFORMANCE_FACTORS6_1_PATH = os.path.join(DATA_DIR, 'fac6_1/merged_factors.json')
HIGH_PERFORMANCE_FACTORS6_2_PATH = os.path.join(DATA_DIR, 'fac6_2/merged_factors.json')

# 合并工具相关路径
MERGE_DIR = os.path.join(PROJECT_ROOT, 'src', 'lude', 'utils', 'merge')
MERGE_CSV_DIR = os.path.join(MERGE_DIR, 'csv')  # CSV文件存放目录
MERGE_RESULT_PATH = "/Users/zhaolei/Downloads/result.csv"  # 合并结果文件路径
BLACKLIST_PATH = os.path.join(MERGE_DIR, 'blacklist.json')  # 黑名单文件路径
