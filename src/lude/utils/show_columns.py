import os
import pandas as pd
from lude.config.paths import DATA_DIR

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
    
    print(df.head())
    print(df['amount'])
    # 获取列名
    columns = df.columns.tolist()
    
    # 获取索引信息
    index_names = df.index.names
    
    print("=" * 50)
    print(f"文件: {file_path}")
    print("=" * 50)
    
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
