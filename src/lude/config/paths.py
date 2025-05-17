#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路径配置模块
统一管理项目中使用的各种路径
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

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
DINGDING_OPT_RESULT_PATH = os.path.join(DATA_DIR, 'dd_opt.txt')
DINGDING_OPT_RESULT_PATH_TEST = os.path.join(DATA_DIR, 'dd_opt_test.txt')
HIGH_PERFORMANCE_FACTORS_PATH = os.path.join(DATA_DIR, 'high_performance_factors.json')

# 合并工具相关路径
MERGE_DIR = os.path.join(PROJECT_ROOT, 'src', 'lude', 'utils', 'merge')
MERGE_CSV_DIR = os.path.join(MERGE_DIR, 'csv')  # CSV文件存放目录
MERGE_RESULT_PATH = "/Users/zhaolei/Downloads/result.csv"  # 合并结果文件路径
BLACKLIST_PATH = os.path.join(MERGE_DIR, 'blacklist.json')  # 黑名单文件路径
