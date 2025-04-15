import optuna
import pandas as pd
import numpy as np
import itertools
import joblib
from more_factor_test_origin_code import cal_cagr
from datetime import datetime
import os
from cal_factor_util import add_custom_factors
import argparse

# 创建结果目录
RESULTS_DIR = "optimization_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='可转债多因子优化程序')
    parser.add_argument('--method', type=str, default='random', choices=['tpe', 'random', 'cmaes'],
                        help='优化方法: tpe(贝叶斯优化), random(随机搜索), cmaes(协方差矩阵适应进化策略,不支持分类任务 true/false)')
    parser.add_argument('--n_trials', type=int, default=2000, help='优化迭代次数')
    parser.add_argument('--n_factors', type=int, default=3, choices=[3, 4, 5], help='因子数量')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期')
    parser.add_argument('--price_min', type=int, default=100, help='价格下限')
    parser.add_argument('--price_max', type=int, default=150, help='价格上限')
    parser.add_argument('--hold_num', type=int, default=5, help='持仓数量')
    parser.add_argument('--n_jobs', type=int, default=10, help='并行任务数')
    
    return parser.parse_args()

def load_data():
    """加载数据并添加自定义因子"""
    print("正在加载数据...")
    df = pd.read_parquet('cb_data.pq')
    
    print("正在计算自定义因子...")
    df = add_custom_factors(df)
    
    return df

def get_available_factors():
    """获取所有可用因子"""
    # 这些是实际可用的因子
    factors = [
        'theory_conv_prem',
        'conv_prem',
        'dblow',
        'cap_mv_rate',
        'turnover_5',
        'amount_5',
        'volatility_stk',
        'theory_value',
        'theory_bias',
        'remain_cap',
        'bond_prem',
        'remain_size',
        'turnover',
        'option_value',
        'amount',
        'bias_5',
        'alpha_pct_chg_5',
        'pure_value'
    ]
    
    return factors

def generate_factor_combinations(factors, num_factors, max_combinations=5000):
    """生成因子组合"""
    all_combinations = list(itertools.combinations(range(len(factors)), num_factors))
    print(f"因子数量 {num_factors}: 生成了 {len(all_combinations)} 个组合")
    # 如果组合数量过多，随机采样
    if len(all_combinations) > max_combinations:
        np.random.seed(42)
        indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
        combinations = [all_combinations[i] for i in indices]
    else:
        combinations = all_combinations
    
    print(f"生成了 {len(combinations)} 个因子组合")
    return combinations

def objective(trial, df, factors, factor_combinations, args):
    """优化目标函数"""
    # 选择因子组合
    combination_idx = trial.suggest_int("combination_idx", 0, len(factor_combinations) - 1)
    factor_indices = factor_combinations[combination_idx]
    
    # 构建因子配置
    rank_factors = []
    for i, idx in enumerate(factor_indices):
        factor_name = factors[idx]
        factor_info = {
            'name': factor_name,
            'weight': trial.suggest_int(f"factor{i}_weight", 1, 5),
            'ascending': trial.suggest_categorical(f"factor{i}_ascending", [True, False])
        }
        rank_factors.append(factor_info)
    
    # 计算年化收益率
    try:
        cagr = cal_cagr(df, args.start_date, args.end_date, args.hold_num, 
                        None, args.price_min, args.price_max, rank_factors)
        
        # 记录每次试验的详细信息
        trial.set_user_attr("rank_factors", rank_factors)
        return cagr
    except Exception as e:
        print(f"计算CAGR时出错: {e}")
        return -1.0  # 返回一个很差的值

def create_sampler(method):
    """创建采样器"""
    if method == 'tpe':
        return optuna.samplers.TPESampler(seed=42)
    elif method == 'random':
        return optuna.samplers.RandomSampler(seed=42)
    elif method == 'cmaes':
        try:
            return optuna.samplers.CmaEsSampler(seed=42)
        except (ImportError, ModuleNotFoundError):
            print("警告: cmaes 模块未安装，自动切换为 TPE 采样器")
            print("如需使用 CMA-ES，请运行: pip install cmaes")
            return optuna.samplers.TPESampler(seed=42)
    else:
        raise ValueError(f"不支持的优化方法: {method}")

def run_optimization(df, args):
    """运行优化过程"""
    # 获取可用因子
    factors = get_available_factors()
    print(f"可用因子总数: {len(factors)}")
    
    # 生成因子组合
    factor_combinations = generate_factor_combinations(factors, args.n_factors)
    
    # 创建时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建研究对象
    study_name = f"cb_optimization_{args.method}_{args.n_factors}factors_{timestamp}"
    storage_path = f"{RESULTS_DIR}/{study_name}.db"
    
    # 创建采样器
    sampler = create_sampler(args.method)
    
    study = optuna.create_study(
        study_name=study_name,
        storage=f"sqlite:///{storage_path}",
        sampler=sampler,
        direction="maximize"
    )
    
    # 开始优化
    print(f"开始使用 {args.method} 方法优化 {args.n_factors} 个因子组合...")
    print(f"优化参数: 迭代次数={args.n_trials}, 持仓数={args.hold_num}, 价格区间={args.price_min}-{args.price_max}")
    
    study.optimize(
        lambda trial: objective(trial, df, factors, factor_combinations, args),
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        show_progress_bar=True
    )
    
    # 获取最佳结果
    best_trial = study.best_trial
    best_value = best_trial.value
    best_rank_factors = best_trial.user_attrs["rank_factors"]
    
    # 打印结果
    print("\n" + "="*60)
    print(f"最佳年化收益率: {best_value:.4f}")
    print("\n最佳因子组合:")
    for i, factor in enumerate(best_rank_factors):
        print(f"  {i+1}. {factor['name']}")
        print(f"     - 权重: {factor['weight']}")
        print(f"     - 排序方向: {'降序' if not factor['ascending'] else '升序'}")
    print("="*60)
    
    # 保存最佳模型
    model_path = f"{RESULTS_DIR}/best_model_{args.method}_{args.n_factors}factors_{timestamp}.pkl"
    model_data = {
        "study_name": study_name,
        "best_value": best_value,
        "best_rank_factors": best_rank_factors,
        "optimization_method": args.method,
        "n_factors": args.n_factors,
        "price_range": (args.price_min, args.price_max),
        "date_range": (args.start_date, args.end_date),
        "hold_num": args.hold_num,
        "timestamp": timestamp
    }
    joblib.dump(model_data, model_path)
    print(f"\n最佳模型已保存至: {model_path}")
    
    # 输出前5个最佳结果
    print("\n前5个最佳组合:")
    top_trials = sorted(study.trials, key=lambda t: t.value if t.value is not None else float('-inf'), reverse=True)[:5]
    
    for i, trial in enumerate(top_trials):
        if trial.value is not None:
            print(f"\n{i+1}. 年化收益率: {trial.value:.4f}")
            rank_factors = trial.user_attrs.get("rank_factors", [])
            for j, factor in enumerate(rank_factors):
                print(f"   - {factor['name']} (权重: {factor['weight']}, {'降序' if not factor['ascending'] else '升序'})")
    
    return study, model_data

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 加载数据
    df = load_data()
    
    # 运行优化
    study, best_model = run_optimization(df, args)
    
    print("\n优化完成!")

if __name__ == "__main__":
    main()
