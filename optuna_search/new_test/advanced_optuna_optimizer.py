import optuna
import pandas as pd
import numpy as np
import itertools
import time
from more_factor_test_origin_code import cal_cagr
from cal_factor_util import add_custom_factors
import os
import joblib
from datetime import datetime

# 创建结果目录
RESULTS_DIR = "optimization_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# 基础设置
N_TRIALS = 1000  # 迭代次数
N_JOBS = 10  # 并行数量
START_DATE = '20220801'  # 开始日期
END_DATE = '20240325'  # 结束日期
HOLD_NUM = 5  # 持仓数量
THRESHOLD_NUM = None  # 阈值轮动

# 价格范围优化
PRICE_MIN_RANGE = [90, 100, 110]
PRICE_MAX_RANGE = [140, 150, 160]

# 因子数量范围
MIN_FACTORS = 3
MAX_FACTORS = 6

def load_data():
    """加载数据并添加自定义因子"""
    print("正在加载数据...")
    df = pd.read_parquet('cb_data.pq')
    index = pd.read_parquet('index.pq')
    
    print("正在计算自定义因子...")
    df = add_custom_factors(df)
    
    return df, index

def get_all_factors():
    """获取所有可用因子"""
    # 合并所有因子
    all_factors = ['name',
        'pre_close',
        'open',
        'high',
        'low',
        'close',
        'limit',
        'close_ma_5',
        'bias_5',
        'pct_chg',
        'adj_factor',
        'vol',
        'vol_5',
        'amount',
        'amount_5',
        'volatility',
        'code_stk',
        'name_stk',
        'pre_close_stk',
        'open_stk',
        'high_stk',
        'low_stk',
        'close_stk',
        'pct_chg_stk',
        'adj_factor_stk',
        'vol_stk',
        'amount_stk',
        'pe_ttm',
        'pb',
        'ps_ttm',
        'dv_ratio',
        'total_share',
        'float_share',
        'total_mv',
        'circ_mv',
        'debt_to_assets',
        'volatility_stk',
        'is_call',
        'conv_price',
        'conv_value',
        'conv_prem',
        'dblow',
        'issue_size',
        'remain_size',
        'remain_cap',
        'turnover',
        'turnover_5',
        'cap_mv_rate',
        'list_date',
        'list_days',
        'conv_start_date',
        'left_conv_start_days',
        'conv_end_date',
        'left_years',
        'ytm',
        'pure_value',
        'bond_prem',
        'option_value',
        'theory_value',
        'theory_bias',
        'rating',
        'yy_rating',
        'orgform',
        'area',
        'industry_1',
        'industry_2',
        'industry_3',
        'maturity_put_price',
        'maturity',
        'popularity_ranking',
        'pct_chg_5',
        'pct_chg_5_stk',
        'alpha_pct_chg_5',
        'theory_conv_prem',
        'mod_conv_prem',
        'open_pct_chg',
        'high_pct_chg',
        'low_pct_chg']
    
    return all_factors

def objective(trial, df, all_factors):
    """优化目标函数"""
    # 优化价格范围
    price_min = trial.suggest_categorical("price_min", PRICE_MIN_RANGE)
    price_max = trial.suggest_categorical("price_max", PRICE_MAX_RANGE)
    
    # 优化因子数量
    num_factors = trial.suggest_int("num_factors", MIN_FACTORS, MAX_FACTORS)
    
    # 选择因子组合
    selected_factors = trial.suggest_categorical("selected_factors", 
                                               list(range(len(all_factors_combinations[num_factors]))))
    factor_indices = all_factors_combinations[num_factors][selected_factors]
    
    # 构建因子配置
    rank_factors = []
    for i, idx in enumerate(factor_indices):
        factor_name = all_factors[idx]
        factor_info = {
            'name': factor_name,
            'weight': trial.suggest_int(f"factor{i}_weight", 1, 5),
            'ascending': trial.suggest_categorical(f"factor{i}_ascending", [True, False])
        }
        rank_factors.append(factor_info)
    
    # 计算年化收益率
    try:
        cagr = cal_cagr(df, START_DATE, END_DATE, HOLD_NUM, THRESHOLD_NUM, price_min, price_max, rank_factors)
        
        # 记录每次试验结果
        trial.set_user_attr("rank_factors", rank_factors)
        trial.set_user_attr("price_min", price_min)
        trial.set_user_attr("price_max", price_max)
        
        return cagr
    except Exception as e:
        print(f"计算CAGR时出错: {e}")
        return -1.0  # 返回一个很差的值

def run_optimization(df):
    """运行优化过程"""
    # 创建研究对象
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage_name = f"{RESULTS_DIR}/optuna_study_{timestamp}.db"
    study_name = f"cb_optimization_{timestamp}"
    
    study = optuna.create_study(
        study_name=study_name,
        storage=f"sqlite:///{storage_name}",
        sampler=optuna.samplers.TPESampler(seed=42),
        direction="maximize",
        load_if_exists=True
    )
    
    # 开始优化
    start_time = time.time()
    print(f"开始优化，迭代次数: {N_TRIALS}，并行任务数: {N_JOBS}")
    
    study.optimize(
        lambda trial: objective(trial, df, get_all_factors()),
        n_trials=N_TRIALS,
        n_jobs=N_JOBS,
        show_progress_bar=True
    )
    
    elapsed_time = time.time() - start_time
    print(f"优化完成，耗时: {elapsed_time:.2f} 秒")
    
    # 保存结果
    best_params = study.best_params
    best_value = study.best_value
    best_trial = study.best_trial
    
    # 获取最佳因子组合
    best_rank_factors = best_trial.user_attrs["rank_factors"]
    best_price_min = best_trial.user_attrs["price_min"]
    best_price_max = best_trial.user_attrs["price_max"]
    
    print("\n" + "="*50)
    print("最优参数:")
    print(f"价格范围: {best_price_min} - {best_price_max}")
    print("因子组合:")
    for i, factor in enumerate(best_rank_factors):
        print(f"  {i+1}. {factor['name']} (权重: {factor['weight']}, 排序方向: {'降序' if not factor['ascending'] else '升序'})")
    print(f"最优年化收益率: {best_value:.4f}")
    print("="*50)
    
    # 保存最佳模型
    model_path = f"{RESULTS_DIR}/best_model_{timestamp}.pkl"
    model_data = {
        "best_params": best_params,
        "best_value": best_value,
        "best_rank_factors": best_rank_factors,
        "best_price_min": best_price_min,
        "best_price_max": best_price_max,
        "timestamp": timestamp
    }
    joblib.dump(model_data, model_path)
    print(f"最佳模型已保存至: {model_path}")
    
    # 保存前10个最佳试验
    top_trials = sorted(study.trials, key=lambda t: t.value if t.value is not None else float('-inf'), reverse=True)[:10]
    
    print("\n前10个最佳试验:")
    for i, trial in enumerate(top_trials):
        if trial.value is not None:
            rank_factors = trial.user_attrs.get("rank_factors", "未记录")
            price_min = trial.user_attrs.get("price_min", "未记录")
            price_max = trial.user_attrs.get("price_max", "未记录")
            
            print(f"\n第{i+1}名 - 年化收益率: {trial.value:.4f}")
            print(f"价格范围: {price_min} - {price_max}")
            print("因子组合:")
            for j, factor in enumerate(rank_factors):
                print(f"  {j+1}. {factor['name']} (权重: {factor['weight']}, 排序方向: {'降序' if not factor['ascending'] else '升序'})")
    
    return study, model_data

def generate_factor_combinations(all_factors):
    """为每个因子数量生成所有可能的组合"""
    combinations_dict = {}
    
    for num in range(MIN_FACTORS, MAX_FACTORS + 1):
        # 限制组合数量，避免内存溢出
        max_combinations = 1000
        all_combinations = list(itertools.combinations(range(len(all_factors)), num))
        
        if len(all_combinations) > max_combinations:
            # 随机采样组合
            np.random.seed(42)
            indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
            combinations_dict[num] = [all_combinations[i] for i in indices]
        else:
            combinations_dict[num] = all_combinations
            
        print(f"因子数量 {num}: 生成了 {len(combinations_dict[num])} 个组合")
        
    return combinations_dict

if __name__ == "__main__":
    # 加载数据
    df, index = load_data()
    
    # 获取所有因子
    all_factors = get_all_factors()
    print(f"可用因子总数: {len(all_factors)}")
    
    # 生成因子组合
    print("正在生成因子组合...")
    all_factors_combinations = generate_factor_combinations(all_factors)
    
    # 运行优化
    # study, best_model = run_optimization(df)
    
    print("\n优化完成!")
