"""
可转债CAGR计算器 - 精简版

本模块提供计算可转债组合CAGR的核心功能，支持止盈和非止盈两种模式。
基于more_factor_test_origin_code_none_threadhold.py精简而来，只保留核心计算逻辑。

支持生成HTML报告展示详细的回测结果分析。

基准数据说明：
- 使用index.pq文件中的index_jsl列作为基准数据
- index_jsl是集思录等权位指数，用于在报告中与策略收益进行比较
- 在HTML报告中会显示策略与基准的对比图表和性能指标

使用方法：
1. 运行calculate_bonds_cagr获取回测指标
2. 使用generate_quantstats_report函数生成HTML报告
3. 报告将保存在reports目录下，可在浏览器中打开查看

"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from numpy import nan
import quantstats as qs
import datetime as dt
from pathlib import Path
import matplotlib.pyplot as plt

# 导入Excel报告生成工具
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.lude.utils.generate_excel_report import generate_excel_report

from lude.utils.cagr_utils import calculate_cagr_geometric, calculate_cagr_manually, calculate_cagr_trading_days
from lude.config.paths import DATA_DIR, PROJECT_ROOT

# 忽略警告
warnings.filterwarnings('ignore')
# 设置年化参数和风险收益指标参数
yearly_factor = 245  # 交易日标准年化因子
risk_free = 0.0  # 无风险利率
# 基础常量设置
SP = 0.06  # 盘中止盈条件，6%止盈
C_RATE = 2 / 1000  # 买卖一次花费的总佣金和滑点（双边）
threshold_num = None  # 轮动阈值


def calculate_bonds_cagr(df, start_date, end_date, hold_num, min_price, max_price,
                         rank_factors, threshold_num=None):
    """
    计算可转债组合的CAGR和其他风险收益指标
    
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
            df[f'{factor["name"]}_score'] = trade_date_group[factor["name"]].rank(ascending=factor['ascending']) * factor['weight']
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

    # 使用原始方法计算 CAGR
    cagr = calculate_cagr_manually(res['daily_return'], start_date, end_date)

    # 计算累计收益率
    res['cumulative_return'] = (1 + res['daily_return']).cumprod() - 1
    
    # 计算最大回撤率
    res['cummax'] = res['cumulative_return'].cummax()
    res['drawdown'] = (res['cumulative_return'] - res['cummax']) / (1 + res['cummax'])
    max_drawdown = abs(res['drawdown'].min())
    
    # 准备数据供 quantstats 使用
    # 创建带日期索引的收益率序列
    # 使用更有描述性的变量名，避免混淆
    formatted_return_series = pd.Series(res['daily_return'].values, index=res.index, name='return')
    
    # 转换索引为日期格式，如果不是已经是日期格式的话
    if not isinstance(formatted_return_series.index, pd.DatetimeIndex):
        try:
            # 尝试转换为日期格式
            formatted_return_series.index = pd.to_datetime(formatted_return_series.index)
        except:
            # 如果是'trade_date'格式，尝试特殊处理
            formatted_return_series.index = pd.to_datetime(formatted_return_series.index.astype(str), format='%Y%m%d')

    # 使用 quantstats 计算风险收益指标
    try:
        # 查阅 quantstats 文档，使用正确的 API 参数
        # 注意：quantstats 的不同版本 API 可能有变化
        print(f"\n使用 quantstats {qs.__version__} 版本计算风险收益指标...")

        # 新版 API
        qs_max_drawdown = qs.stats.max_drawdown(formatted_return_series)
        qs_sharpe = qs.stats.sharpe(formatted_return_series, rf=risk_free, periods=yearly_factor)
        qs_sortino = qs.stats.sortino(formatted_return_series, rf=risk_free, periods=yearly_factor)
        qs_calmar = qs.stats.calmar(formatted_return_series)

        # 更新计算结果，注意取最大回撤率的绝对值
        max_drawdown = abs(qs_max_drawdown)  # quantstats 返回的回撤率是负值，我们取绝对值
        sharpe_ratio = qs_sharpe
        sortino_ratio = qs_sortino

        # quantstats 的卡玛比率计算可能与标准有差异，手动重新计算
        # 使用标准公式：年化收益率 / 最大回撤率
        calmar_ratio = cagr / max_drawdown if max_drawdown > 0 else float('inf')

    except Exception as e:
        # 如果 quantstats 计算出错，使用标准计算方法
        print(f"使用 quantstats 计算风险收益指标时出错: {str(e)}")
        # 计算年化标准差
        annual_std = formatted_return_series.std() * np.sqrt(yearly_factor)

        # 计算夏普比率
        sharpe_ratio = (cagr - risk_free) / annual_std if annual_std > 0 else 0

        # 计算索提诺比率
        downside_returns = formatted_return_series[formatted_return_series < 0]
        if len(downside_returns) > 0:
            # 使用下行风险标准差
            downside_std = downside_returns.std() * np.sqrt(yearly_factor)
            sortino_ratio = (cagr - risk_free) / downside_std if downside_std > 0 else 0
        else:
            sortino_ratio = float('inf')  # 如果没有负收益，索提诺比率为无穷大

        # 计算卡玛比率
        calmar_ratio = cagr / max_drawdown if max_drawdown > 0 else float('inf')

    # 返回所有指标
    results = {
        'cagr': cagr,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio,
        'daily_selected_bonds': daily_selected_bonds,
        'daily_returns': res,
        'quantstats_returns': formatted_return_series  # 添加这个字段，保存已经格式化好的收益率序列
    }
    
    return results


def generate_quantstats_report(returns, benchmark=None, start_date=None, end_date=None, 
                         output_dir=None, title="可转债策略回测报告", 
                         strategy_name="多因子可转债策略", factor_desc=None, metrics=None):
    """
    生成量化交易策略详细的HTML报告
    
    参数：
        returns: pandas.Series - 策略的每日收益率序列，带日期索引
        benchmark: pandas.Series - 基准指数的每日收益率序列，带日期索引（可选）
        start_date: str - 开始日期，格式'YYYYMMDD'
        end_date: str - 结束日期，格式'YYYYMMDD'
        output_dir: str - 输出目录路径，默认为DATA_DIR下的reports子目录
        title: str - 报告标题
        strategy_name: str - 策略名称
        factor_desc: str - 因子组合描述
    
    返回：
        report_path: str - 生成的HTML报告文件路径
    """
    # 创建输出目录
    if output_dir is None:
        output_dir = os.path.join(PROJECT_ROOT, 'reports')
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 格式化日期，用于文件名
    now = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 转换日期格式，用于报告显示
    start_display = pd.to_datetime(start_date, format='%Y%m%d').strftime('%Y-%m-%d') if start_date else '开始'
    end_display = pd.to_datetime(end_date, format='%Y%m%d').strftime('%Y-%m-%d') if end_date else '结束'
    
    # 构建报告文件名
    report_filename = f"{strategy_name.replace(' ', '_')}_{start_date}_{end_date}_{now}.html"
    report_path = os.path.join(output_dir, report_filename)
    
    # 构建完整的报告标题，包含策略名称和日期范围
    full_title = f"{title}: {strategy_name} ({start_display} 至 {end_display})"
    
    # 准备因子描述
    factor_info = f"\n<h3>因子组合描述:</h3>\n<pre>{factor_desc}</pre>" if factor_desc else ""

    # 设置报告选项
    report_kwargs = {
        'title': full_title,
        'output': report_path,
        'benchmark': benchmark,
        'periods_per_year': yearly_factor,
        'rf': risk_free,  # 无风险利率
        'grayscale': False,  # 使用彩色图表
        'match_dates': True,  # 确保策略和基准使用相同的日期范围
        'display': False  # 不自动打开浏览器
    }
    
    try:
        print(f"正在生成HTML报告: {report_path}...")
        # 使用quantstats生成HTML报告
        qs.reports.html(returns, **report_kwargs)
        print(f"HTML报告生成成功! 文件位置: {report_path}")
        
        # 如果想自动打开报告（仅在本地测试时使用）
        # import webbrowser
        # webbrowser.open('file://' + os.path.abspath(report_path))
        
        return report_path
    except Exception as e:
        print(f"生成HTML报告时出错: {str(e)}")
        return None


if __name__ == '__main__':

    # 加载数据文件
    cb_data_path = os.path.join(DATA_DIR, 'cb_data.pq')
    index_data_path = os.path.join(DATA_DIR, 'index.pq')
    
    print(f"加载可转债数据: {cb_data_path}")
    if not os.path.exists(cb_data_path):
        print(f"错误：找不到可转债数据文件: {cb_data_path}")
        sys.exit(1)
        
    df = pd.read_parquet(cb_data_path)
    
    # 加载指数数据作为基准
    benchmark = None
    if os.path.exists(index_data_path):
        print(f"加载指数数据: {index_data_path}")
        index_df = pd.read_parquet(index_data_path)
        
        # 处理基准数据 - 提取index_jsl列作为基准
        if 'index_jsl' in index_df.columns:
            print("找到index_jsl基准数据，将用于生成比较报告")
            
            # 根据index_df的结构处理数据
            # 假设index_df包含'trade_date'列和'index_jsl'列
            if 'trade_date' in index_df.columns:
                # 设置日期为索引
                index_df.set_index('trade_date', inplace=True)
            
            # 计算基准的每日收益率
            benchmark = index_df['index_jsl'].pct_change().dropna()
            
            # 确保索引是日期类型
            if not isinstance(benchmark.index, pd.DatetimeIndex):
                benchmark.index = pd.to_datetime(benchmark.index)
                
            print(f"基准数据行数: {len(benchmark)}")
        else:
            print("警告: 在index.pq中未找到index_jsl列，将不使用基准数据")
    else:
        print(f"警告：找不到指数数据文件: {index_data_path}，将不使用基准数据")

    start_date = '20220729'
    end_date = '20250328'
    hold_num = 5
    min_price = 100
    max_price = 150

    factors = [
        {"name": "amount_5", "description": "转股溢价率", "weight": 3, "ascending": True},
        {"name": "dblow", "description": "股息率", "weight": 2, "ascending": False},
        {"name": "dv_ratio", "description": "剩余年限", "weight": 4, "ascending": False},
        {"name": "pct_chg_5_stk", "description": "剩余年限", "weight": 3, "ascending": True},
        {"name": "ps_ttm", "description": "正股年化波动率", "weight": 2, "ascending": True},
        {"name": "ytm", "description": "正股年化波动率", "weight": 3, "ascending": True}
    ]

    # 计算启用止盈情况的综合指标
    results = calculate_bonds_cagr(
        df, start_date, end_date, hold_num, min_price, max_price, factors, None
    )

    # 打印各项指标结果
    print("策略绩效指标:")
    print(f"年化收益率: {results['cagr']:.6f}")
    print(f"最大回撤率: {results['max_drawdown']:.6f}")
    print(f"夏普比率: {results['sharpe_ratio']:.6f}")
    print(f"索提诺比率: {results['sortino_ratio']:.6f}")
    print(f"卡玛比率: {results['calmar_ratio']:.6f}")
    
    # 准备生成HTML报告
    # 使用函数中已经格式化好的收益率序列
    daily_returns = results['quantstats_returns']
    
    # 输出收益率序列的信息供检查
    print(f"\n收益率序列信息:")
    print(f"- 总长度: {len(daily_returns)}")
    print(f"- 平均值: {daily_returns.mean():.6f}")
    print(f"- 累计产品: {(1 + daily_returns).prod() - 1:.6f}")
    print(f"- 第一个日期: {daily_returns.index[0]}")
    print(f"- 最后一个日期: {daily_returns.index[-1]}")
    
    # 准备因子描述文本
    factor_desc = "因子组合详情:\n"
    for factor in factors:
        factor_desc += f"- {factor['description']} ({factor['name']}): 权重={factor['weight']}, "
        factor_desc += f"排序方向={'升序' if factor['ascending'] else '降序'}\n"
    
    factor_desc += f"\n筛选条件:\n- 持有数量: {hold_num}只\n- 价格区间: {min_price}-{max_price}元"
    if SP:
        factor_desc += f"\n- 止盈设置: {SP*100}%"
    
    # 生成HTML报告
    strategy_name = f"可转债多因子策略 (持有{hold_num}只)"
    report_path = generate_quantstats_report(
        returns=daily_returns,
        benchmark=benchmark,
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy_name,
        factor_desc=factor_desc

    )
    
    if report_path:
        print(f"\nHTML报告已生成: {report_path}")

    # 生成Excel格式的报告用于对比
    excel_report_path = generate_excel_report(
        results['daily_selected_bonds'],
        results['daily_returns'],
        output_dir=None,
        start_date=start_date,
        end_date=end_date
    )

    print(f"Excel报告已生成: {excel_report_path}")
