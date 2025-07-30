"""
绩效指标计算模块

提供计算可转债组合年化收益率(CAGR)和其他风险收益指标的高效函数，支持多种筛选条件和排序因子。
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Union, Tuple

from lude.utils.cagr_utils import calculate_cagr_manually

# 全局常量设置
C_RATE = 2 / 1000  # 买卖一次花费的总佣金和滑点（双边）
SP = 0.06  # 盘中止盈条件，6%止盈
YEARLY_FACTOR = 245  # 交易日标准年化因子
RISK_FREE = 0.0  # 无风险利率


def filter_bonds(df: pd.DataFrame, min_price: float, max_price: float) -> pd.DataFrame:
    """
    筛选可转债数据
    
    参数:
        df: 可转债数据DataFrame
        min_price: 最低价格筛选
        max_price: 最高价格筛选
    
    返回:
        DataFrame: 带有筛选标记的DataFrame
    """
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
    
    return df


def calculate_factor_scores(
    df: pd.DataFrame, 
    rank_factors: List[Dict[str, Any]]
) -> pd.DataFrame:
    """
    计算多因子得分和排名
    
    参数:
        df: 可转债数据DataFrame
        rank_factors: 排序因子，格式为[{'name': '因子名', 'weight': 权重, 'ascending': 排序方向}, ...]
    
    返回:
        DataFrame: 添加了多因子得分和排名的DataFrame
    """
    # 获取未被过滤的数据
    filtered_df = df[df['filter'] == False]
    trade_date_group = filtered_df.groupby('trade_date')
    
    # 应用每个因子并计算得分
    for factor in rank_factors:
        if factor['name'] in df.columns:
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(
                ascending=factor['ascending']) * factor['weight']
    
    # 计算总得分和排名
    df['score'] = df[df.filter(like='score').columns].sum(axis=1, min_count=1)
    df['rank'] = df.groupby('trade_date')['score'].rank('first', ascending=False)
    
    return df


def apply_threshold_ranking(
    df: pd.DataFrame, 
    hold_num: int, 
    threshold_num: Optional[int] = None
) -> pd.DataFrame:
    """
    应用阈值轮动逻辑
    
    参数:
        df: 可转债数据DataFrame，已包含排名
        hold_num: 持有数量
        threshold_num: 轮动阈值，默认为None
    
    返回:
        DataFrame: 应用了阈值轮动的DataFrame
    """
    if not threshold_num:
        return df
        
    df.rename(columns={'rank': 'ori_rank'}, inplace=True)  # 记录原排名
    df['rank'] = np.nan  # 初始化排名
    df['mod_rank'] = np.nan  # 初始化修正排名
    
    # 获取位置索引
    RANK_INDEX = df.columns.get_loc('rank')
    ORI_RANK_INDEX = df.columns.get_loc('ori_rank')
    
    # 设置首日排名等于原排名
    first_day_mask = df.index.get_level_values(1) == df.index.get_level_values(1)[0]
    df.iloc[first_day_mask, RANK_INDEX] = df.iloc[first_day_mask, ORI_RANK_INDEX]
    
    # 获取交易日列表
    trade_date_list = df.index.get_level_values('trade_date').unique()
    
    # 遍历每个交易日对排名进行处理
    for trade_date, _df in df.groupby('trade_date'):
        # 跳过首日
        if trade_date == df.index.get_level_values(1)[0]:
            continue
            
        last_trade_date = trade_date_list[trade_date_list.get_loc(trade_date) - 1]
        
        # 构建排名DataFrame
        _ranks_df = df.loc[df.index.get_level_values('trade_date') == trade_date, ['ori_rank']] \
            .merge(df.loc[df.index.get_level_values('trade_date') == last_trade_date, 'rank'], 
                  how='left', on='code') \
            .rename(columns={'rank': 'last_rank'})
        
        # 应用阈值规则
        _ranks_df['mod_rank'] = (_ranks_df['ori_rank'] - threshold_num).where(
            _ranks_df['last_rank'] <= hold_num, _ranks_df['ori_rank'])
            
        # 重新排序
        _ranks_df['rank'] = _ranks_df['mod_rank'].rank(method='first')
        
        # 更新原DataFrame
        df.loc[df.index.get_level_values('trade_date') == trade_date, 
              ['mod_rank', 'rank']] = _ranks_df[['mod_rank', 'rank']].values
    
    return df


def apply_take_profit(
    df: pd.DataFrame, 
    SP: Optional[float] = 0.06
) -> pd.DataFrame:
    """
    应用止盈逻辑
    
    参数:
        df: 可转债数据DataFrame
        SP: 止盈比例，默认为0.06 (6%)
    
    返回:
        DataFrame: 应用了止盈逻辑的DataFrame
    """
    # 按证券代码分组
    code_group = df.groupby('code')
    
    # 计算次日价格和默认收益率
    df['aft_open'] = code_group.open.shift(-1)  # 计算次日开盘价
    df['aft_close'] = code_group.close.shift(-1)  # 计算次日收盘价
    df['aft_high'] = code_group.high.shift(-1)  # 计算次日最高价
    df['time_return'] = code_group.pct_chg.shift(-1)  # 先计算不止盈情况的收益率
    df['SFZY'] = '未满足止盈'  # 先记录默认情况

    # 根据参数控制是否应用止盈逻辑
    if SP:
        # 如果次日最高价达到止盈条件，则按止盈价计算收益
        tp_high_mask = df['aft_high'] >= df['close'] * (1 + SP)
        df.loc[tp_high_mask, 'time_return'] = SP
        
        # 对于开盘价已满足止盈条件的记录，使用实际开盘价计算收益
        # 这一步会覆盖部分最高价已设置的收益率
        tp_open_mask = df['aft_open'] >= df['close'] * (1 + SP)
        df.loc[tp_open_mask, 'time_return'] = (df['aft_open'] - df['close']) / df['close']
    
    return df


def calculate_portfolio_returns(
    df: pd.DataFrame, 
    hold_num: int
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    计算投资组合收益率
    
    参数:
        df: 处理后的可转债数据DataFrame
        hold_num: 持有数量
    
    返回:
        Tuple: (日收益率DataFrame, 选中的可转债DataFrame)
    """
    # 标记选中的可转债
    df.loc[(df['rank'] <= hold_num), 'signal'] = 1
    
    # 创建每日选中的可转债记录
    daily_selected_bonds = df[df['signal'] == 1].copy()
    daily_selected_bonds = daily_selected_bonds.reset_index()
    
    # 删除没有标记的行并按日期排序 - 使用显式复制避免SettingWithCopyWarning
    df_with_signal = df.dropna(subset=['signal']).copy()
    df_with_signal = df_with_signal.sort_values(by='trade_date')
    
    # 计算组合回报
    portfolio_returns = pd.DataFrame()
    
    # 按等权计算组合回报
    portfolio_returns['time_return'] = df_with_signal.groupby('trade_date')['time_return'].mean()
    
    # 计算手续费
    pos_df = df_with_signal['signal'].unstack('code')
    pos_df.fillna(0, inplace=True)
    portfolio_returns['cost'] = pos_df.diff().abs().sum(axis=1) * C_RATE / (
        pos_df.shift().sum(axis=1) + pos_df.sum(axis=1))
    portfolio_returns.iloc[0, 1] = 0.5 * C_RATE  # 修正首行手续费
    
    # 扣除手续费及佣金后的回报
    portfolio_returns['daily_return'] = (portfolio_returns['time_return'] + 1) * (
        1 - portfolio_returns['cost']) - 1
    
    # 计算累计收益率
    portfolio_returns['cumulative_return'] = (1 + portfolio_returns['daily_return']).cumprod() - 1
    
    return portfolio_returns, daily_selected_bonds


def calculate_risk_metrics(
    returns: pd.Series,
    cagr: float
) -> Dict[str, float]:
    """
    计算风险指标
    
    参数:
        returns: 日收益率序列
        cagr: 年化收益率
    
    返回:
        Dict: 风险指标字典
    """
    try:
        # 尝试使用quantstats库计算指标
        import quantstats as qs
        
        # 计算风险指标
        max_drawdown = abs(qs.stats.max_drawdown(returns))
        sharpe_ratio = qs.stats.sharpe(returns, rf=RISK_FREE, periods=YEARLY_FACTOR)
        sortino_ratio = qs.stats.sortino(returns, rf=RISK_FREE, periods=YEARLY_FACTOR)
        calmar_ratio = cagr / max_drawdown if max_drawdown > 0 else float('inf')
        
    except (ImportError, Exception):
        # 使用标准方法计算风险指标
        
        # 计算累计收益率
        cum_returns = (1 + returns).cumprod() - 1
        
        # 计算最大回撤
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / (1 + running_max)
        max_drawdown = abs(drawdown.min())
        
        # 计算年化标准差
        annual_std = returns.std() * np.sqrt(YEARLY_FACTOR)
        
        # 计算夏普比率
        sharpe_ratio = (cagr - RISK_FREE) / annual_std if annual_std > 0 else 0
        
        # 计算索提诺比率
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std() * np.sqrt(YEARLY_FACTOR)
            sortino_ratio = (cagr - RISK_FREE) / downside_std if downside_std > 0 else 0
        else:
            sortino_ratio = float('inf')
        
        # 计算卡玛比率
        calmar_ratio = cagr / max_drawdown if max_drawdown > 0 else float('inf')
    
    # 返回所有风险指标
    return {
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio
    }


def calculate_performance_metrics(
    df: pd.DataFrame, 
    start_date: str,
    end_date: str,
    hold_num: int,
    min_price: float,
    max_price: float,
    rank_factors: List[Dict[str, Any]],
    threshold_num: Optional[int] = None,
    SP: Optional[float] = 0.06
) -> Dict[str, Any]:
    """
    计算可转债组合的综合绩效指标
    
    参数：
        df: 可转债数据DataFrame
        start_date: 开始日期，格式'YYYYMMDD'
        end_date: 结束日期，格式'YYYYMMDD'
        hold_num: 持有数量
        min_price: 最低价格筛选
        max_price: 最高价格筛选
        rank_factors: 排序因子，格式为[{'name': '因子名', 'weight': 权重, 'ascending': 排序方向}, ...]
        threshold_num: 轮动阈值，默认为None
        SP: 止盈比例，默认为0.06 (6%)，设为None则不启用止盈
    
    返回：
        dict: 包含以下指标的字典
            - cagr: 年化收益率
            - max_drawdown: 最大回撤率
            - sharpe_ratio: 夏普比率
            - sortino_ratio: 索提诺比率
            - calmar_ratio: 卡玛比率
            - daily_selected_bonds: 每日选中的可转债DataFrame
            - daily_returns: 每日收益率DataFrame
    """
    # 数据筛选 - 按日期范围
    df = df[(df.index.get_level_values('trade_date') >= start_date) &
            (df.index.get_level_values('trade_date') <= end_date)].copy()
    
    # 1. 筛选可转债
    df = filter_bonds(df, min_price, max_price)
    
    # 2. 计算多因子得分和排名
    df = calculate_factor_scores(df, rank_factors)
    
    # 3. 应用阈值轮动（如果启用）
    if threshold_num:
        df = apply_threshold_ranking(df, hold_num, threshold_num)
    
    # 4. 应用止盈逻辑
    df = apply_take_profit(df, SP)
    
    # 5. 计算投资组合收益率
    daily_returns, daily_selected_bonds = calculate_portfolio_returns(df, hold_num)
    
    # 6. 计算年化收益率
    cagr = calculate_cagr_manually(daily_returns['daily_return'], start_date, end_date)
    
    # 7. 计算风险指标
    risk_metrics = calculate_risk_metrics(daily_returns['daily_return'], cagr)
    
    # 8. 返回所有指标
    results = {
        'cagr': cagr,
        'max_drawdown': risk_metrics['max_drawdown'],
        'sharpe_ratio': risk_metrics['sharpe_ratio'],
        'sortino_ratio': risk_metrics['sortino_ratio'],
        'calmar_ratio': risk_metrics['calmar_ratio'],
        'daily_selected_bonds': daily_selected_bonds,
        'daily_returns': daily_returns,
        'processed_df': df  # 添加处理后的数据框，供过拟合检测使用
    }
    
    return results
