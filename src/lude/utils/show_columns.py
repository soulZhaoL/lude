import os
import pandas as pd
from lude.config.paths import DATA_DIR

def get_date_range_info(df):
    """
    获取数据集的日期范围信息
    
    参数:
        df: pandas DataFrame
    
    返回:
        dict: 包含开始日期、结束日期等信息
    """
    date_info = {}
    
    # 检查索引是否包含日期信息
    if hasattr(df.index, 'levels'):  # MultiIndex
        for level_idx, level in enumerate(df.index.levels):
            if pd.api.types.is_datetime64_any_dtype(level):
                dates = level
                date_info[f'index_level_{level_idx}'] = {
                    'start_date': dates.min(),
                    'end_date': dates.max(),
                    'level_name': df.index.names[level_idx]
                }
                break
    elif pd.api.types.is_datetime64_any_dtype(df.index):  # Single datetime index
        date_info['index'] = {
            'start_date': df.index.min(),
            'end_date': df.index.max(),
            'level_name': df.index.name
        }
    
    # 检查是否有日期相关的列
    date_columns = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_columns.append(col)
            date_info[f'column_{col}'] = {
                'start_date': df[col].min(),
                'end_date': df[col].max(),
                'level_name': col
            }
    
    # 检查可能的日期字符串列（如'date', 'trade_date'等）
    potential_date_cols = [col for col in df.columns if any(term in col.lower() for term in ['date', 'time', '日期'])]
    for col in potential_date_cols:
        if col not in date_columns:  # 避免重复处理
            try:
                # 尝试转换为日期类型并获取范围
                temp_dates = pd.to_datetime(df[col], errors='coerce')
                if not temp_dates.isna().all():
                    date_info[f'column_{col}'] = {
                        'start_date': temp_dates.min(),
                        'end_date': temp_dates.max(),
                        'level_name': col
                    }
            except:
                pass
    
    return date_info

def print_date_range_info(date_info):
    """打印日期范围信息"""
    if not date_info:
        print("\n未找到日期信息")
        return
    
    print("\n数据集日期范围信息:")
    print("=" * 50)
    
    for key, info in date_info.items():
        source_type = "索引" if "index" in key else "列"
        level_name = info['level_name'] or "未命名"
        
        print(f"\n{source_type}: {level_name}")
        print("-" * 30)
        print(f"开始日期: {info['start_date']}")
        print(f"结束日期: {info['end_date']}")
        
        # 计算时间跨度
        if pd.notna(info['start_date']) and pd.notna(info['end_date']):
            duration = info['end_date'] - info['start_date']
            print(f"时间跨度: {duration.days} 天")

def show_parquet_columns(file_path):
    """
    显示 parquet 文件的所有列名和索引信息
    
    参数:
        file_path: parquet 文件路径
    """
    # 设置pandas显示选项，不省略中间的列
    pd.set_option('display.max_columns', None)  # 显示所有列
    pd.set_option('display.width', 1000)        # 设置显示宽度
    pd.set_option('display.max_colwidth', 20)   # 设置每列的最大宽度，避免过长
    
    # 读取 parquet 文件
    df = pd.read_parquet(file_path)
    
    # 获取日期范围信息
    date_info = get_date_range_info(df)
    
    print(df.head())
    print(df['amount'])
    print("conv_prem")
    print(df['conv_prem'])
    # 获取列名
    columns = df.columns.tolist()
    
    # 获取索引信息
    index_names = df.index.names
    
    print("=" * 50)
    print(f"文件: {file_path}")
    print("=" * 50)
    
    # 打印日期范围信息
    print_date_range_info(date_info)
    
    # 打印索引信息
    print("\n索引信息:")
    print("-" * 30)
    for idx, name in enumerate(index_names):
        if name is not None:
            print(f"{idx+1}. {name}")
    
    # 打印列名信息
    print("\n列名信息:")
    print("-" * 30)
    for idx, col in enumerate(columns):
        # print(f"{idx+1}. {col}")
        print(f"'{col}',")
    
    # 打印数据形状
    print("\n数据形状:")
    print("-" * 30)
    print(f"行数: {df.shape[0]}")
    print(f"列数: {df.shape[1]}")
    
    # 打印数据类型信息
    # print("\n数据类型信息:")
    # print("-" * 30)
    # for col, dtype in df.dtypes.items():
    #     print(f"{col}: {dtype}")
    
    # 返回列名列表
    return columns

def categorize_factors(columns):
    """
    将因子分类为不同的组
    
    Args:
        columns: 列名列表（因子名称）
    
    Returns:
        dict: 分类后的因子字典，键为分类名称，值为该分类下的因子列表
    """
    # 初始化各个分类
    categories = {
        "价格相关因子": [],
        "成交量/流动性相关因子": [],
        "价值相关因子": [],
        "溢价率相关因子": [],
        "技术指标因子": [],
        "基本面相关因子": [],
        "时间/日期相关因子": [],
        "其他因子": []
    }
    
    # 分类规则
    for col in columns:
        # 价格相关因子
        if any(term in col.lower() for term in ['price', 'close', 'open', 'high', 'low', '价格', '收盘', '开盘', '最高', '最低']):
            categories["价格相关因子"].append(col)
        
        # 成交量/流动性相关因子
        elif any(term in col.lower() for term in ['volume', 'vol', 'turnover', 'liquidity', '成交量', '换手率', '流动性']):
            categories["成交量/流动性相关因子"].append(col)
        
        # 价值相关因子
        elif any(term in col.lower() for term in ['pe', 'pb', 'ps', 'pcf', 'ev', 'ebitda', 'roe', 'roa', '市盈率', '市净率', '市销率']):
            categories["价值相关因子"].append(col)
        
        # 溢价率相关因子
        elif any(term in col.lower() for term in ['premium', 'discount', '溢价率', '折价率']):
            categories["溢价率相关因子"].append(col)
        
        # 技术指标因子
        elif any(term in col.lower() for term in ['ma', 'ema', 'sma', 'rsi', 'macd', 'kdj', 'boll', 'atr', 'momentum', 'oscillator', 'pc']):
            categories["技术指标因子"].append(col)
        
        # 基本面相关因子
        elif any(term in col.lower() for term in ['profit', 'revenue', 'income', 'debt', 'asset', 'liability', 'cash', 'dividend', 'growth', '利润', '收入', '资产', '负债', '现金', '股息']):
            categories["基本面相关因子"].append(col)
        
        # 时间/日期相关因子
        elif any(term in col.lower() for term in ['date', 'time', 'day', 'month', 'year', 'period', '日期', '时间', '天数', '月份', '年份', '周期']):
            categories["时间/日期相关因子"].append(col)
        
        # 其他因子
        else:
            categories["其他因子"].append(col)
    
    # 过滤掉空分类
    return {k: v for k, v in categories.items() if v}

def show_categorized_factors(categories):
    """显示分类后的因子"""
    print("\n因子分类结果:")
    print("=" * 50)
    
    for category, factors in categories.items():
        print(f"\n{category} ({len(factors)}个):")
        print("-" * 30)
        for idx, factor in enumerate(factors):
            print(f"  {idx+1}. {factor}")

if __name__ == "__main__":
    # 指定 parquet 文件路径
    cb_data_path = os.path.join(DATA_DIR, 'cb_data.pq')
    
    # 显示列名
    columns = show_parquet_columns(cb_data_path)
    
    # 对因子进行分类
    categories = categorize_factors(columns)
    
    # 显示分类结果
    show_categorized_factors(categories)
    
    # 保存分类结果到文件
    with open("factor_categories.txt", "w", encoding="utf-8") as f:
        f.write("因子分类结果:\n")
        f.write("=" * 50 + "\n")
        
        for category, factors in categories.items():
            f.write(f"\n{category} ({len(factors)}个):\n")
            f.write("-" * 30 + "\n")
            for idx, factor in enumerate(factors):
                f.write(f"  {idx+1}. {factor}\n")
    
    print(f"\n分类结果已保存到 'factor_categories.txt'")
