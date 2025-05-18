#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
JSON合并工具 - 合并多个目录下的high_performance_factors.json文件到一个文件中
"""

import os
import json
import glob
import argparse
from typing import Dict, List, Any, Optional
from pathlib import Path


def find_json_files(base_dir: str, pattern: str = "lude_*_fac*_num*") -> List[str]:
    """
    查找符合模式的所有目录下的high_performance_factors.json文件

    Args:
        base_dir: 基础目录路径
        pattern: 目录名匹配模式

    Returns:
        符合条件的JSON文件路径列表
    """
    json_files = []
    
    # 构建搜索模式，查找所有匹配的目录
    search_pattern = os.path.join(base_dir, pattern, "lude/src/lude/data/high_performance_factors.json")
    json_files = glob.glob(search_pattern)
    
    if not json_files:
        print(f"警告: 在 {search_pattern} 下未找到任何JSON文件")
    
    return json_files


def extract_metadata_from_path(file_path: str) -> Dict[str, Any]:
    """
    从文件路径中提取元数据（fac和num参数）

    Args:
        file_path: JSON文件的完整路径

    Returns:
        包含元数据的字典
    """
    # 从路径中提取目录名
    dir_name = file_path.split(os.sep)
    
    # 查找包含fac和num的目录名
    metadata = {}
    for part in dir_name:
        if "fac" in part and "num" in part:
            # 尝试提取fac和num的值
            try:
                parts = part.split("_")
                for i, item in enumerate(parts):
                    if item.startswith("fac"):
                        metadata["factor_count"] = int(item[3:])
                    if item.startswith("num"):
                        metadata["model_number"] = int(item[3:])
            except (ValueError, IndexError):
                print(f"警告: 无法从 {part} 提取元数据")
    
    return metadata


def merge_json_files(json_files: List[str], output_file: str) -> None:
    """
    合并多个JSON文件并保存为一个文件

    Args:
        json_files: 要合并的JSON文件路径列表
        output_file: 输出文件路径
    """
    merged_data = {}
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取元数据
            metadata = extract_metadata_from_path(file_path)
            
            # 使用目录名作为键
            key = f"fac{metadata.get('factor_count', 'unknown')}_num{metadata.get('model_number', 'unknown')}"
            merged_data[key] = {
                "metadata": metadata,
                "data": data
            }
            
            print(f"已处理: {file_path}")
        except Exception as e:
            print(f"处理 {file_path} 时出错: {str(e)}")
    
    # 保存合并后的数据
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print(f"合并完成! 结果已保存到: {output_file}")
    except Exception as e:
        print(f"保存合并数据时出错: {str(e)}")


def main():
    """
    主函数 - 解析参数并执行合并逻辑
    """
    parser = argparse.ArgumentParser(description='合并多个目录下的high_performance_factors.json文件')
    parser.add_argument('--base-dir', type=str, default='/root/autodl-tmp',
                        help='基础目录路径，默认为 /root/autodl-tmp')
    parser.add_argument('--pattern', type=str, default='lude_*_fac*_num*',
                        help='目录名匹配模式，默认为 lude_*_fac*_num*')
    parser.add_argument('--output', type=str, default='/root/merged_factors.json',
                        help='输出文件路径，默认为 /root/merged_factors.json')
    
    args = parser.parse_args()
    
    # 查找JSON文件
    json_files = find_json_files(args.base_dir, args.pattern)
    
    if json_files:
        print(f"找到 {len(json_files)} 个JSON文件")
        
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(args.output)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 合并文件
        merge_json_files(json_files, args.output)
    else:
        print("未找到任何符合条件的JSON文件，无法执行合并操作")


if __name__ == "__main__":
    # 使用默认参数
    # python /Users/zhaolei/My/python/lude/src/lude/utils/json_merger.py

    # 或者自定义参数
    # python /Users/zhaolei/My/python/lude/src/lude/utils/json_merger.py --base-dir /root/autodl-tmp --pattern "lude_100_150_hold5_fac*_num*" --output /root/merged_high_performance_factors.json
    main()
