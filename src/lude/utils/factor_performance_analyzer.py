"""
因子组合绩效分析器

从优化结果文件中提取最佳因子组合，并计算其绩效指标。
"""

import os
import re
import sys
import json
import pandas as pd
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from tqdm import tqdm
from lude.config.paths import DINGDING_OPT_RESULT_PATH, HIGH_PERFORMANCE_FACTORS_PATH, DINGDING_OPT_RESULT_PATH_TEST


# 添加项目根目录到路径，确保能够导入自定义模块
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from lude.utils.performance_metrics import calculate_performance_metrics
from lude.config.paths import DATA_DIR


def parse_factor_combination(text: str) -> List[Dict[str, Any]]:
    """
    从文本中解析因子组合
    
    参数:
        text: 包含因子组合的文本块
    
    返回:
        factor_list: 解析后的因子列表
    """
    factor_list = []
    
    # 提取最佳因子组合部分
    # 注意：使用非贪婪模式捕获因子描述，能处理描述中包含括号的情况
    factor_pattern = r'\d+\.\s+(\S+)\s+\((.+?)\)\s+\(权重:\s+(\d+),\s+(升序|降序)\)'
    
    # 查找所有匹配项
    factor_matches = re.finditer(factor_pattern, text)
    
    for match in factor_matches:
        factor_name = match.group(1)
        factor_desc = match.group(2)
        weight = int(match.group(3))
        direction = match.group(4)
        
        # 确定排序方向
        ascending = direction == '升序'
        
        factor_dict = {
            'name': factor_name,
            'description': factor_desc,
            'weight': weight,
            'ascending': ascending
        }
        factor_list.append(factor_dict)
    
    return factor_list


def extract_from_txt_file(opt_file: str) -> List[Dict[str, Any]]:
    """
    从钉钉文本文件(dd_opt.txt)中提取最佳因子组合及其元数据
    
    参数:
        opt_file: 优化结果文本文件路径
    
    返回:
        results: 包含因子组合及元数据的结果列表
    """
    with open(opt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分割文件内容为多个优化结果块
    result_blocks = re.split(r'【可转债优化新结果】', content)
    
    # 去除第一个空块
    if not result_blocks[0].strip():
        result_blocks = result_blocks[1:]
    
    results = []
    
    for i, block in enumerate(result_blocks):
        if not block.strip():
            continue
            
        # 提取优化时间
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', block)
        timestamp = timestamp_match.group(1) if timestamp_match else None
        
        # 提取预期CAGR
        cagr_match = re.search(r'年化收益率\(CAGR\):\s+([\d.]+)', block)
        expected_cagr = float(cagr_match.group(1)) if cagr_match else None
        
        # 提取策略类型
        strategy_match = re.search(r'策略:\s+(\w+)', block)
        strategy = strategy_match.group(1) if strategy_match else None
        
        # 提取最佳因子组合
        factor_block_match = re.search(r'最佳因子组合:(.*?)(?=\n\n|\Z)', block, re.DOTALL)
        
        if not factor_block_match:
            continue
            
        factor_block = factor_block_match.group(1)
        factor_list = parse_factor_combination(factor_block)
        
        if factor_list:
            results.append({
                'timestamp': timestamp,
                'expected_cagr': expected_cagr,
                'strategy': strategy,
                'factors': factor_list
            })
    
    return results


def extract_from_json_file(json_file: str) -> List[Dict[str, Any]]:
    """
    从JSON文件(high_performance_factors.json)中提取最佳因子组合及其元数据
    
    参数:
        json_file: 高性能因子组合JSON文件路径
    
    返回:
        results: 包含因子组合及元数据的结果列表
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        # 检查加载的数据是否为列表
        if not isinstance(records, list):
            print(f"错误: JSON文件{json_file}格式不正确，应为列表")
            return []
        
        # 不需要特殊处理，因为JSON格式已经是我们期望的格式
        # 但添加一个验证步骤确保每个记录都有必要的字段
        valid_records = []
        for record in records:
            if not isinstance(record, dict):
                continue
                
            if 'factors' not in record or not isinstance(record['factors'], list):
                continue
                
            if 'cagr' not in record and 'expected_cagr' not in record:
                # 尝试从元数据中获取CAGR值
                continue
            
            # 确保record中有expected_cagr字段
            if 'expected_cagr' not in record and 'cagr' in record:
                record['expected_cagr'] = record['cagr']
                
            valid_records.append(record)
            
        return valid_records
        
    except json.JSONDecodeError:
        print(f"错误: 无法解析JSON文件{json_file}")
        return []
    except Exception as e:
        print(f"读取JSON文件{json_file}时出错: {e}")
        return []


def extract_factor_combinations_with_metadata(opt_file: str) -> List[Dict[str, Any]]:
    """
    从优化结果文件中提取最佳因子组合及其元数据
    根据文件扩展名自动选择适当的解析方法
    
    参数:
        opt_file: 优化结果文件路径
    
    返回:
        results: 包含因子组合及元数据的结果列表
    """
    if not os.path.exists(opt_file):
        raise FileNotFoundError(f"文件不存在: {opt_file}")
        
    # 根据文件扩展名选择解析方法
    file_ext = os.path.splitext(opt_file)[1].lower()
    
    if file_ext == '.json':
        print("检测到JSON格式文件，使用JSON解析器")
        return extract_from_json_file(opt_file)
    else:  # 默认为TXT文件或其他文本格式
        print("使用文本解析器解析钉钉优化结果")
        return extract_from_txt_file(opt_file)


def process_single_factor_combination(args):
    """
    处理单个因子组合并计算其绩效指标
    
    参数:
        args: 包含所有必要参数的字典
    
    返回:
        performance: 包含绩效指标的字典
    """
    result, df, start_date, end_date, hold_num, min_price, max_price, threshold_num, take_profit_rate = args
    
    factors = result['factors']
    
    # 格式化因子名称，以便于显示
    factor_names = [f"{factor['name']} ({factor['weight']}{'↑' if factor['ascending'] else '↓'})" 
                   for factor in factors]
    factor_str = ', '.join(factor_names)
    
    # 计算绩效指标
    try:
        perf = calculate_performance_metrics(
            df=df,
            start_date=start_date,
            end_date=end_date,
            hold_num=hold_num,
            min_price=min_price,
            max_price=max_price,
            rank_factors=factors,
            threshold_num=threshold_num,
            take_profit_rate=take_profit_rate
        )
        
        # 将因子组合转换为JSON格式
        factors_json = json.dumps(factors, ensure_ascii=False)
        
        # 记录计算结果
        performance = {
            '优化时间': result.get('timestamp'),
            '策略类型': result.get('strategy'),
            '预期CAGR': result.get('expected_cagr'),
            '实际CAGR': perf['cagr'],
            'CAGR差异': perf['cagr'] - (result.get('expected_cagr') or 0),
            '最大回撤': perf['max_drawdown'],
            '夏普比率': perf['sharpe_ratio'],
            '索提诺比率': perf['sortino_ratio'],
            '卡玛比率': perf['calmar_ratio'],
            '因子数量': len(factors),
            '因子组合': factor_str,
            '因子JSON': factors_json,
            '成功': True,
            '日志': f"因子组合: {factor_str}\n计算结果 - 实际CAGR: {perf['cagr']:.6f}\n" + \
                  (f"预期CAGR: {result['expected_cagr']:.6f}, 差异: {perf['cagr'] - result['expected_cagr']:.6f}\n" if result.get('expected_cagr') else "") + \
                  f"最大回撤: {perf['max_drawdown']:.6f}, 夏普比率: {perf['sharpe_ratio']:.6f}"
        }
        
    except Exception as e:
        # 将因子组合转换为JSON格式
        factors_json = json.dumps(factors, ensure_ascii=False)
        
        # 记录失败信息
        performance = {
            '优化时间': result.get('timestamp'),
            '策略类型': result.get('strategy'),
            '预期CAGR': result.get('expected_cagr'),
            '实际CAGR': None,
            'CAGR差异': None,
            '最大回撤': None,
            '夏普比率': None,
            '索提诺比率': None,
            '卡玛比率': None,
            '因子数量': len(factors),
            '因子组合': factor_str,
            '因子JSON': factors_json,
            '错误信息': str(e),
            '成功': False,
            '日志': f"因子组合: {factor_str}\n计算失败: {e}"
        }
    
    return performance


def calculate_factor_performances(
    factor_results: List[Dict[str, Any]], 
    data_file: str,
    start_date: str,
    end_date: str,
    hold_num: int,
    min_price: float,
    max_price: float, 
    threshold_num: Optional[int] = None,
    take_profit_rate: Optional[float] = 0.06,
    max_workers: int = None  # 最大线程数，默认为None (CPU核心数 * 5)
) -> pd.DataFrame:
    """
    使用多线程计算所有因子组合的绩效指标
    
    参数:
        factor_results: 包含因子组合及元数据的结果列表
        data_file: 可转债数据文件路径
        start_date: 开始日期，格式'YYYYMMDD'
        end_date: 结束日期，格式'YYYYMMDD'
        hold_num: 持有数量
        min_price: 最低价格筛选
        max_price: 最高价格筛选
        threshold_num: 轮动阈值，默认为None
        take_profit_rate: 止盈比例，默认为0.06 (6%)
        max_workers: 最大线程数，默认为None (CPU核心数 * 5)
        
    返回:
        performance_df: 包含所有因子组合绩效指标的DataFrame
    """
    print(f"加载可转债数据: {data_file}")
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"找不到可转债数据文件: {data_file}")
        
    df = pd.read_parquet(data_file)
    print(f"数据加载成功，共 {len(df)} 条记录")
    
    total = len(factor_results)
    print(f"\n开始多线程计算 {total} 个因子组合的绩效指标...")
    
    # 准备线程池参数
    args_list = [(result, df, start_date, end_date, hold_num, min_price, max_price, threshold_num, take_profit_rate) 
                for result in factor_results]
    
    # 使用线程池并行处理
    performances = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 使用tqdm显示进度条
        futures = list(tqdm(
            executor.map(process_single_factor_combination, args_list),
            total=len(args_list),
            desc="计算进度"
        ))
        
        # 收集结果
        performances = futures
    
    # 输出计算结果摘要
    success_count = sum(1 for p in performances if p.get('成功', False))
    print(f"\n计算完成: 成功 {success_count}/{total} 个因子组合")
    
    # 输出每个组合的日志
    for i, perf in enumerate(performances):
        print(f"\n[{i+1}/{total}] {perf['日志']}")
    
    # 转换为DataFrame
    performance_df = pd.DataFrame(performances)
    
    return performance_df


def main(
    opt_file: str = None, 
    cb_data_file: str = None,
    output_file: str = None,
    start_date: str = '20220729',
    end_date: str = '20250328',
    hold_num: int = 5,
    min_price: float = 100.0,
    max_price: float = 150.0,
    threshold_num: Optional[int] = None,
    take_profit_rate: Optional[float] = 0.06,
    max_workers: int = 10  # 最大线程数，默认为None (CPU核心数 * 5)
):
    """
    主函数 - 允许通过参数灵活控制计算过程
    
    参数:
        opt_file: 优化结果文件路径，默认为DATA_DIR下的dd_opt.txt
        cb_data_file: 可转债数据文件路径，默认会自动搜索
        output_file: 输出文件路径，默认在项目根目录生成带时间戳的文件
        start_date: 回测开始日期，默认'20220729'
        end_date: 回测结束日期，默认'20250328'
        hold_num: 持有数量，默认5
        min_price: 最低价格筛选，默认100.0
        max_price: 最高价格筛选，默认150.0
        threshold_num: 轮动阈值，默认为None
        take_profit_rate: 止盈比例，默认为0.06 (6%)
    """
    # 设置默认的输入输出文件路径
    if opt_file is None:
        # opt_file = os.path.join(DATA_DIR, 'dd_opt_copy.txt')
        opt_file = os.path.join(DATA_DIR, 'dd_opt.txt')
        
    if cb_data_file is None:
        # 尝试在几个可能的位置查找数据文件
        possible_paths = [
            os.path.join(DATA_DIR, 'cb_data.pq'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                cb_data_file = path
                break
        
        # 如果还找不到，提示用户手动输入
        if cb_data_file is None:
            print("警告: 找不到可转债数据文件，请指定正确路径")
            cb_data_file = input("请输入可转债数据文件的绝对路径: ")
    
    # 设置默认输出文件名
    if output_file is None:
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(PROJECT_ROOT, f'factor_performance_results_{current_time}.xlsx')
    
    print(f"正在读取优化结果文件: {opt_file}")
    factor_results = extract_factor_combinations_with_metadata(opt_file)
    print(f"共解析出 {len(factor_results)} 个因子组合")
    
    print(f"正在计算绩效指标...")
    print(f"参数配置: 持仓数={hold_num}, 价格范围={min_price}-{max_price}, "
          f"日期={start_date}-{end_date}, 止盈={take_profit_rate}, 轮动阈值={threshold_num}")
    # 计算绩效指标
    performance_df = calculate_factor_performances(
        factor_results=factor_results,
        data_file=cb_data_file,
        start_date=start_date,
        end_date=end_date,
        hold_num=hold_num,
        min_price=min_price,
        max_price=max_price,
        threshold_num=threshold_num,
        take_profit_rate=take_profit_rate,
        max_workers=max_workers  # 传递线程池大小参数
    )
    
    # 按实际CAGR排序
    if '实际CAGR' in performance_df.columns:
        performance_df = performance_df.sort_values(by='实际CAGR', ascending=False)
    
    # 保存结果到Excel文件
    print(f"保存结果到文件: {output_file}")
    performance_df.to_excel(output_file, index=False)
    print(f"结果已保存到: {output_file}")


if __name__ == '__main__':
    # 使用默认线程数（CPU核心数 * 5）
    # python factor_performance_analyzer.py --opt_file=/path/to/dd_opt.txt
    # python factor_performance_analyzer.py --opt_file=/data/high_performance_factors.json

    # 指定线程数为16
    # python factor_performance_analyzer.py --opt_file=/path/to/dd_opt.txt --max_workers=16

    # 同时指定其他参数
    # python factor_performance_analyzer.py --opt_file=/path/to/dd_opt.txt --max_workers=16 --hold_num=10 --min_price=120 --max_price=160
    

    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='因子组合绩效分析器')
    # parser.add_argument('--opt_file', type=str, help='优化结果文件路径')
    parser.add_argument('--cb_data_file', type=str, help='可转债数据文件路径')
    parser.add_argument('--output_file', type=str, help='输出文件路径')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期，格式为YYYYMMDD')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期，格式为YYYYMMDD')
    parser.add_argument('--hold_num', type=int, default=5, help='持有数量')
    parser.add_argument('--min_price', type=float, default=100.0, help='最低价格筛选')
    parser.add_argument('--max_price', type=float, default=150.0, help='最高价格筛选')
    parser.add_argument('--threshold_num', type=int, help='轮动阈值')
    parser.add_argument('--take_profit_rate', type=float, default=0.06, help='止盈比例，默认为0.06 (6%)')
    parser.add_argument('--max_workers', type=int, help='最大线程数，默认为CPU核心数 * 5')
    
    args = parser.parse_args()
    
    # 调用主函数
    main(
        opt_file=DINGDING_OPT_RESULT_PATH_TEST,
        cb_data_file=args.cb_data_file,
        output_file=args.output_file,
        start_date=args.start_date,
        end_date=args.end_date,
        hold_num=args.hold_num,
        min_price=args.min_price,
        max_price=args.max_price,
        threshold_num=args.threshold_num,
        take_profit_rate=args.take_profit_rate,
        max_workers=args.max_workers
    )
