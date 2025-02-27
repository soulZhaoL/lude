#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
合并脚本：整合format_basket.py和excel_merge_util.py的功能
1. 首先处理禄得可转债行情表，生成basket_strategy.csv
2. 然后合并csv目录下的所有csv文件，生成最终的result.csv
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
    # 设置CSV文件夹路径
    csv_dir = os.path.join(script_dir, 'csv')
    os.makedirs(csv_dir, exist_ok=True)
    
    # 获取CSV文件夹下所有以"禄得可转债行情表"开头的csv文件
    input_files = glob.glob(os.path.join(csv_dir, '禄得可转债行情表*.csv'))
    
    if len(input_files) == 0:
        raise FileNotFoundError("未找到以'禄得可转债行情表'开头的CSV文件")
    elif len(input_files) > 1:
        raise ValueError(f"找到多个符合条件的CSV文件: {input_files}，请确保只有一个文件")
    
    input_file = input_files[0]
    output_file = os.path.join(csv_dir, 'basket_strategy.csv')
    
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

def merge_excel(csv_dir: str, output_path: str) -> None:
    """
    合并csv目录下的所有csv文件，生成最终的result.csv
    注意：会排除掉"禄得可转债行情表"开头的文件
    
    Args:
        csv_dir: csv目录的路径
        output_path: 输出文件的完整路径
    """
    # 获取所有CSV文件
    csv_files = glob.glob(os.path.join(csv_dir, "*.csv"))
    
    # 排除"禄得可转债行情表"开头的文件
    csv_files = [f for f in csv_files if not os.path.basename(f).startswith('禄得可转债行情表')]
    
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

def recalculate_weights(file_path: str) -> None:
    """
    重新计算CSV文件中的权重（第四列）
    
    Args:
        file_path: CSV文件路径
    """
    try:
        # 读取CSV文件
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        # 重新计算权重（第四列）
        if df.shape[1] >= 4 and len(df) > 0:
            weight = 1 / len(df)
            df.iloc[:, 3] = weight
            print(f"已重新计算权重: {weight}")
            
            # 保存文件
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"文件已保存: {file_path}")
        else:
            print("警告：文件列数不足或没有数据，无法计算权重")
            
    except Exception as e:
        print(f"处理文件时发生错误: {str(e)}")
        raise

def merge_files():
    """执行文件合并操作"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_dir = os.path.join(script_dir, 'csv')
    
    try:
        # 第一步：处理禄得可转债行情表
        print("开始处理禄得可转债行情表...")
        basket_file = format_basket(script_dir)
        print(f"已生成文件：{basket_file}")
        
        # 第二步：合并CSV文件
        print("\n开始合并CSV文件...")
        output_path = "/Users/zhaolei/Downloads/result.csv"
        merge_excel(csv_dir, output_path)
        print(f"\n合并完成！结果文件：{output_path}")
        
    except Exception as e:
        print(f"错误：{str(e)}")
        raise

def show_menu():
    """显示操作菜单"""
    print("\n=== 可转债数据处理工具 ===")
    print("1. 合并文件")
    print("2. 重新计算权重")
    print("0. 退出")
    print("=====================")

def main():
    """主函数：提供交互式菜单"""
    while True:
        show_menu()
        choice = input("请选择操作 (0-2): ").strip()
        
        if choice == "0":
            print("程序已退出")
            break
            
        elif choice == "1":
            print("\n执行文件合并操作...")
            merge_files()
            
        elif choice == "2":
            print("\n执行重新计算权重...")
            try:
                file_path = "/Users/zhaolei/Downloads/result.csv"
                if not os.path.exists(file_path):
                    print(f"错误：文件不存在：{file_path}")
                    continue
                recalculate_weights(file_path)
            except Exception as e:
                print(f"错误：{str(e)}")
            
        else:
            print("\n无效的选择，请重试")
        
        input("\n按回车键继续...")

if __name__ == "__main__":
    main()
