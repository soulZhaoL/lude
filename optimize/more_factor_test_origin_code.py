import warnings
warnings.filterwarnings('ignore') # 忽略警告
import pandas as pd
from pandas import IndexSlice as idx
pd.set_option('display.max_columns', None)  # 当列太多时不换行
df = pd.read_parquet('../cb_data.pq') # 导入转债数据
index = pd.read_parquet('../index.pq') # 导入指数数据
from numpy import exp, nan
print(df.head())


# 基础设置
start_date = '20220801'  # 开始日期
end_date = '20240325' # 结束日期
benchmark = 'index_jsl' # 选择基准，集思录等权:index_jsl, 沪深300:index_300, 中证1000:index_1000, 国证2000:index_2000
shares_per_board_lot = 10 # 每手数量(最小交易单位)
def cal_cagr(df, start_date, end_date, rank_factors):
    hold_num = 5 # 持有数量
    threadhold_num = 5 # 轮动阈值
    c_rate =  1 / 1000 # 买卖一次花费的总佣金和滑点（双边）

    # 排除设置
    df = df[(df.index.get_level_values('trade_date') >= start_date) & (df.index.get_level_values('trade_date') <= end_date)] # 选择时间范围内数据
    df['filter'] = False # 初始化过滤器

    df['close_pct'] = df.groupby('trade_date')['close'].rank(pct=True) # 将收盘从小到大百分比排列

    df.loc[df.is_call.isin(['已公告强赎', '公告到期赎回','公告实施强赎', '公告提示强赎', '已满足强赎条件']), 'filter'] = True # 排除赎回状态
    df.loc[df.list_days <= 3, 'filter'] = True # 排除新债
    df.loc[df.left_years < 0.5, 'filter'] = True # 排除到期日小于1年的标的

    # df.loc[df.conv_prem >0.5 , 'filter'] = True # 排除溢价率
    # df.loc[df.remain_size > 10, 'filter'] = True # 排除剩余规模
    # df.loc[df.rating.isin(['BBB+', 'BBB','BBB+', 'BB+','BB', 'BB-','B+', 'B','B-', 'CCC+','CCC', 'CCC-']), 'filter'] = True # 排除评级
    df.loc[df.close > 150, 'filter'] = True  # 排除价格
    df.loc[df.close < 100, 'filter'] = True  # 排除价格
    #df.loc[df.ps_ttm < 0, 'filter'] = True # 排除市盈率
    #df.loc[df.ps_ttm < 0, 'filter'] = True # 排除市销率
    # df.loc[df.pb < 0, 'filter'] = True # 排除市净率
    # df.loc[df.close_pct > 0.8, 'filter'] = True # 排除收盘价高于x%的标的

    # 计算多因子得分 和 排名(score总分越大越好， rank总排名越小越好)

    # 生成因子字典，name:列名，weight:权重, ascending:排序方向
    # rank_factors = [
    #     {'name': 'left_years', 'weight': 5, 'ascending': False}, #价格
    #     {'name': 'issue_size', 'weight': 5, 'ascending': False},  #溢价率
    #     {'name': 'ps_ttm', 'weight': 3, 'ascending': True},  #余额
    #     {'name': 'pe_ttm', 'weight': 4, 'ascending': True}  #余额
    # ]

    # print(rank_factors)
    # 计算多因子得分 和 排名(score总分越大越好， rank总排名越小越好)
    trade_date_group = df[df['filter'] ==False].groupby('trade_date')
    for factor in rank_factors:
        if factor['name'] in df.columns:
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(ascending=factor['ascending']) * factor['weight']
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
                .merge(df.loc[df.index.get_level_values('trade_date') == last_trade_date, 'rank'], how='left', on='code') \
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
    df['time_return'] = code_group.pct_chg.shift(-1) # 计算标的每日回报
    df.loc[(df['rank'] <= hold_num), 'signal'] = 1 # 标记信号
    df.dropna(subset=['signal'], inplace=True) # 删除没有标记的行
    df.sort_values(by='trade_date', inplace=True) # 按日期排序


    # 计算组合回报
    res = pd.DataFrame()
    res['time_return'] = df.groupby('trade_date')['time_return'].mean() # 按等权计算组合回报
    # 计算手续费
    pos_df = df['signal'].unstack('code')
    pos_df.fillna(0, inplace=True)
    res['cost'] = pos_df.diff().abs().sum(axis=1) * c_rate / (pos_df.shift().sum(axis=1) + pos_df.sum(axis=1))
    res.iloc[0, 1] = 0.5 * c_rate# 修正首行手续费
    res['time_return'] = (res['time_return'] + 1) * (1 - res['cost']) - 1# 扣除手续费及佣金后的回报

    import quantstats as qs
    cagr = qs.stats.cagr(res['time_return']) # 计算年化收益率
    # print("cagr: ", cagr)
    return cagr

