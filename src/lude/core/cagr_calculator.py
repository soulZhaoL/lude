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

from lude.utils.cagr_utils import calculate_cagr_manually
from lude.config.paths import DATA_DIR

# 忽略警告
warnings.filterwarnings('ignore')

# 基础常量设置
SP = 0.06  # 盘中止盈条件，6%止盈
C_RATE = 2 / 1000  # 买卖一次花费的总佣金和滑点（双边）
threshold_num = None  # 轮动阈值


def calculate_bonds_cagr(df, start_date, end_date, hold_num, min_price, max_price,
                         rank_factors, threshold_num=None):
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
    
    返回：
        cagr: 使用手动计算法得到的CAGR值
        daily_selected_bonds: 每日选中的可转债DataFrame
        daily_returns: 每日收益率DataFrame
    """
    # 数据筛选 - 按日期范围
    df = df[(df.index.get_level_values('trade_date') >= start_date) &
            (df.index.get_level_values('trade_date') <= end_date)]

    # 初始化过滤器
    df['filter'] = False

    # 计算收盘价百分比排名
    df['close_pct'] = df.groupby('trade_date')['close'].rank(pct=True)

    # 排除条件设置
    df.loc[df.is_call.isin(['已公告强赎', '公告到期赎回', '公告实施强赎',
                            '公告提示强赎', '已满足强赎条件']), 'filter'] = True  # 排除赎回状态
    df.loc[df.list_days <= 3, 'filter'] = True  # 排除新债
    df.loc[df.left_years < 0.5, 'filter'] = True  # 排除到期日小于0.5年的标的
    df.loc[df.amount < 1000, 'filter'] = True  # 排除成交额小于1000万
    df.loc[df.close > max_price, 'filter'] = True  # 排除价格过高
    df.loc[df.close < min_price, 'filter'] = True  # 排除价格过低

    # 计算多因子得分和排名
    trade_date_group = df[df['filter'] == False].groupby('trade_date')

    # 应用每个因子并计算得分
    for factor in rank_factors:
        if factor['name'] in df.columns:
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(
                ascending=factor['ascending']) * factor['weight']
        else:
            print(f'未找到因子【{factor["name"]}】, 跳过')

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
    df.sort_values(by='trade_date', inplace=True)

    # 计算组合回报
    res = pd.DataFrame()

    # 按等权计算组合回报
    res['time_return'] = df.groupby('trade_date')['time_return'].mean()

    # 计算手续费
    pos_df = df['signal'].unstack('code')
    pos_df.fillna(0, inplace=True)
    res['cost'] = pos_df.diff().abs().sum(axis=1) * C_RATE / (pos_df.shift().sum(axis=1) + pos_df.sum(axis=1))
    res.iloc[0, 1] = 0.5 * C_RATE  # 修正首行手续费

    # 扣除手续费及佣金后的回报
    res['daily_return'] = (res['time_return'] + 1) * (1 - res['cost']) - 1

    # 累计日收益率
    # res['cumulative_return'] = (1 + res['daily_return']).cumprod() - 1

    # 使用手动计算法计算CAGR
    cagr = calculate_cagr_manually(res['daily_return'], start_date, end_date)

    # return cagr, daily_selected_bonds, res
    return cagr


if __name__ == '__main__':
    # 加载数据文件
    cb_data_path = os.path.join(DATA_DIR, 'cb_data.pq')
    index_data_path = os.path.join(DATA_DIR, 'index.pq')
    
    print(f"加载可转债数据: {cb_data_path}")
    if not os.path.exists(cb_data_path):
        print(f"错误：找不到可转债数据文件: {cb_data_path}")
        sys.exit(1)
        
    df = pd.read_parquet(cb_data_path)
    
    # 尝试加载指数数据
    if os.path.exists(index_data_path):
        print(f"加载指数数据: {index_data_path}")
        index = pd.read_parquet(index_data_path)
    else:
        print(f"警告：找不到指数数据文件: {index_data_path}")
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
        df, start_date, end_date, hold_num, min_price, max_price, factors, None
    )

    # 打印CAGR结果
    print("启用止盈情况的CAGR:")
    print(cagr)
