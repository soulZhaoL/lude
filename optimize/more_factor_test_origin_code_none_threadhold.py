import warnings
import os
import numpy as np
import math
import sys

# 添加项目根目录到Python路径，以便能够导入utils模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings('ignore')  # 忽略警告
import pandas as pd
from pandas import IndexSlice as idx

pd.set_option('display.max_columns', None)  # 当列太多时不换行
from numpy import exp, nan

# 导入CAGR计算工具
from utils.cagr_utils import (
    calculate_cagr_manually,
    calculate_cagr_trading_days,
    get_quantstats_cagr,
    compare_cagr_methods,
    format_cagr_results
)

# 基础设置
benchmark = 'index_jsl'  # 选择基准，集思录等权:index_jsl, 沪深300:index_300, 中证1000:index_1000, 国证2000:index_2000
shares_per_board_lot = 10  # 每手数量(最小交易单位)
# 添加日内止盈比例
SP = 0.06  # 盘中止盈条件，6%止盈
c_rate = 2 / 1000  # 买卖一次花费的总佣金和滑点（双边）
# lude.cc网站参考收益率 - 可配置
LUDE_CAGR_NO_STOP = 0.0258  # 不止盈情况
LUDE_CAGR_WITH_STOP = 0.4573  # 启用止盈情况


def cal_cagr(df, start_date, end_date, hold_num, min, max, rank_factors, enable_stop_profit=True):
    """
    计算可转债组合的CAGR
    
    参数:
        df: 可转债数据
        start_date: 开始日期
        end_date: 结束日期
        hold_num: 持有数量
        min: 最低价格
        max: 最高价格
        rank_factors: 排序因子
        enable_stop_profit: 是否启用止盈功能，默认为True
    
    返回:
        cagrs: 不同方法计算的CAGR结果
        daily_selected_bonds: 每日选中的可转债
        res: 每日收益率
    """
    threadhold_num = None  # 轮动阈值

    # 排除设置
    df = df[(df.index.get_level_values('trade_date') >= start_date) & (
            df.index.get_level_values('trade_date') <= end_date)]  # 选择时间范围内数据
    df['filter'] = False  # 初始化过滤器

    df['close_pct'] = df.groupby('trade_date')['close'].rank(pct=True)  # 将收盘从小到大百分比排列

    df.loc[df.is_call.isin(
        ['已公告强赎', '公告到期赎回', '公告实施强赎', '公告提示强赎', '已满足强赎条件']), 'filter'] = True  # 排除赎回状态
    df.loc[df.list_days <= 3, 'filter'] = True  # 排除新债
    df.loc[df.left_years < 0.5, 'filter'] = True  # 排除到期日小于1年的标的

    df.loc[df.amount < 1000, 'filter'] = True  # 排除成交额小于1000万
    df.loc[df.close > max, 'filter'] = True  # 排除价格
    df.loc[df.close < min, 'filter'] = True  # 排除价格

    # print(rank_factors)
    # 计算多因子得分 和 排名(score总分越大越好， rank总排名越小越好)
    trade_date_group = df[df['filter'] == False].groupby('trade_date')
    for factor in rank_factors:
        if factor['name'] in df.columns:
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(ascending=factor['ascending']) * \
                                            factor['weight']
        else:
            print(f'未找到因子【{factor["name"]}】, 跳过')

    df['score'] = df[df.filter(like='score').columns].sum(axis=1, min_count=1)
    if hold_num >= 1:
        df['rank'] = df.groupby('trade_date')['score'].rank('first', ascending=False)
    else:
        df['rank_pct'] = df.groupby('trade_date')['score'].rank('first', ascending=False, pct=False)

    # 阈值轮动
    if threadhold_num:
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

            # 若上一交易日排名last_rank <= hold_num，今日mod_rank = ori_rank - threadhold_num，否则今日mod_rank = ori_rank
            _ranks_df['mod_rank'] = (_ranks_df['ori_rank'] - threadhold_num).where(_ranks_df['last_rank'] <= hold_num,
                                                                                   _ranks_df['ori_rank'])
            # 根据mod_rank 重新排序出今日rank
            _ranks_df['rank'] = _ranks_df['mod_rank'].rank(method='first')

            # 将今日最终排名rank写入原df
            df.loc[df.index.get_level_values('trade_date') == trade_date, ['mod_rank', 'rank']] = _ranks_df[
                ['mod_rank', 'rank']].values

    # 计算每日信号 采样信号 持仓状态
    code_group = df.groupby('code')

    # 添加日内止盈逻辑
    df['aft_open'] = code_group.open.shift(-1)  # 计算次日开盘价
    df['aft_close'] = code_group.close.shift(-1)  # 计算次日收盘价
    df['aft_high'] = code_group.high.shift(-1)  # 计算次日最高价
    df['time_return'] = code_group.pct_chg.shift(-1)  # 先计算不止盈情况的收益率
    df['SFZY'] = '未满足止盈'  # 先记录默认情况

    # 根据参数控制是否应用止盈逻辑
    if enable_stop_profit:
        # 应用止盈逻辑
        # 要确保执行顺序的正确性：先处理最高价，后处理开盘价
        # 注意：开盘价条件会覆盖最高价条件的部分记录

        # 如果次日最高价达到止盈条件，则按止盈价计算收益
        df.loc[df['aft_high'] >= df['close'] * (1 + SP), 'time_return'] = SP
        df.loc[df['aft_high'] >= df['close'] * (1 + SP), 'SFZY'] = '满足止盈'

        # 对于开盘价已满足止盈条件的记录，使用实际开盘价计算收益
        # 这一步会覆盖部分最高价已设置的收益率
        df.loc[df['aft_open'] >= df['close'] * (1 + SP), 'time_return'] = (df['aft_open'] - df['close']) / df['close']
    # 添加日内止盈逻辑 END

    df.loc[(df['rank'] <= hold_num), 'signal'] = 1  # 标记信号

    # 创建每日选中的可转债记录
    daily_selected_bonds = df[df['signal'] == 1].copy()
    daily_selected_bonds = daily_selected_bonds.reset_index()

    df.dropna(subset=['signal'], inplace=True)  # 删除没有标记的行
    df.sort_values(by='trade_date', inplace=True)  # 按日期排序

    # 计算组合回报
    res = pd.DataFrame()
    res['time_return'] = df.groupby('trade_date')['time_return'].mean()  # 按等权计算组合回报
    # 计算手续费
    pos_df = df['signal'].unstack('code')
    pos_df.fillna(0, inplace=True)
    res['cost'] = pos_df.diff().abs().sum(axis=1) * c_rate / (pos_df.shift().sum(axis=1) + pos_df.sum(axis=1))
    res.iloc[0, 1] = 0.5 * c_rate  # 修正首行手续费
    res['time_return'] = (res['time_return'] + 1) * (1 - res['cost']) - 1  # 扣除手续费及佣金后的回报

    # 计算日收益率
    res['daily_return'] = res['time_return']

    # 累计日收益率
    res['cumulative_return'] = (1 + res['daily_return']).cumprod() - 1

    # 使用多种方法计算CAGR
    try:
        # 使用quantstats库，同时测试期望不同的periods参数
        import quantstats as qs
        cagr_quantstats_365 = get_quantstats_cagr(res['time_return'], periods=365)  # 使用365天计算年化收益率
        cagr_quantstats_252 = get_quantstats_cagr(res['time_return'])  # 使用默认252天计算年化收益率

        print(
            f"{'止盈' if enable_stop_profit else '不止盈'} - QuantStats CAGR (periods=365): {cagr_quantstats_365:.6f} ({cagr_quantstats_365 * 100:.2f}%)")
        print(
            f"{'止盈' if enable_stop_profit else '不止盈'} - QuantStats CAGR (periods=252): {cagr_quantstats_252:.6f} ({cagr_quantstats_252 * 100:.2f}%)")
    except Exception as e:
        print(f"无法使用quantstats计算CAGR: {e}")
        cagr_quantstats_365 = None
        cagr_quantstats_252 = None

    # 使用手动计算法
    cagr_manual = calculate_cagr_manually(res['time_return'], start_date, end_date)
    print(f"{'止盈' if enable_stop_profit else '不止盈'} - 手动计算CAGR: {cagr_manual:.6f} ({cagr_manual * 100:.2f}%)")

    # 收集所有CAGR计算结果
    cagrs = {
        'quantstats_365': cagr_quantstats_365,
        'quantstats_252': cagr_quantstats_252,
        'manual': cagr_manual
    }

    return cagrs, daily_selected_bonds, res


if __name__ == '__main__':
    # 直接读取parquet文件，不再转换为CSV
    df = pd.read_parquet('cb_data.pq')
    index = pd.read_parquet('index.pq')

    # 基础设置
    start_date = '20220729'  # 开始日期
    end_date = '20250328'  # 结束日期
    hold_num = 5  # 持有数量
    min = 100
    max = 150

    # 排序因子
    factors = [
        {'name': 'dv_ratio', 'weight': 2, 'ascending': False},
        {'name': 'amount_5', 'weight': 2, 'ascending': True},
        {'name': 'amount_stk', 'weight': 2, 'ascending': True}
    ]

    # 计算两种情况的CAGR：启用止盈和不启用止盈
    print("=" * 30)
    print("计算不止盈情况的CAGR")
    print("=" * 30)
    cagrs_no_stop, bonds_no_stop, returns_no_stop = cal_cagr(df, start_date, end_date, hold_num, min, max, factors,
                                                             enable_stop_profit=False)

    print("\n" + "=" * 30)
    print("计算启用止盈情况的CAGR")
    print("=" * 30)
    cagrs_with_stop, bonds_with_stop, returns_with_stop = cal_cagr(df, start_date, end_date, hold_num, min, max,
                                                                   factors, enable_stop_profit=True)

    # 打印两种情况的CAGR结果比较
    print("\n" + "=" * 50)
    print("不止盈与启用止盈两种情况的CAGR结果比较")
    print("=" * 50)

    print("\n不止盈情况下的CAGR:")
    print(f"quantstats_365: {cagrs_no_stop['quantstats_365']:.6f} ({cagrs_no_stop['quantstats_365'] * 100:.2f}%)")
    print(f"quantstats_252: {cagrs_no_stop['quantstats_252']:.6f} ({cagrs_no_stop['quantstats_252'] * 100:.2f}%)")
    print(f"manual        : {cagrs_no_stop['manual']:.6f} ({cagrs_no_stop['manual'] * 100:.2f}%)")
    print("")

    print("启用止盈情况下的CAGR:")
    print(f"quantstats_365: {cagrs_with_stop['quantstats_365']:.6f} ({cagrs_with_stop['quantstats_365'] * 100:.2f}%)")
    print(f"quantstats_252: {cagrs_with_stop['quantstats_252']:.6f} ({cagrs_with_stop['quantstats_252'] * 100:.2f}%)")
    print(f"manual        : {cagrs_with_stop['manual']:.6f} ({cagrs_with_stop['manual'] * 100:.2f}%)")
    print("")

    # 打印lude.cc网站展示的结果以供比较
    print("lude.cc网站结果参考:")
    print(f"不止盈: {LUDE_CAGR_NO_STOP * 100:.2f}%")
    print(f"启用止盈: {LUDE_CAGR_WITH_STOP * 100:.2f}%")

    # 保存两种情况的结果
    # 1. 不止盈情况
    bonds_no_stop_file = 'daily_selected_bonds_no_stop.csv'
    bonds_no_stop.to_csv(bonds_no_stop_file, index=False)

    returns_no_stop_file = 'daily_returns_no_stop.csv'
    returns_no_stop.to_csv(returns_no_stop_file)

    # 2. 启用止盈情况
    bonds_with_stop_file = 'daily_selected_bonds_with_stop.csv'
    bonds_with_stop.to_csv(bonds_with_stop_file, index=False)

    returns_with_stop_file = 'daily_returns_with_stop.csv'
    returns_with_stop.to_csv(returns_with_stop_file)

    print("\n文件保存情况:")
    print(f"1. 不止盈情况 - 可转债选择: {bonds_no_stop_file}")
    print(f"2. 不止盈情况 - 每日收益率: {returns_no_stop_file}")
    print(f"3. 启用止盈情况 - 可转债选择: {bonds_with_stop_file}")
    print(f"4. 启用止盈情况 - 每日收益率: {returns_with_stop_file}")

    # # 使用当前选择的结果（启用止盈）显示最近的可转债选择
    # print("\n最近选择的可转债（最后10条记录，启用止盈情况）：")
    # display_columns = ['trade_date', 'code', 'bond_nm', 'close', 'score', 'rank', 'SFZY']
    # available_columns = [col for col in display_columns if col in bonds_with_stop.columns]
    # sorted_bonds = bonds_with_stop.sort_values(by='trade_date', ascending=False)
    # print(sorted_bonds[available_columns].head(10).to_string(index=False))

    # # 统计止盈情况
    # if 'SFZY' in bonds_with_stop.columns:
    #     zy_stats = bonds_with_stop['SFZY'].value_counts()
    #     print("\n止盈统计：")
    #     print(zy_stats)
    #     zy_rate = zy_stats.get('满足止盈', 0) / len(bonds_with_stop) * 100
    #     print(f"止盈比例: {zy_rate:.2f}%")

    # 对比与lude.cc网站结果的差异
    print("\n与lude.cc网站结果的比较:")

    # 1. 不止盈情况
    lude_cagr_no_stop = LUDE_CAGR_NO_STOP
    closest_method_no_stop = None
    closest_diff_no_stop = float('inf')

    for method, cagr_value in cagrs_no_stop.items():
        if cagr_value is not None:
            diff = abs(cagr_value - lude_cagr_no_stop)
            if diff < closest_diff_no_stop:
                closest_diff_no_stop = diff
                closest_method_no_stop = method

    if closest_method_no_stop:
        print(f"1. 不止盈情况 - 与lude.cc结果({lude_cagr_no_stop * 100:.2f}%)最接近的方法: {closest_method_no_stop}")
        print(
            f"   差值: {closest_diff_no_stop * 100:.2f}%点，计算结果: {cagrs_no_stop[closest_method_no_stop] * 100:.2f}%")

    # 2. 启用止盈情况
    lude_cagr_with_stop = LUDE_CAGR_WITH_STOP  # lude.cc网站显示的启用止盈情况 - 45.88%
    closest_method_with_stop = None
    closest_diff_with_stop = float('inf')

    for method, cagr_value in cagrs_with_stop.items():
        if cagr_value is not None:
            diff = abs(cagr_value - lude_cagr_with_stop)
            if diff < closest_diff_with_stop:
                closest_diff_with_stop = diff
                closest_method_with_stop = method

    if closest_method_with_stop:
        print(
            f"2. 启用止盈情况 - 与lude.cc结果({lude_cagr_with_stop * 100:.2f}%)最接近的方法: {closest_method_with_stop}")
        print(
            f"   差值: {closest_diff_with_stop * 100:.2f}%点，计算结果: {cagrs_with_stop[closest_method_with_stop] * 100:.2f}%")
