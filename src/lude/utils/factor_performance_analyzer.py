"""
因子组合绩效分析器

从优化结果文件中提取最佳因子组合，并计算其绩效指标。
"""

import concurrent.futures
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from tqdm import tqdm

from lude.config.paths import DATA_DIR, HIGH_PERFORMANCE_FACTORS4_1_PATH, HIGH_PERFORMANCE_FACTORS4_2_PATH, HIGH_PERFORMANCE_FACTORS4_3_PATH, HIGH_PERFORMANCE_FACTORS4_4_PATH, HIGH_PERFORMANCE_FACTORS5_1_PATH, HIGH_PERFORMANCE_FACTORS5_2_PATH, HIGH_PERFORMANCE_FACTORS6_1_PATH, HIGH_PERFORMANCE_FACTORS6_2_PATH
from lude.config.paths import DINGDING_OPT_RESULT_PATH_TEST, PROJECT_ROOT
from lude.core.cagr_calculator import calculate_bonds_cagr
from lude.core.overfitting_detector import check_overfitting


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
    从JSON文件中提取最佳因子组合及其元数据
    支持两种格式:
    1. 旧格式: 直接的因子组合列表
    2. 新格式: 嵌套的对象，包含多个模型组，每个模型组有自己的元数据和数据数组

    参数:
        json_file: 高性能因子组合JSON文件路径

    返回:
        results: 包含因子组合及元数据的结果列表
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # 检查是否为新格式（嵌套对象）或旧格式（列表）
        if isinstance(json_data, dict):
            print(f"检测到新格式JSON文件: {json_file}")
            return extract_from_nested_json(json_data)
        elif isinstance(json_data, list):
            print(f"检测到旧格式JSON文件: {json_file}")
            return extract_from_flat_json(json_data)
        else:
            print(f"错误: JSON文件{json_file}格式不正确，应为对象或列表")
            return []

    except json.JSONDecodeError:
        print(f"错误: 无法解析JSON文件{json_file}")
        return []
    except Exception as e:
        print(f"读取JSON文件{json_file}时出错: {e}")
        return []


def extract_from_flat_json(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从旧格式的平面JSON数据中提取因子组合

    参数:
        records: JSON数据列表

    返回:
        valid_records: 有效的因子组合记录列表
    """
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


def extract_from_nested_json(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从新格式的嵌套JSON数据中提取因子组合

    参数:
        json_data: 嵌套的JSON数据对象

    返回:
        all_records: 从所有模型组中提取的因子组合记录列表
    """
    all_records = []

    # 遍历所有模型组
    for model_key, model_data in json_data.items():
        print(f"处理模型组: {model_key}")

        # 检查模型组数据结构
        if not isinstance(model_data, dict) or 'data' not in model_data:
            print(f"警告: 模型组 {model_key} 格式不正确，跳过")
            continue

        # 提取元数据（如果有）
        metadata = model_data.get('metadata', {})
        model_records = model_data.get('data', [])

        if not isinstance(model_records, list):
            print(f"警告: 模型组 {model_key} 的数据不是列表，跳过")
            continue

        # 处理每条记录
        for record in model_records:
            if not isinstance(record, dict):
                continue

            if 'factors' not in record or not isinstance(record['factors'], list):
                continue

            # 确保record中有expected_cagr字段
            if 'expected_cagr' not in record and 'cagr' in record:
                record['expected_cagr'] = record['cagr']

            # 添加模型组信息
            record['model_group'] = model_key
            if metadata:
                record['model_metadata'] = metadata

            all_records.append(record)

    print(f"从嵌套JSON中提取了 {len(all_records)} 条记录")
    return all_records


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
    result, df, start_date, end_date, hold_num, min_price, max_price, threshold_num, take_profit_rate, enable_overfitting_check = args

    factors = result['factors']

    # 格式化因子名称，以便于显示
    factor_names = [f"{factor['name']} ({factor['weight']}{'↑' if factor['ascending'] else '↓'})"
                    for factor in factors]
    factor_str = ', '.join(factor_names)

    # 计算绩效指标 - 使用统一的cagr_calculator.py
    try:
        perf = calculate_bonds_cagr(
            df=df.copy(),  # 传入数据副本避免修改原数据
            start_date=start_date,
            end_date=end_date,
            hold_num=hold_num,
            min_price=min_price,
            max_price=max_price,
            rank_factors=factors,
            threshold_num=threshold_num,
            filter_conditions=None,  # 暂不使用额外的筛选条件
            check_overfitting=False,  # 在外部进行过拟合检测
            verbose_overfitting=False,
            return_details=True  # 返回详细信息
        )

        # 进行过拟合检测（如果启用）
        if enable_overfitting_check:
            overfitting_result = check_overfitting(
                df=perf['processed_df'],  # 使用处理后的数据框，包含filter列
                daily_selected_bonds=perf['daily_selected_bonds'],
                res=perf['daily_returns'],
                hold_num=hold_num,
                min_trading_days_ratio=0.80,
                verbose=False  # 多线程环境下关闭详细输出
            )
        else:
            # 创建空的过拟合检测结果
            overfitting_result = {
                'overall': {'overfitting_detected': False, 'warning_messages': []},
                'trading_days_coverage': {'coverage_ratio': None, 'days_with_successful_selection': None},
                'candidate_pool_sufficiency': {'insufficient_days_count': None, 'avg_daily_candidates': None, 'min_daily_candidates': None},
                'stock_concentration': None,
                'time_stability': None
            }

        # 将因子组合转换为JSON格式
        factors_json = json.dumps(factors, ensure_ascii=False)

        # 格式化过拟合检测结果摘要
        if enable_overfitting_check:
            overfitting_summary = "通过" if not overfitting_result['overall']['overfitting_detected'] else "过拟合"
            warning_summary = "; ".join(overfitting_result['overall']['warning_messages']) if overfitting_result['overall']['warning_messages'] else "无警告"
        else:
            overfitting_summary = "未检测"
            warning_summary = "已禁用过拟合检测"

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
            '过拟合检测': overfitting_summary,
            '过拟合警告': warning_summary,
            # 过拟合检测详细结果
            '交易日覆盖率': overfitting_result['trading_days_coverage']['coverage_ratio'],
            '成功选股天数': overfitting_result['trading_days_coverage']['days_with_successful_selection'],
            '候选池不足天数': overfitting_result['candidate_pool_sufficiency']['insufficient_days_count'],
            '平均候选数': overfitting_result['candidate_pool_sufficiency']['avg_daily_candidates'],
            '最少候选数': overfitting_result['candidate_pool_sufficiency']['min_daily_candidates'],
            '成功': True,
            '日志': f"因子组合: {factor_str}\n计算结果 - 实际CAGR: {perf['cagr']:.6f}\n" + \
                    (
                        f"预期CAGR: {result['expected_cagr']:.6f}, 差异: {perf['cagr'] - result['expected_cagr']:.6f}\n" if result.get(
                            'expected_cagr') else "") + \
                    f"最大回撤: {perf['max_drawdown']:.6f}, 夏普比率: {perf['sharpe_ratio']:.6f}\n" + \
                    f"过拟合检测: {overfitting_summary}"
        }

        # 添加选股集中度信息（如果有）
        if overfitting_result['stock_concentration']:
            stock_conc = overfitting_result['stock_concentration']
            performance['选股标的总数'] = stock_conc.get('total_unique_stocks', 0)
            performance['最高频标的占比'] = stock_conc.get('top_stock_ratio', 0)
            performance['前5标的占比'] = stock_conc.get('top5_stocks_ratio', 0)

        # 添加时间稳定性信息（如果有）
        if overfitting_result['time_stability']:
            time_stab = overfitting_result['time_stability']
            performance['时间段数'] = time_stab.get('window_count', 0)
            performance['CAGR变异系数'] = time_stab.get('cagr_cv', 0)
            performance['CAGR均值'] = time_stab.get('cagr_mean', 0)
            performance['CAGR标准差'] = time_stab.get('cagr_std', 0)

        # 添加模型组信息（如果有）
        if 'model_group' in result:
            performance['模型组'] = result.get('model_group')

        # 添加模型元数据（如果有）
        if 'model_metadata' in result:
            metadata = result.get('model_metadata', {})
            if 'factor_count' in metadata:
                performance['因子数量(元数据)'] = metadata.get('factor_count')
            if 'model_number' in metadata:
                performance['模型编号'] = metadata.get('model_number')

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
            '过拟合检测': '计算失败',
            '过拟合警告': f'绩效计算异常: {str(e)}',
            # 过拟合检测详细结果 - 设为None以保持列结构一致
            '交易日覆盖率': None,
            '成功选股天数': None,
            '候选池不足天数': None,
            '平均候选数': None,
            '最少候选数': None,
            '选股标的总数': None,
            '最高频标的占比': None,
            '前5标的占比': None,
            '时间段数': None,
            'CAGR变异系数': None,
            'CAGR均值': None,
            'CAGR标准差': None,
            '错误信息': str(e),
            '成功': False,
            '日志': f"因子组合: {factor_str}\n计算失败: {e}"
        }

        # 添加模型组信息（如果有）
        if 'model_group' in result:
            performance['模型组'] = result.get('model_group')

        # 添加模型元数据（如果有）
        if 'model_metadata' in result:
            metadata = result.get('model_metadata', {})
            if 'factor_count' in metadata:
                performance['因子数量(元数据)'] = metadata.get('factor_count')
            if 'model_number' in metadata:
                performance['模型编号'] = metadata.get('model_number')

    return performance


def _generate_output_files(
    performance_df: pd.DataFrame, 
    output_file: str, 
    enable_overfitting_check: bool, 
    generate_detailed_report: bool
) -> None:
    """
    生成输出文件：主要文件和详细文件
    
    参数:
        performance_df: 绩效分析结果DataFrame
        output_file: 主输出文件路径
        enable_overfitting_check: 是否启用了过拟合检测
        generate_detailed_report: 是否生成详细报告
    """
    # 定义核心字段
    core_fields = [
        '优化时间', '策略类型', '预期CAGR', '实际CAGR', 'CAGR差异', 
        '最大回撤', '夏普比率', '索提诺比率', '卡玛比率', 
        '因子数量', '因子组合', '因子JSON', '成功'
    ]
    
    # 如果启用了过拟合检测，添加核心过拟合字段
    if enable_overfitting_check:
        core_fields.extend(['过拟合检测', '过拟合警告', '交易日覆盖率'])
    
    # 添加模型相关字段（如果存在）
    if '模型组' in performance_df.columns:
        core_fields.append('模型组')
    if '模型编号' in performance_df.columns:
        core_fields.append('模型编号')
    if '因子数量(元数据)' in performance_df.columns:
        core_fields.append('因子数量(元数据)')
    
    # 过滤出存在的字段
    available_core_fields = [field for field in core_fields if field in performance_df.columns]
    
    # 生成主要文件（核心指标）
    main_df = performance_df[available_core_fields].copy()
    print(f"\n保存主要结果到文件: {output_file}")
    main_df.to_excel(output_file, index=False)
    print(f"主要结果已保存到: {output_file}")
    
    # 生成详细文件（如果启用）
    if generate_detailed_report and enable_overfitting_check:
        # 生成详细文件路径
        file_dir = os.path.dirname(output_file)
        file_name = os.path.basename(output_file)
        name_without_ext = os.path.splitext(file_name)[0]
        detailed_file = os.path.join(file_dir, f"{name_without_ext}_detailed.xlsx")
        
        print(f"保存详细结果到文件: {detailed_file}")
        performance_df.to_excel(detailed_file, index=False)
        print(f"详细结果已保存到: {detailed_file}")
        
        print(f"\n文件说明:")
        print(f"  - 主要文件 ({os.path.basename(output_file)}): 包含核心绩效指标和过拟合检测结果")
        print(f"  - 详细文件 ({os.path.basename(detailed_file)}): 包含完整的过拟合检测细节")
    elif not enable_overfitting_check:
        print(f"\n注意: 过拟合检测已禁用，仅生成核心绩效指标文件")


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
        max_workers: int = None,  # 最大线程数，默认为None (CPU核心数 * 5)
        enable_overfitting_check: bool = True  # 是否启用过拟合检测
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
        enable_overfitting_check: 是否启用过拟合检测，默认为True

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
    args_list = [(result, df, start_date, end_date, hold_num, min_price, max_price, threshold_num, take_profit_rate, enable_overfitting_check)
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
        print(f"\n[{i + 1}/{total}] {perf['日志']}")

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
        max_workers: int = 10,  # 最大线程数，默认为None (CPU核心数 * 5)
        enable_overfitting_check: bool = True,  # 是否启用过拟合检测
        generate_detailed_report: bool = True   # 是否生成详细报告
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
        enable_overfitting_check: 是否启用过拟合检测，默认为True
        generate_detailed_report: 是否生成详细报告（包含所有过拟合检测字段），默认为True
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

    # 统计模型组信息
    model_groups = {}
    for result in factor_results:
        model_group = result.get('model_group', '未分组')
        if model_group not in model_groups:
            model_groups[model_group] = 0
        model_groups[model_group] += 1

    print(f"共解析出 {len(factor_results)} 个因子组合")

    # 输出模型组统计信息
    if model_groups and len(model_groups) > 1:  # 只有当有多个模型组时才输出统计信息
        print("模型组统计:")
        for group, count in model_groups.items():
            print(f"  - {group}: {count} 个因子组合")

    print(f"正在计算绩效指标...")
    print(f"参数配置: 持仓数={hold_num}, 价格范围={min_price}-{max_price}, "
          f"日期={start_date}-{end_date}, 止盈={take_profit_rate}, 轮动阈值={threshold_num}")
    print(f"过拟合检测: {'启用' if enable_overfitting_check else '禁用'}")
    print(f"详细报告: {'生成' if generate_detailed_report else '仅主要指标'}")
    
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
        max_workers=max_workers,  # 传递线程池大小参数
        enable_overfitting_check=enable_overfitting_check
    )

    # 按实际CAGR排序，处理可能的None值
    if '实际CAGR' in performance_df.columns:
        # 先将None值替换为NaN，以便排序
        performance_df['实际CAGR'] = pd.to_numeric(performance_df['实际CAGR'], errors='coerce')
        # 按CAGR降序排序，NaN值放在最后
        performance_df = performance_df.sort_values(by='实际CAGR', ascending=False, na_position='last')

    # 统计过拟合检测结果
    if enable_overfitting_check and '过拟合检测' in performance_df.columns:
        overfitting_stats = performance_df['过拟合检测'].value_counts()
        print(f"\n过拟合检测结果统计:")
        for status, count in overfitting_stats.items():
            print(f"  - {status}: {count} 个因子组合")
        
        # 显示过拟合因子组合的详细信息
        overfitted_df = performance_df[performance_df['过拟合检测'] == '过拟合']
        if len(overfitted_df) > 0:
            print(f"\n检测到 {len(overfitted_df)} 个过拟合因子组合:")
            for idx, row in overfitted_df.head(5).iterrows():  # 只显示前5个
                cagr_value = row.get('实际CAGR', 'N/A')
                cagr_str = f"{cagr_value:.4f}" if pd.notnull(cagr_value) and cagr_value != 'N/A' else 'N/A'
                print(f"  - {row['因子组合'][:50]}... (CAGR: {cagr_str})")
                if row.get('过拟合警告') and row['过拟合警告'] != '无警告':
                    print(f"    警告: {row['过拟合警告']}")

    # 生成输出文件
    _generate_output_files(performance_df, output_file, enable_overfitting_check, generate_detailed_report)
    
    # 为用户提供一些使用建议
    if enable_overfitting_check and '过拟合检测' in performance_df.columns:
        total_factors = len(performance_df)
        passed_factors = len(performance_df[performance_df['过拟合检测'] == '通过'])
        print(f"\n建议:")
        print(f"  - 总共分析了 {total_factors} 个因子组合")
        print(f"  - 其中 {passed_factors} 个通过过拟合检测，建议优先考虑")
        print(f"  - 主要文件包含核心指标，详细文件包含完整的过拟合检测结果")


if __name__ == '__main__':
    # 使用示例:
    # 
    # 1. 默认运行（启用过拟合检测）:
    # python factor_performance_analyzer.py
    # 
    # 2. 禁用过拟合检测（快速分析）:
    # python factor_performance_analyzer.py --disable_overfitting_check
    # 
    # 3. 只生成主要文件（不生成详细报告）:
    # python factor_performance_analyzer.py --no_detailed_report
    # 
    # 4. 自定义参数:
    # python factor_performance_analyzer.py --max_workers=16 --hold_num=10 --min_price=120 --max_price=160
    #
    # 5. 完全自定义:
    # python factor_performance_analyzer.py --disable_overfitting_check --no_detailed_report --max_workers=8

    import argparse

    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='因子组合绩效分析器')
    # parser.add_argument('--opt_file', type=str, help='优化结果文件路径')
    parser.add_argument('--cb_data_file', type=str, help='可转债数据文件路径')
    parser.add_argument('--output_file', type=str, help='输出文件路径')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期，格式为YYYYMMDD')
    parser.add_argument('--end_date', type=str, default='20250824', help='回测结束日期，格式为YYYYMMDD')
    parser.add_argument('--hold_num', type=int, default=5, help='持有数量')
    parser.add_argument('--min_price', type=float, default=100.0, help='最低价格筛选')
    parser.add_argument('--max_price', type=float, default=200.0, help='最高价格筛选')
    parser.add_argument('--threshold_num', type=int, help='轮动阈值')
    parser.add_argument('--take_profit_rate', type=float, default=0.06, help='止盈比例，默认为0.06 (6%%)')
    parser.add_argument('--max_workers', type=int, help='最大线程数，默认为CPU核心数乘以5')
    
    # 新增的过拟合检测控制参数
    parser.add_argument('--disable_overfitting_check', action='store_true', 
                       help='禁用过拟合检测(提高分析速度)')
    parser.add_argument('--no_detailed_report', action='store_true',
                       help='不生成详细报告,仅生成主要指标文件')

    args = parser.parse_args()

    path = HIGH_PERFORMANCE_FACTORS4_1_PATH
    # path = HIGH_PERFORMANCE_FACTORS4_2_PATH
    # path = HIGH_PERFORMANCE_FACTORS4_3_PATH
    # path = HIGH_PERFORMANCE_FACTORS4_4_PATH
    # path = HIGH_PERFORMANCE_FACTORS5_1_PATH
    # path = HIGH_PERFORMANCE_FACTORS5_2_PATH
    # path = HIGH_PERFORMANCE_FACTORS5_3_PATH
    # path = HIGH_PERFORMANCE_FACTORS5_4_PATH
    # path = HIGH_PERFORMANCE_FACTORS6_1_PATH
    # path = HIGH_PERFORMANCE_FACTORS6_2_PATH
    # path = HIGH_PERFORMANCE_FACTORS6_3_PATH
    # path = HIGH_PERFORMANCE_FACTORS6_4_PATH
    # output_path 路径等于path 移除文件部分
    output_path = path.replace('merged_factors.json', '')
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_path, f'factor_performance_results_test_{current_time}.xlsx')
    # 调用主函数
    main(
        opt_file=path,
        cb_data_file=args.cb_data_file,
        output_file=output_file,
        start_date=args.start_date,
        end_date=args.end_date,
        hold_num=args.hold_num,
        min_price=args.min_price,
        max_price=args.max_price,
        threshold_num=args.threshold_num,
        take_profit_rate=args.take_profit_rate,
        max_workers=args.max_workers,
        enable_overfitting_check=not args.disable_overfitting_check,  # 默认启用，除非明确禁用
        generate_detailed_report=not args.no_detailed_report          # 默认生成，除非明确禁用
    )
