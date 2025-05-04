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