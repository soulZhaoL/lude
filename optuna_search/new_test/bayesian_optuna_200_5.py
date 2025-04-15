import optuna
import pandas as pd
import itertools
from more_factor_test_origin_code import cal_cagr

# 基础设置
n_trials = 2000  # 迭代次数
n_jobs = 10  # 并行数量
start_date = '20220729'  # 开始日期
end_date = '20250328'  # 结束日期
num_factors = 3  # 因子数量
hold_num = 5  # 持仓数量
threshold_num = None  # 阈值轮动
price_min = 100  # 最小价格
price_max = 200  # 最大价格

# 参数空间定义
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

def load_data():
    """加载数据"""
    df = pd.read_parquet('cb_data.pq')
    index = pd.read_parquet('index.pq')
    return df, index

def decode_combination(encoded):
    """解码因子组合索引为因子名称列表"""
    return [factors[i] for i in encoded]

def objective(trial):
    """优化目标函数"""
    encoded_id = trial.suggest_int('encoded_id', 0, len(encoded_combinations) - 1)
    factor_ids = encoded_combinations[encoded_id]
    rank_factors = []
    decoded_factors = decode_combination(factor_ids)
    for i in range(num_factors):
        factor_info = {
            'name': decoded_factors[i],
            'weight': trial.suggest_categorical(f'factor{i + 1}_weight', [1, 2, 3, 4, 5]),
            'ascending': trial.suggest_categorical(f'factor{i + 1}_ascending', [True, False])
        }
        rank_factors.append(factor_info)

    cagr = cal_cagr(df, start_date, end_date, hold_num, threshold_num, price_min, price_max, rank_factors)
    # print("factor_combination:{}, cagr:{}".format(rank_factors, cagr))
    return cagr

def flexible_decode_combination(encoded_params):
    """从优化参数中解码出完整的因子组合信息"""
    # 解码因子组合索引
    factor_indices = combinations[encoded_params['encoded_id']]
    # 构建详细的因子组合列表
    rank_factors = []
    for i, index in enumerate(factor_indices):
        factor_info = {
            'name': factors[index],
            'weight': encoded_params[f'factor{i + 1}_weight'],
            'ascending': encoded_params[f'factor{i + 1}_ascending']
        }
        rank_factors.append(factor_info)

    return rank_factors

def run_optimization():
    """运行优化过程"""
    # 创建一个研究对象并指定TPESampler
    study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=888), direction='maximize')
    study.optimize(lambda trial: objective(trial), n_trials=n_trials, n_jobs=n_jobs)
    
    # 打印最优参数
    best_params = study.best_params
    best_value = study.best_value
    print("最优参数：", best_params)
    print("最优参数下的目标函数值：", best_value)
    
    # 解码最优参数
    factor_combination = flexible_decode_combination(best_params)
    print(factor_combination)
    print("最优参数下的目标函数值：", best_value)
    
    return study, factor_combination, best_value

if __name__ == "__main__":
    # 加载数据
    df, index = load_data()
    
    # 生成所有可能的因子组合
    combinations = list(itertools.combinations(range(len(factors)), num_factors))
    encoded_combinations = {i: combo for i, combo in enumerate(combinations)}
    
    # 运行优化
    study, best_factors, best_cagr = run_optimization()
