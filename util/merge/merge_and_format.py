#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
合并脚本：整合format_basket.py和excel_merge_util.py的功能
1. 首先处理禄得可转债行情表，生成basket_strategy.csv
2. 然后合并excel_merge目录下的所有csv文件，生成最终的result.csv
"""

import csv
import os
import glob
import pandas as pd
from typing import List, Dict

def format_basket(script_dir: str) -> str:
    """
    处理禄得可转债行情表，生成basket_strategy.csv
    
    Args:
        script_dir: 脚本所在目录路径
        
    Returns:
        str: 生成的basket_strategy.csv的完整路径
    """
    # 切换到format2basket目录
    format_basket_dir = os.path.join(script_dir, 'format2basket')
    os.chdir(format_basket_dir)
    
    # 获取当前目录下所有以"禄得可转债行情表"开头的csv文件
    input_files = glob.glob('禄得可转债行情表*.csv')
    
    if len(input_files) == 0:
        raise FileNotFoundError("未找到以'禄得可转债行情表'开头的CSV文件")
    elif len(input_files) > 1:
        raise ValueError(f"找到多个符合条件的CSV文件: {input_files}，请确保只有一个文件")
    
    input_file = input_files[0]
    
    # 输出CSV文件路径（在excel_merge目录下）
    output_dir = os.path.join(script_dir, 'excel_merge')
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'basket_strategy.csv')
    
    # 读取原始文件
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # 准备新CSV需要的表头
    fieldnames = ["代码", "市场", "数量", "相对权重", "方向", "转债名称"]
    new_rows = []
    
    # 只取前5条记录
    for i in range(min(5, len(rows))):
        bond_code = rows[i]["转债代码"]
        bond_name = rows[i]["转债名称"]
        
        code_part, market_part = bond_code.split(".")
        
        new_rows.append({
            "代码": code_part,
            "市场": market_part,
            "数量": 0,
            "相对权重": 0,
            "方向": 0,
            "转债名称": bond_name
        })
    
    # 将处理结果写入新的CSV文件
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in new_rows:
            writer.writerow(row)
    
    return output_file

def merge_excel(excel_merge_dir: str, output_path: str) -> None:
    """
    合并excel_merge目录下的所有csv文件，生成最终的result.csv
    
    Args:
        excel_merge_dir: excel_merge目录的路径
        output_path: 输出文件的完整路径
    """
    # 切换到excel_merge目录
    os.chdir(excel_merge_dir)
    
    # 获取所有CSV文件
    csv_files = glob.glob(os.path.join(os.getcwd(), "*.csv"))
    
    # 创建一个空的DataFrame用于存储合并后的数据
    merged_df = pd.DataFrame()
    
    # 遍历所有CSV文件并尝试不同编码读取
    for file in csv_files:
        for encoding in ['utf-8', 'gbk', 'latin1', 'iso-8859-1']:
            try:
                df = pd.read_csv(file, encoding=encoding)
                print(f"{file} 成功使用编码 '{encoding}' 读取")
                break
            except Exception:
                continue
        else:
            print(f"{file} 无法读取")
            continue
        
        # 合并数据
        merged_df = pd.concat([merged_df, df], ignore_index=True)
    
    # 去除重复行（以第一列为基础去重）
    if not merged_df.empty:
        merged_df.drop_duplicates(subset=[merged_df.columns[0]], inplace=True)
        
        # 计算权重并将第四列的值设置为权重，使其总和为1
        if merged_df.shape[1] >= 4:
            total_rows = len(merged_df)
            if total_rows > 0:
                weight = 1 / total_rows
                merged_df.iloc[:, 3] = weight
    
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # 将合并后的数据保存为新的CSV文件
        merged_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"合并完成！已生成文件：{output_path}")
    else:
        print("警告：没有找到可以合并的数据")

def main():
    """主函数：按顺序执行所有操作"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # 第一步：处理禄得可转债行情表
        print("开始处理禄得可转债行情表...")
        basket_file = format_basket(script_dir)
        print(f"已生成文件：{basket_file}")
        
        # 第二步：合并CSV文件
        print("\n开始合并CSV文件...")
        excel_merge_dir = os.path.join(script_dir, 'excel_merge')
        output_path = "/Users/zhaolei/Downloads/result.csv"
        merge_excel(excel_merge_dir, output_path)
        
    except Exception as e:
        print(f"错误：{str(e)}")
        raise

if __name__ == "__main__":
    main()
