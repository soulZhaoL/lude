#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
可转债多因子领域知识优化程序入口
"""

import argparse
import os

from lude.utils.common_utils import load_data
from lude.optimization.optimization_engine import run_optimization
from lude.utils.logger import optimization_logger as logger

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='可转债多因子领域知识优化程序')
    parser.add_argument('--method', type=str, default='tpe', choices=['tpe', 'random', 'cmaes'],
                        help='优化方法: tpe(贝叶斯优化), random(随机搜索), cmaes(协方差矩阵适应进化策略)')
    parser.add_argument('--n_trials', type=int, default=3000, help='优化迭代次数')
    parser.add_argument('--n_factors', type=int, default=3, choices=[3, 4, 5], help='因子数量')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期')
    parser.add_argument('--price_min', type=int, default=100, help='价格下限')
    parser.add_argument('--price_max', type=int, default=150, help='价格上限')
    parser.add_argument('--hold_num', type=int, default=5, help='持仓数量')
    parser.add_argument('--n_jobs', type=int, default=15, help='并行任务数')
    parser.add_argument('--strategy', type=str, default='multistage', 
                        choices=['domain', 'prescreen', 'multistage', 'filter'],
                        help='优化策略: domain(领域知识分组), prescreen(预筛选), multistage(多阶段), filter(过滤冗余)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 加载数据
    df = load_data()
    
    # 运行优化
    model_path = run_optimization(df, args)
    
    if model_path:
        logger.info(f"\n优化完成，最佳模型已保存至: {model_path}")
    else:
        logger.warning("\n优化未完成或出错")
    
    logger.info("完成!")

if __name__ == "__main__":
    # 入口函数
    main()
