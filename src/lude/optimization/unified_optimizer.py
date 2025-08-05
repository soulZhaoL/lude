#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一优化器入口

作为所有优化策略的统一入口点，支持单次和持续优化模式
"""

import argparse

from lude.utils.common_utils import load_data
from lude.optimization.engine import run_optimization
from lude.optimization.continuous_optimizer import run_continuous_optimization
from lude.utils.logger import optimization_logger as logger


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='可转债多因子统一优化程序')
    
    # 运行模式
    parser.add_argument('--mode', type=str, default='single', choices=['single', 'continuous'],
                        help='运行模式: single(单次运行), continuous(持续优化)')
    
    # 优化方法和策略
    parser.add_argument('--method', type=str, default='tpe', choices=['tpe', 'random', 'cmaes'],
                        help='优化方法: tpe(贝叶斯优化), random(随机搜索), cmaes(协方差矩阵适应进化策略)')
    parser.add_argument('--strategy', type=str, default='multistage', 
                        choices=['domain', 'prescreen', 'multistage', 'filter'],
                        help='优化策略: domain(领域知识分组), prescreen(预筛选), multistage(多阶段), filter(过滤冗余)')
    
    # 优化参数
    parser.add_argument('--n_trials', type=int, default=3000, help='优化迭代次数')
    parser.add_argument('--n_factors', type=int, default=3, choices=[3, 4, 5, 6, 7], help='因子数量')
    
    # 回测参数
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期')
    parser.add_argument('--price_min', type=int, default=100, help='价格下限')
    parser.add_argument('--price_max', type=int, default=150, help='价格上限')
    parser.add_argument('--hold_num', type=int, default=5, help='持仓数量')
    
    # 运行参数
    parser.add_argument('--n_jobs', type=int, default=15, help='并行任务数')
    parser.add_argument('--seed', type=int, default=42, help='随机种子(单次模式)')
    parser.add_argument('--workspace_id', type=str, default='', help='工作区ID标识，用于进程管理')
    
    # 持续优化参数
    parser.add_argument('--iterations', type=int, default=10, help='持续优化次数')
    parser.add_argument('--seed_start', type=int, default=42, help='起始随机种子(持续模式)')
    parser.add_argument('--seed_step', type=int, default=1000, help='种子递增步长(持续模式)')
    
    # 新增：过滤优化参数
    parser.add_argument('--enable_filter_opt', action='store_true', 
                        help='启用过滤因子组合优化')
    
    return parser.parse_args()


def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_args()
        
        # 设置进程标题，包含工作区ID
        try:
            import setproctitle
            if args.workspace_id:
                process_title = f"lude_unified_optimizer_{args.workspace_id}"
                setproctitle.setproctitle(process_title)
                logger.info(f"进程标题已设置为: {process_title}")
        except ImportError:
            logger.warning("setproctitle模块未安装，无法设置进程标题")
        
        logger.info(f"启动统一优化器 - 模式: {args.mode}")
        logger.info(f"过滤优化参数: {getattr(args, 'enable_filter_opt', False)}")
        
        if args.mode == 'single':
            # 单次优化模式
            logger.info("执行单次优化")
            
            # 加载数据
            df = load_data()
            
            # 运行优化
            model_path = run_optimization(df, args)
            
            if model_path:
                logger.info(f"优化完成，最佳模型已保存至: {model_path}")
            else:
                logger.warning("优化未完成或出错")
                
        elif args.mode == 'continuous':
            # 持续优化模式
            logger.info("执行持续优化")
            
            # 运行持续优化
            run_continuous_optimization(
                iterations=args.iterations,
                strategy=args.strategy,
                method=args.method,
                n_trials=args.n_trials,
                n_factors=args.n_factors,
                start_date=args.start_date,
                end_date=args.end_date,
                price_min=args.price_min,
                price_max=args.price_max,
                hold_num=args.hold_num,
                n_jobs=args.n_jobs,
                seed_start=args.seed_start,
                seed_step=args.seed_step,
                workspace_id=args.workspace_id,
                enable_filter_opt=getattr(args, 'enable_filter_opt', False)
            )
        
        logger.info("优化程序完成!")
        
    except Exception as e:
        # 🚨 关键修复：捕获所有异常并同时输出到logger和stderr
        import traceback
        import sys
        
        error_msg = f"优化器执行异常: {str(e)}"
        full_traceback = traceback.format_exc()
        
        # 输出到logger
        logger.error(error_msg)
        logger.error(f"完整错误堆栈:\n{full_traceback}")
        
        # 🚨 关键：同时输出到stderr，确保shell脚本能捕获
        print(f"ERROR: {error_msg}", file=sys.stderr)
        print(f"完整错误堆栈:\n{full_traceback}", file=sys.stderr)
        sys.stderr.flush()
        
        # 🚨 重要：以非零退出码退出，让shell脚本知道失败了
        sys.exit(1)


if __name__ == "__main__":
    # 入口函数
    main()