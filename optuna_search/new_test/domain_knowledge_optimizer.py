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
import time

# 创建结果目录
RESULTS_DIR = "optimization_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

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
    parser.add_argument('--n_jobs', type=int, default=5, help='并行任务数')
    parser.add_argument('--strategy', type=str, default='multistage', 
                        choices=['domain', 'prescreen', 'multistage', 'filter'],
                        help='优化策略: domain(领域知识分组), prescreen(预筛选), multistage(多阶段), filter(过滤冗余)')
    
    return parser.parse_args()

def load_data():
    """加载数据并添加自定义因子"""
    print("正在加载数据...")
    df = pd.read_parquet('cb_data.pq')
    
    # print("正在计算自定义因子...")
    # df = add_custom_factors(df)
    
    return df

def domain_knowledge_factors():
    """基于领域知识对因子进行分类"""
    # 基础因子 - 溢价与价值相关
    premium_value_factors = [
        'conv_prem',         # 转股溢价率
        'theory_conv_prem',  # 理论溢价率
        'mod_conv_prem',     # 修正溢价率
        'pure_value',        # 纯债价值
        'bond_prem',         # 纯债溢价率
        'conv_value',        # 转股价值
        'option_value',      # 期权价值
        'theory_value',      # 理论价值
        'theory_bias',       # 理论偏离度
        'dblow'              # 双低
    ]

    # 基础因子 - 价格相关
    price_factors = [
        'close',       # 收盘价
        'pre_close',   # 前收盘价
        'open',        # 开盘价
        'high',        # 最高价
        'low',         # 最低价
        'conv_price'   # 转股价格
    ]

    # 基础因子 - 交易相关
    trading_factors = [
        'amount',       # 成交额(万)
        'vol',          # 成交量(手)
        'pct_chg',      # 涨跌幅
        'turnover',     # 换手率
        'cap_mv_rate'   # 转债市占比
    ]

    # 基础因子 - 规模与期限相关
    scale_maturity_factors = [
        'issue_size',   # 发行规模(亿)
        'remain_size',  # 剩余规模(亿)
        'remain_cap',   # 剩余市值(亿)
        'list_days',    # 上市天数
        'left_years'    # 剩余年限
    ]

    # 基础因子 - 收益与强赎相关
    redeem_yield_factors = [
        'ytm'                  # 到期收益率
    ]

    # 历史类因子 - 涨跌与超额收益
    historical_return_factors = [
        'pct_chg_5',       # 5日涨跌幅
        'pct_chg_5_stk',   # 正股5日涨跌幅
        'alpha_pct_chg_5'  # 5日超额涨跌幅
    ]

    # 历史类因子 - 价格乖离与均线
    historical_price_bias_factors = [
        'bias_5',      # 5日乖离率
        'close_ma_5'   # 5日均价
    ]

    # 历史类因子 - 交易与波动
    historical_trading_volatility_factors = [
        'vol_5',           # 5日成交量
        'amount_5',        # 5日成交额
        'turnover_5',      # 5日换手率
        'volatility',      # 年化波动率
        'volatility_stk'   # 正股年化波动率
    ]

    # 正股相关因子 - 正股价格与交易
    stock_price_trading_factors = [
        'close_stk',    # 正股收盘价
        'pct_chg_stk',  # 正股涨跌幅
        'amount_stk',   # 正股成交额(万)
        'vol_stk'       # 正股成交量
    ]

    # 正股相关因子 - 正股规模
    stock_scale_factors = [
        'total_mv',  # 正股总市值(亿)
        'circ_mv'    # 正股流通市值(亿)
    ]

    # 正股相关因子 - 正股估值与财务指标
    stock_valuation_factors = [
        'pb',               # 市净率
        'pe_ttm',           # 市盈率TTM
        'ps_ttm',           # 市销率TTM
        'debt_to_assets',   # 资产负债率
        'dv_ratio'          # 股息率
    ]
    
    # 组合所有因子类别
    all_categories = {
        '溢价与价值相关': premium_value_factors,
        '价格相关': price_factors,
        '交易相关': trading_factors,
        '规模与期限相关': scale_maturity_factors,
        '收益与强赎相关': redeem_yield_factors,
        '涨跌与超额收益': historical_return_factors,
        '价格乖离与均线': historical_price_bias_factors,
        '交易与波动': historical_trading_volatility_factors,
        '正股价格与交易': stock_price_trading_factors,
        '正股规模': stock_scale_factors,
        '正股估值与财务指标': stock_valuation_factors
    }
    
    return all_categories

def domain_knowledge_combinations(df, num_factors, max_combinations=50000):
    """使用领域知识生成因子组合"""
    # 获取所有因子分类
    factor_categories = domain_knowledge_factors()
    
    # 获取数据中实际存在的因子
    available_factors = df.columns.tolist()
    
    # 优化后的因子分类（只保留数据中存在的因子）
    optimized_categories = {}
    
    for category_name, factors in factor_categories.items():
        existing_factors = [f for f in factors if f in available_factors]
        if existing_factors:
            optimized_categories[category_name] = existing_factors
            print(f"{category_name}: 找到 {len(existing_factors)} 个有效因子")
    
    # 从每个分类中挑选因子组合
    total_categories = len(optimized_categories)
    combinations = []
    
    # 计算每组分配多少个组合名额
    combinations_per_category = max_combinations // total_categories
    remaining_slots = max_combinations % total_categories
    
    # 生成所有可能的单分类和跨分类的因子组合
    all_factors = []
    factor_to_category = {}
    
    for category, factors in optimized_categories.items():
        for factor in factors:
            all_factors.append(factor)
            factor_to_category[factor] = category
    
    # 构建每个分类内部的因子组合
    for category_name, factors in optimized_categories.items():
        # 如果该分类的因子不足指定数量，跳过
        if len(factors) < num_factors:
            print(f"分类 {category_name} 因子数量不足 {num_factors} 个，跳过内部组合生成")
            continue
        
        # 从该分类中选择num_factors个因子的所有可能组合
        category_combinations = list(itertools.combinations(factors, num_factors))
        
        # 如果组合数量超过分配的名额，随机抽样
        if len(category_combinations) > combinations_per_category:
            np.random.seed(42 + hash(category_name) % 1000)  # 使用分类名作为随机种子的一部分
            indices = np.random.choice(len(category_combinations), combinations_per_category, replace=False)
            category_combinations = [category_combinations[i] for i in indices]
        
        combinations.extend(category_combinations)
        print(f"分类 {category_name} 内部生成了 {len(category_combinations)} 个因子组合")
    
    # 计算已生成的组合数量
    current_combinations = len(combinations)
    
    # 计算需要生成的跨分类组合数量
    cross_combination_slots = max_combinations - current_combinations
    
    if cross_combination_slots > 0:
        print(f"生成 {cross_combination_slots} 个跨分类因子组合")
        
        # 交叉组合：从不同分类中各选取一部分因子
        cross_category_combinations = []
        
        for _ in range(cross_combination_slots * 10):  # 生成更多组合再随机抽样
            selected_factors = []
            
            # 随机选择不同分类的因子
            categories = list(optimized_categories.keys())
            np.random.shuffle(categories)
            
            for i in range(num_factors):
                category = categories[i % len(categories)]
                factors = optimized_categories[category]
                
                if not factors:
                    continue
                
                # 随机选择一个未被选择的因子
                available = [f for f in factors if f not in selected_factors]
                if not available:
                    continue
                
                factor = np.random.choice(available)
                selected_factors.append(factor)
            
            # 只有当选择了足够数量的因子时才添加组合
            if len(selected_factors) == num_factors:
                cross_category_combinations.append(tuple(selected_factors))
        
        # 去重
        cross_category_combinations = list(set(cross_category_combinations))
        
        # 如果生成的组合数量超过需要的数量，随机选择
        if len(cross_category_combinations) > cross_combination_slots:
            np.random.seed(42)
            indices = np.random.choice(len(cross_category_combinations), cross_combination_slots, replace=False)
            cross_category_combinations = [cross_category_combinations[i] for i in indices]
        
        combinations.extend(cross_category_combinations)
    
    # 进行最终的去重
    combinations = list(set(combinations))
    
    # 打印结果
    print(f"共生成了 {len(combinations)} 个因子组合")
    
    # 将因子组合转换为索引形式
    index_mapping = {factor: idx for idx, factor in enumerate(all_factors)}
    index_combinations = []
    
    for combo in combinations:
        try:
            indices = [index_mapping[factor] for factor in combo]
            index_combinations.append(tuple(indices))
        except KeyError:
            continue
    
    return all_factors, index_combinations

def prescreen_factors(df, factors, top_n=30, args=None):
    """预筛选最有潜力的单因子"""
    factor_performance = []
    
    print("开始单因子表现预筛选...")
    for i, factor in enumerate(factors):
        if factor not in df.columns:
            continue
            
        # 尝试正向和反向排序
        for ascending in [True, False]:
            try:
                # 配置单因子测试
                rank_factors = [{'name': factor, 'weight': 5, 'ascending': ascending}]
                
                # 计算表现
                cagr = cal_cagr(df, args.start_date, args.end_date, args.hold_num, 
                               None, args.price_min, args.price_max, rank_factors)
                
                factor_performance.append({
                    'factor': factor,
                    'ascending': ascending,
                    'cagr': cagr
                })
                
                print(f"因子 {i+1}/{len(factors)}: {factor} ({'升序' if ascending else '降序'}) - CAGR: {cagr:.4f}")
            except Exception as e:
                print(f"因子 {factor} 测试失败: {e}")
    
    # 按表现排序
    factor_performance.sort(key=lambda x: x['cagr'], reverse=True)
    
    # 打印表现最好的因子
    print("\n表现最好的因子:")
    for i, item in enumerate(factor_performance[:top_n]):
        print(f"{i+1}. {item['factor']} ({'升序' if item['ascending'] else '降序'}) - CAGR: {item['cagr']:.4f}")
    
    # 返回表现最好的top_n个因子
    best_factors = []
    best_directions = {}
    
    for item in factor_performance[:top_n]:
        best_factors.append(item['factor'])
        best_directions[item['factor']] = item['ascending']
    
    return best_factors, best_directions

def filter_redundant_factors(factors, threshold=0.8):
    """根据业务知识过滤掉冗余因子"""
    redundant_groups = [
        # 溢价率相关冗余组
        ['conv_prem', 'theory_conv_prem', 'mod_conv_prem'], 
        
        # 价值相关冗余组
        ['pure_value', 'theory_value', 'conv_value'], 
        
        # 价格相关冗余组
        ['close', 'pre_close', 'open', 'high', 'low'],  
        
        # 交易量相关冗余组
        ['vol', 'vol_5'],  
        ['amount', 'amount_5'],  
        ['turnover', 'turnover_5'],  
        
        # 正股相关冗余组
        ['close_stk', 'pct_chg_stk'],
        ['amount_stk', 'vol_stk'],
        ['total_mv', 'circ_mv'],
        
        # 估值相关冗余组
        ['pe_ttm', 'pb', 'ps_ttm'],
        
        # 技术指标冗余组
        ['pc1', 'pc3', 'pc5', 'pc7'],  # 价格动量因子组
        ['rsi1', 'rsi3', 'rsi5', 'rsi7'],  # RSI因子组
        ['stoch1', 'stoch2', 'stoch3'],  # 随机指标因子组
        ['macd', 'macd_signal', 'macd_diff'],  # MACD因子组
        ['momentum3', 'momentum6', 'momentum12'],  # 动量因子组
        ['velocity3', 'velocity5', 'velocity7'],  # 速度因子组
        ['volatility', 'volatility_stk'],  # 波动率因子组
        ['dema5', 'dema21'],  # 双指数移动平均线因子组
        
        # 历史类冗余组
        ['pct_chg_5', 'pct_chg_5_stk', 'alpha_pct_chg_5'],
        ['bias_5', 'close_ma_5'],
        
        # 规模期限相关冗余组
        ['issue_size', 'remain_size', 'remain_cap'],
        ['list_days', 'left_years']
        
    ]
    
    # 从每组保留一个代表性因子
    to_keep = []
    for group in redundant_groups:
        present_factors = [f for f in group if f in factors]
        if present_factors:
            to_keep.append(present_factors[0])  # 保留第一个出现的因子
    
    # 添加未分组的因子
    grouped_factors = [item for group in redundant_groups for item in group]
    for factor in factors:
        if factor not in grouped_factors:
            to_keep.append(factor)
    
    print(f"通过冗余分析，从 {len(factors)} 个因子精简为 {len(to_keep)} 个因子")
    return to_keep

def multistage_optimization(df, factors, num_factors, args, max_combinations=50000):
    """多阶段优化策略"""
    print("启动多阶段优化策略...")
    
    # 第一阶段：随机探索
    first_stage_trials = max(100, args.n_trials // 3)  # 使用约1/3的迭代次数进行初始探索
    print(f"第一阶段：随机探索 {first_stage_trials} 次迭代")
    
    # 为第一阶段创建一个新的optuna研究
    first_stage_study_name = f"cb_optimization_multistage_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    first_stage_storage = f"sqlite:///{RESULTS_DIR}/{first_stage_study_name}.db"
    
    # 第一阶段使用随机采样器进行广泛探索
    first_stage_study = optuna.create_study(
        study_name=first_stage_study_name,
        storage=first_stage_storage,
        direction='maximize',
        sampler=optuna.samplers.RandomSampler(seed=42)
    )
    
    # 从所有因子中随机选择组合
    print("生成随机因子组合...")
    all_combinations = list(itertools.combinations(range(len(factors)), num_factors))
    if len(all_combinations) > max_combinations // 2:
        np.random.seed(42)
        indices = np.random.choice(len(all_combinations), max_combinations // 2, replace=False)
        first_stage_combinations = [all_combinations[i] for i in indices]
    else:
        first_stage_combinations = all_combinations
    print(f"第一阶段随机组合数量: {len(first_stage_combinations)}")
    
    # 启动第一阶段优化
    first_stage_study.optimize(
        lambda trial: objective(trial, df, factors, first_stage_combinations, args),
        n_trials=first_stage_trials,
        n_jobs=args.n_jobs
    )
    
    # 收集第一阶段的最佳试验
    best_trials = first_stage_study.trials_dataframe()
    best_trials = best_trials.sort_values('value', ascending=False)
    
    # 保存第一阶段的最佳结果
    first_stage_best_value = first_stage_study.best_value
    first_stage_best_params = first_stage_study.best_params
    first_stage_best_trial = first_stage_study.best_trial
    
    print(f"第一阶段最佳年化收益率: {first_stage_best_value:.4f}")
    print("第一阶段最佳因子组合:")
    combination_idx = first_stage_best_params['combination_idx']
    factor_indices = first_stage_combinations[combination_idx]
    for i, idx in enumerate(factor_indices):
        factor_name = factors[idx]
        weight = first_stage_best_params[f'factor{i}_weight']
        ascending = first_stage_best_params[f'factor{i}_ascending']
        print(f"  {i+1}. {factor_name}")
        print(f"     - 权重: {weight}")
        print(f"     - 排序方向: {'升序' if ascending else '降序'}")
    
    # 第二阶段：聚焦优化
    # 从第一阶段的前N个最佳试验中提取有效因子
    top_n_trials = min(20, len(best_trials))
    print(f"第二阶段：基于第一阶段前 {top_n_trials} 个最佳结果进行聚焦优化")
    
    good_factor_counts = {}
    factor_direction_preference = {}
    factor_weight_preference = {}
    
    # 统计第一阶段表现好的因子
    for i in range(top_n_trials):
        if i >= len(best_trials):
            break
            
        trial_params = {}
        for param, value in best_trials.iloc[i].items():
            if param.startswith('params_'):
                param_name = param.replace('params_', '')
                trial_params[param_name] = value
        
        if 'combination_idx' not in trial_params:
            continue
            
        combination_idx = int(trial_params['combination_idx'])
        if combination_idx >= len(first_stage_combinations):
            continue
            
        factor_indices = first_stage_combinations[combination_idx]
        
        for j, idx in enumerate(factor_indices):
            factor_name = factors[idx]
            
            # 统计因子出现次数
            if factor_name not in good_factor_counts:
                good_factor_counts[factor_name] = 0
                factor_direction_preference[factor_name] = {'asc': 0, 'desc': 0}
                factor_weight_preference[factor_name] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                
            good_factor_counts[factor_name] += 1
            
            # 统计排序方向偏好
            ascending_param = f'factor{j}_ascending'
            if ascending_param in trial_params:
                if trial_params[ascending_param]:
                    factor_direction_preference[factor_name]['asc'] += 1
                else:
                    factor_direction_preference[factor_name]['desc'] += 1
            
            # 统计权重偏好
            weight_param = f'factor{j}_weight'
            if weight_param in trial_params:
                weight = int(trial_params[weight_param])
                if weight in factor_weight_preference[factor_name]:
                    factor_weight_preference[factor_name][weight] += 1
    
    # 按出现次数排序因子
    popular_factors = sorted(good_factor_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 选择前top_n_factors个常用因子
    top_factors = []
    for factor_name, count in popular_factors[:min(len(popular_factors), 20)]:
        direction = 'desc' if factor_direction_preference[factor_name]['desc'] > factor_direction_preference[factor_name]['asc'] else 'asc'
        weight = max(factor_weight_preference[factor_name].items(), key=lambda x: x[1])[0]
        top_factors.append((factor_name, direction, weight))
        print(f"常用因子 {factor_name}: 出现 {count} 次, 偏好方向: {direction}, 偏好权重: {weight}")
    
    # 生成第二阶段的组合
    second_stage_combinations = []
    
    # 1. 直接包含第一阶段的最佳组合
    best_combo_params = {}
    best_combo_indices = []
    for i, idx in enumerate(factor_indices):
        factor_name = factors[idx]
        best_combo_indices.append(factors.index(factor_name))
        best_combo_params[f'factor{i}_weight'] = first_stage_best_params[f'factor{i}_weight']
        best_combo_params[f'factor{i}_ascending'] = first_stage_best_params[f'factor{i}_ascending']
    
    # 确保最佳组合在第二阶段的组合中
    second_stage_combinations.append(tuple(best_combo_indices))
    
    # 2. 从top_factors中选择不同的组合
    top_factor_names = [f[0] for f in top_factors]
    top_factor_indices = [factors.index(f) for f in top_factor_names if f in factors]
    
    if len(top_factor_indices) >= num_factors:
        # 生成top因子的组合
        top_factor_combos = list(itertools.combinations(top_factor_indices, num_factors))
        second_stage_combinations.extend(top_factor_combos)
    
    # 3. 混合组合：在已知好因子的基础上组合其他因子
    for i in range(min(10, len(top_factor_indices))):
        base_factor_idx = top_factor_indices[i]
        remaining_factors = [idx for idx in range(len(factors)) if idx != base_factor_idx]
        
        # 为每个好因子随机添加其他因子形成组合
        for _ in range(200):  # 每个base因子生成200个组合
            combo = [base_factor_idx]
            for _ in range(num_factors - 1):
                idx = np.random.choice(remaining_factors)
                while idx in combo:  # 确保不重复
                    idx = np.random.choice(remaining_factors)
                combo.append(idx)
            second_stage_combinations.append(tuple(sorted(combo)))
    
    # 移除重复组合
    second_stage_combinations = list(set(second_stage_combinations))
    
    # 限制组合数量
    if len(second_stage_combinations) > max_combinations:
        np.random.seed(42)
        indices = np.random.choice(len(second_stage_combinations), max_combinations, replace=False)
        second_stage_combinations = [second_stage_combinations[i] for i in indices]
    
    print(f"第二阶段优化组合数量: {len(second_stage_combinations)}")
    
    # 创建第二阶段研究
    second_stage_study_name = f"cb_optimization_multistage_phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    second_stage_storage = f"sqlite:///{RESULTS_DIR}/{second_stage_study_name}.db"
    
    # 第二阶段使用TPE采样器进行精细优化
    sampler = optuna.samplers.TPESampler(seed=42)
    second_stage_study = optuna.create_study(
        study_name=second_stage_study_name,
        storage=second_stage_storage,
        direction='maximize',
        sampler=sampler
    )
    
    # 添加第一阶段的最佳结果作为一个试验点
    # 需要重新映射combination_idx，确保它在第二阶段组合范围内
    first_stage_params_adjusted = first_stage_best_params.copy()
    
    # 获取第一阶段最佳组合的因子索引
    first_best_combination = first_stage_combinations[first_stage_best_params['combination_idx']]
    
    # 检查这个组合是否已经在第二阶段组合中
    if first_best_combination in second_stage_combinations:
        # 找到最佳组合在第二阶段组合列表中的索引
        first_stage_params_adjusted['combination_idx'] = second_stage_combinations.index(first_best_combination)
    else:
        # 如果不在，将其添加到第二阶段组合列表的开头
        second_stage_combinations.insert(0, first_best_combination)
        first_stage_params_adjusted['combination_idx'] = 0
    
    # 确保使用调整后的参数
    second_stage_study.enqueue_trial(first_stage_params_adjusted)
    
    # 启动第二阶段优化
    second_stage_trials = args.n_trials - first_stage_trials
    print(f"第二阶段：精细优化 {second_stage_trials} 次迭代")
    second_stage_study.optimize(
        lambda trial: objective(trial, df, factors, second_stage_combinations, args),
        n_trials=second_stage_trials,
        n_jobs=args.n_jobs
    )
    
    # 比较两个阶段的结果，取最好的
    if first_stage_best_value > second_stage_study.best_value:
        print(f"注意：第一阶段结果 ({first_stage_best_value:.4f}) 优于第二阶段 ({second_stage_study.best_value:.4f})")
        print("使用第一阶段的最佳结果")
        # 创建合并的研究结果
        final_study_name = f"cb_optimization_multistage_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        final_storage = f"sqlite:///{RESULTS_DIR}/{final_study_name}.db"
        final_study = optuna.create_study(
            study_name=final_study_name,
            storage=final_storage,
            direction='maximize'
        )
        # 将第一阶段的最佳参数作为一个试验点添加到最终研究中
        final_study.enqueue_trial(first_stage_best_params)
        final_study.optimize(lambda trial: 0, n_trials=1)  # 只是为了记录参数
        
        # 返回第一阶段的最佳组合和所有组合
        return factors, first_stage_combinations + second_stage_combinations, final_study
    else:
        print(f"第二阶段结果 ({second_stage_study.best_value:.4f}) 优于第一阶段 ({first_stage_best_value:.4f})")
        print("使用第二阶段的最佳结果")
        # 返回第二阶段的组合和所有组合
        return factors, second_stage_combinations, second_stage_study

def choose_strategy(strategy, df, factors, num_factors, args, max_combinations=50000):
    """根据选择的策略生成因子组合"""
    if strategy == 'domain':
        return domain_knowledge_combinations(df, num_factors, max_combinations)
    elif strategy == 'prescreen':
        best_factors, _ = prescreen_factors(df, factors, top_n=30, args=args)
        # 使用预筛选的因子生成组合
        all_combinations = list(itertools.combinations(range(len(best_factors)), num_factors))
        print(f"预筛选因子组合数量: {len(all_combinations)}")
        if len(all_combinations) > max_combinations:
            np.random.seed(42)
            indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
            all_combinations = [all_combinations[i] for i in indices]
        return best_factors, all_combinations
    elif strategy == 'multistage':
        factors, combinations, study = multistage_optimization(df, factors, num_factors, args, max_combinations)
        return factors, combinations, study
    elif strategy == 'filter':
        filtered_factors = filter_redundant_factors(factors)
        all_combinations = list(itertools.combinations(range(len(filtered_factors)), num_factors))
        if len(all_combinations) > max_combinations:
            np.random.seed(42)
            indices = np.random.choice(len(all_combinations), max_combinations, replace=False)
            all_combinations = [all_combinations[i] for i in indices]
        return filtered_factors, all_combinations
    else:
        raise ValueError(f"不支持的策略: {strategy}")

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
            'weight': trial.suggest_int(f"factor{i}_weight", 1, 3),
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
            return optuna.samplers.CmaEsSampler(seed=42, warn_independent_sampling=False)
        except (ImportError, ModuleNotFoundError):
            print("警告: cmaes 模块未安装，自动切换为 TPE 采样器")
            print("如需使用 CMA-ES，请运行: pip install cmaes")
            return optuna.samplers.TPESampler(seed=42)
    else:
        raise ValueError(f"不支持的优化方法: {method}")

def run_optimization(df, args):
    """运行优化过程"""
    # 获取所有可用因子
    all_factors = [
        'conv_prem',
        'theory_conv_prem',
        'mod_conv_prem',
        'close',
        'dblow',
        'pure_value',
        'bond_prem',
        'issue_size',
        'remain_size',
        'remain_cap',
        'pre_close',
        'open',
        'high',
        'low',
        'amount',
        'vol',
        'conv_price',
        'conv_value',
        'option_value',
        'theory_value',
        'theory_bias',
        'pct_chg',
        'turnover',
        'cap_mv_rate',
        'list_days',
        'left_years',
        'ytm',
        'pct_chg_5',
        'pct_chg_5_stk',
        'bias_5',
        'close_ma_5',
        'alpha_pct_chg_5',
        'vol_5',
        'amount_5',
        'turnover_5',
        'volatility',
        'volatility_stk',
        'close_stk',
        'pct_chg_stk',
        'amount_stk',
        'vol_stk',
        'total_mv',
        'circ_mv',
        'pb',
        'pe_ttm',
        'ps_ttm',
        'debt_to_assets',
        'dv_ratio',
    ]
    print(f"可用因子总数: {len(all_factors)}")
    
    # 根据策略生成因子组合
    if args.strategy == 'multistage':
        factors, factor_combinations, study = choose_strategy(
            args.strategy, df, all_factors, args.n_factors, args
        )
    else:
        factors, factor_combinations = choose_strategy(
            args.strategy, df, all_factors, args.n_factors, args
        )
        study = None
    
    print(f"选择的因子总数: {len(factors)}")
    print(f"生成的组合总数: {len(factor_combinations)}")
    
    # 创建时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建研究对象
    study_name = f"cb_optimization_{args.strategy}_{args.method}_{args.n_factors}factors_{timestamp}"
    storage_path = f"{RESULTS_DIR}/{study_name}.db"
    
    # 创建采样器
    sampler = create_sampler(args.method)
    
    if study is None:
        study = optuna.create_study(
            study_name=study_name,
            storage=f"sqlite:///{storage_path}",
            sampler=sampler,
            direction="maximize"
        )
    
    # 开始优化
    start_time = time.time()
    print(f"开始使用 {args.method} 方法优化 {args.n_factors} 个因子组合...")
    print(f"优化参数: 迭代次数={args.n_trials}, 持仓数={args.hold_num}, 价格区间={args.price_min}-{args.price_max}")
    
    study.optimize(
        lambda trial: objective(trial, df, factors, factor_combinations, args),
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        show_progress_bar=True
    )
    
    end_time = time.time()
    print(f"优化完成，耗时 {(end_time - start_time)/60:.2f} 分钟")
    
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
        print(f"     - 排序方向: {'升序' if factor['ascending'] else '降序'}")
    print("="*60)
    
    # 保存最佳模型
    model_path = f"{RESULTS_DIR}/best_model_{args.strategy}_{args.method}_{args.n_factors}factors_{timestamp}.pkl"
    model_data = {
        "study_name": study_name,
        "best_value": best_value,
        "best_rank_factors": best_rank_factors,
        "optimization_method": args.method,
        "strategy": args.strategy,
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
                print(f"   - {factor['name']} (权重: {factor['weight']}, {'升序' if factor['ascending'] else '降序'})")
    
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
