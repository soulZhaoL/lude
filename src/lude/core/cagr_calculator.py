"""
可转债CAGR计算器 - 精简版

本模块提供计算可转债组合CAGR的核心功能，支持止盈和非止盈两种模式。
基于more_factor_test_origin_code_none_threadhold.py精简而来，只保留核心计算逻辑。
"""

import os
import sys
import warnings

import pandas as pd
from numpy import nan
from lude.utils.logger import optimization_logger as logger

from lude.utils.cagr_utils import calculate_cagr_manually
from lude.config.paths import DATA_DIR

# 忽略警告
warnings.filterwarnings('ignore')

# 基础常量设置
SP = 0.06  # 盘中止盈条件，6%止盈
C_RATE = 2 / 1000  # 买卖一次花费的总佣金和滑点（双边）
threshold_num = None  # 轮动阈值


def calculate_bonds_cagr(df, start_date, end_date, hold_num, min_price, max_price,
                         rank_factors, threshold_num=None, filter_conditions=None,
                         check_overfitting=True, verbose_overfitting=False):
    """
    计算可转债组合的CAGR
    
    参数：
        df: 可转债数据DataFrame
        start_date: 开始日期，格式'YYYYMMDD'
        end_date: 结束日期，格式'YYYYMMDD'
        hold_num: 持有数量
        min_price: 最低价格筛选
        max_price: 最高价格筛选
        rank_factors: 排序因子，格式为[{'name': '因子名', 'weight': 权重, 'ascending': 排序方向}, ...]
        threshold_num: 轮动阈值，默认为None
        filter_conditions: 排除因子组合，格式为[{'factor': '因子名', 'operator': '>=', 'value': 阈值}, ...]
        check_overfitting: 是否进行过拟合检测，默认为True
        verbose_overfitting: 是否打印过拟合检测详细信息，默认为False
    
    返回：
        cagr: 使用手动计算法得到的CAGR值，如果检测到过拟合则返回惩罚值
        （可选）如果需要更多信息，可以返回详细结果字典
    """
    logger.info(f"rank_factors:{rank_factors}, filter_conditions:{filter_conditions}")
    # 数据筛选 - 按日期范围
    df = df[(df.index.get_level_values('trade_date') >= start_date) &
            (df.index.get_level_values('trade_date') <= end_date)]

    # 初始化过滤器
    df['filter'] = False

    # 计算收盘价百分比排名
    df['close_pct'] = df.groupby('trade_date')['close'].rank(pct=True)

    # 基础排除条件设置
    df.loc[df.is_call.isin(['已公告强赎', '公告到期赎回', '公告实施强赎',
                            '公告提示强赎', '已满足强赎条件']), 'filter'] = True  # 排除赎回状态
    df.loc[df.list_days <= 3, 'filter'] = True  # 排除新债
    df.loc[df.left_years < 0.5, 'filter'] = True  # 排除到期日小于0.5年的标的
    df.loc[df.amount < 1000, 'filter'] = True  # 排除成交额小于1000万
    df.loc[df.close > max_price, 'filter'] = True  # 排除价格过高
    df.loc[df.close < min_price, 'filter'] = True  # 排除价格过低
    
    # 应用排除因子组合过滤条件
    # if filter_conditions is None:
    #     # 如果没有提供排除因子，使用默认排除因子
    #     filter_conditions = [
    #         {'factor': 'amount', 'operator': '<', 'value': 1000},  # 默认排除成交额小于1000万
    #         {'factor': 'close', 'operator': '>', 'value': max_price},  # 默认排除价格过高
    #         {'factor': 'close', 'operator': '<', 'value': min_price},  # 默认排除价格过低
    #     ]
    
    # 应用动态排除因子条件
    if filter_conditions:
        for condition in filter_conditions:
            factor_name = condition['factor']
            operator = condition['operator']
            threshold = condition['value']
            
            if factor_name in df.columns:
                if operator == '>=':
                    df.loc[df[factor_name] >= threshold, 'filter'] = True
                elif operator == '>':
                    df.loc[df[factor_name] > threshold, 'filter'] = True
                elif operator == '<=':
                    df.loc[df[factor_name] <= threshold, 'filter'] = True
                elif operator == '<':
                    df.loc[df[factor_name] < threshold, 'filter'] = True
                elif operator == '==':
                    df.loc[df[factor_name] == threshold, 'filter'] = True
                elif operator == '!=':
                    df.loc[df[factor_name] != threshold, 'filter'] = True
                # print(f'应用排除条件: {factor_name} {operator} {threshold}')
            else:
                logger.warning(f'警告: 未找到排除因子【{factor_name}】, 跳过此条件')

    # 计算多因子得分和排名
    trade_date_group = df[df['filter'] == False].groupby('trade_date')

    # 应用每个因子并计算得分
    for factor in rank_factors:
        if factor['name'] in df.columns:
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(
                ascending=factor['ascending']) * factor['weight']
        else:
            logger.warning(f'未找到因子【{factor["name"]}】, 跳过')

    # 计算总得分和排名
    df['score'] = df[df.filter(like='score').columns].sum(axis=1, min_count=1)
    df['rank'] = df.groupby('trade_date')['score'].rank('first', ascending=False)

    # 阈值轮动
    if threshold_num:
        df.rename(columns={'rank': 'ori_rank'}, inplace=True)  # 记录原排名
        df['rank'] = nan  # 初始化排名
        df['mod_rank'] = nan  # 初始化修正排名
        RANK_INDEX = df.columns.get_loc('rank')  # 排名下标值
        ORI_RANK_INDEX = df.columns.get_loc('ori_rank')  # 原始排名下标值
        df.iloc[df.index.get_level_values(1) == df.index.get_level_values(1)[0], RANK_INDEX] = df.iloc[
            df.index.get_level_values(1) == df.index.get_level_values(1)[0], ORI_RANK_INDEX]  # 首日排名等于原排名

        trade_date_list = df.index.get_level_values('trade_date').unique()  # 交易日列表

        # 遍历每个交易日对排名进行处理
        for trade_date, _df in df.groupby('trade_date'):
            # 跳过首日
            if trade_date == df.index.get_level_values(1)[0]:
                continue
            last_trade_date = trade_date_list[trade_date_list.get_loc(trade_date) - 1]  # 上个交易日日期

            # 构建一个包含当日原始排名（ori_rank）、上个交易日排名（last_rank）、修正排名（mod_rank）和重新排序后的最终排名（rank）的_ranks_df
            _ranks_df = df.loc[df.index.get_level_values('trade_date') == trade_date, ['ori_rank']] \
                .merge(df.loc[df.index.get_level_values('trade_date') == last_trade_date, 'rank'], how='left',
                       on='code') \
                .rename(columns={'rank': 'last_rank'})

            # 若上一交易日排名last_rank <= hold_num，今日mod_rank = ori_rank - threshold_num，否则今日mod_rank = ori_rank
            _ranks_df['mod_rank'] = (_ranks_df['ori_rank'] - threshold_num).where(_ranks_df['last_rank'] <= hold_num,
                                                                                  _ranks_df['ori_rank'])
            # 根据mod_rank 重新排序出今日rank
            _ranks_df['rank'] = _ranks_df['mod_rank'].rank(method='first')

            # 将今日最终排名rank写入原df
            df.loc[df.index.get_level_values('trade_date') == trade_date, ['mod_rank', 'rank']] = _ranks_df[
                ['mod_rank', 'rank']].values

    # 添加日内止盈逻辑
    code_group = df.groupby('code')

    # 计算次日价格和默认收益率
    df['aft_open'] = code_group.open.shift(-1)  # 计算次日开盘价
    df['aft_close'] = code_group.close.shift(-1)  # 计算次日收盘价
    df['aft_high'] = code_group.high.shift(-1)  # 计算次日最高价
    df['time_return'] = code_group.pct_chg.shift(-1)  # 先计算不止盈情况的收益率
    df['SFZY'] = '未满足止盈'  # 先记录默认情况

    # 根据参数控制是否应用止盈逻辑
    if SP:
        # 应用止盈逻辑
        # 要确保执行顺序的正确性：先处理最高价，后处理开盘价

        # 如果次日最高价达到止盈条件，则按止盈价计算收益
        df.loc[df['aft_high'] >= df['close'] * (1 + SP), 'time_return'] = SP
        df.loc[df['aft_high'] >= df['close'] * (1 + SP), 'SFZY'] = '满足止盈'

        # 对于开盘价已满足止盈条件的记录，使用实际开盘价计算收益
        # 这一步会覆盖部分最高价已设置的收益率
        df.loc[df['aft_open'] >= df['close'] * (1 + SP), 'time_return'] = (df['aft_open'] - df['close']) / df['close']

    # 标记选中的可转债（排名前N的）
    df.loc[(df['rank'] <= hold_num), 'signal'] = 1

    # 创建每日选中的可转债记录
    daily_selected_bonds = df[df['signal'] == 1].copy()
    daily_selected_bonds = daily_selected_bonds.reset_index()

    # 删除没有标记的行并按日期排序
    df.dropna(subset=['signal'], inplace=True)

    # 检查是否有符合条件的债券
    if df.empty:
        logger.warning(f"没有符合条件的债券数据，返回CAGR为0")
        return 0.0
    
    df.sort_values(by='trade_date', inplace=True)

    # 计算组合回报
    res = pd.DataFrame()

    # 按等权计算组合回报
    time_return_series = df.groupby('trade_date')['time_return'].mean()

    # 检查时间回报序列是否为空
    if time_return_series.empty:
        logger.warning(f"时间回报序列为空，返回CAGR为0")
        return 0.0

    res['time_return'] = time_return_series

    # 计算手续费
    pos_df = df['signal'].unstack('code')
    pos_df.fillna(0, inplace=True)

    # 检查pos_df是否为空
    if pos_df.empty:
        logger.warning(f"持仓数据为空，返回CAGR为0")
        return 0.0

    cost_series = pos_df.diff().abs().sum(axis=1) * C_RATE / (pos_df.shift().sum(axis=1) + pos_df.sum(axis=1))
    res['cost'] = cost_series

    # 安全地修正首行手续费 - 确保res有数据且有cost列
    if len(res) > 0 and 'cost' in res.columns:
        res.iloc[0, res.columns.get_loc('cost')] = 0.5 * C_RATE  # 修正首行手续费

    # 扣除手续费及佣金后的回报
    res['daily_return'] = (res['time_return'] + 1) * (1 - res['cost']) - 1

    # 累计日收益率
    # res['cumulative_return'] = (1 + res['daily_return']).cumprod() - 1

    # 使用手动计算法计算CAGR
    cagr = calculate_cagr_manually(res['daily_return'], start_date, end_date)
    
    # 过拟合检测
    if check_overfitting:
        from lude.core.overfitting_detector import is_strategy_overfitted, get_overfitting_penalty_value
        
        try:
            # 进行过拟合检测
            is_overfitted = is_strategy_overfitted(
                df=df,
                daily_selected_bonds=daily_selected_bonds,
                res=res,
                hold_num=hold_num,
                min_trading_days_ratio=0.9,
                verbose=verbose_overfitting
            )
            
            if is_overfitted:
                # 如果检测到过拟合，返回极小的惩罚值
                penalty_cagr = get_overfitting_penalty_value()
                if verbose_overfitting:
                    logger.warning(f"检测到过拟合！原CAGR: {cagr:.6f} -> 惩罚CAGR: {penalty_cagr:.6f}")
                return penalty_cagr
            else:
                if verbose_overfitting:
                    logger.info(f"未检测到过拟合，返回正常CAGR: {cagr:.6f}")
                return cagr
                
        except Exception as e:
            # 过拟合检测出错时，打印警告但仍返回原始CAGR
            logger.error(f"过拟合检测出错: {e}")
            return cagr
    else:
        # 不进行过拟合检测，直接返回CAGR
        logger.info(f"不进行过拟合检测，直接返回CAGR: {cagr:.6f}")
        return cagr


if __name__ == '__main__':
    # 加载数据文件
    cb_data_path = os.path.join(DATA_DIR, 'cb_data.pq')
    index_data_path = os.path.join(DATA_DIR, 'index.pq')
    
    logger.info(f"加载可转债数据: {cb_data_path}")
    if not os.path.exists(cb_data_path):
        logger.error(f"错误：找不到可转债数据文件: {cb_data_path}")
        sys.exit(1)
        
    df = pd.read_parquet(cb_data_path)
    
    # 尝试加载指数数据
    if os.path.exists(index_data_path):
        logger.info(f"加载指数数据: {index_data_path}")
        index = pd.read_parquet(index_data_path)
    else:
        logger.warning(f"警告：找不到指数数据文件: {index_data_path}")
        index = None

    start_date = '20220729'
    end_date = '20250328'
    hold_num = 5
    min_price = 100
    max_price = 150

    factors = [
        {'name': 'dv_ratio', 'weight': 2, 'ascending': False},
        {'name': 'amount_5', 'weight': 2, 'ascending': True},
        {'name': 'amount_stk', 'weight': 2, 'ascending': True}
    ]

    # 计算启用止盈情况的CAGR
    cagr = calculate_bonds_cagr(
        df, start_date, end_date, hold_num, min_price, max_price, factors, None,
        check_overfitting=False, verbose_overfitting=False
    )

    # 打印CAGR结果
    logger.info("启用止盈情况的CAGR:")
    logger.info(cagr)
