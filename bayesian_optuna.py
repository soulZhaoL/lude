import optuna
import pandas as pd

# 你之前的导入和数据加载代码...
from more_factor_test_origin_code import cal_cagr

df = pd.read_parquet('cb_data.pq')
index = pd.read_parquet('index.pq')

# 基础设置
start_date = '20220801'  # 开始日期
end_date = '20240325'  # 结束日期

# 参数空间定义
factors = ['pre_close', 'open', 'high', 'low', 'close', 'pct_chg', 'vol',#7
           'amount', 'volatility_stk','mod_conv_prem','remain_cap','conv_prem',#12
           'turnover','theory_value','amount','option_value','dblow',#17
           'theory_bias','ytm','cap_mv_rate','pure_value','bond_prem',#22
           'remain_size','theory_conv_prem','pb','pe_ttm','ps_ttm']#27

def objective(trial):
    # 使用 Optuna 定义参数空间
    factor_ids = [trial.suggest_int(f'factor{i}_id', 0, len(factors) - 1) for i in range(1, 5)]
    if len(set(factor_ids)) < 4:
        return -1e6  # 如果因子 ID 重复，则返回一个大的数值作为惩罚

    rank_factors = []
    for i in range(1, 5):
        factor_info = {
            'name': factors[factor_ids[i - 1]],
            'weight': trial.suggest_categorical(f'factor{i}_weight', [1, 2, 3, 4, 5]),
            'ascending': trial.suggest_categorical(f'factor{i}_ascending', [True, False])
        }
        rank_factors.append(factor_info)

    return cal_cagr(df, start_date, end_date, rank_factors)


study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=1313), direction='maximize')
study.optimize(objective, n_trials=5)

# 打印最优参数
best_params = study.best_params
best_value = study.best_value
print("最优参数：", best_params)
print("最优参数下的目标函数值：", best_value)


# 定义转换函数
def transform_params(best_params, factors):
    best_factors_list = []
    for i in range(1, 5):
        factor = {
            'name': factors[best_params[f'factor{i}_id']],
            'weight': best_params[f'factor{i}_weight'],
            # Assuming you want to invert the 'ascending' boolean based on user expectation
            'ascending': not best_params[f'factor{i}_ascending']
        }
        best_factors_list.append(factor)
    return best_factors_list


# 调用函数并打印结果
transformed_params = transform_params(best_params, factors)
transformed_params
