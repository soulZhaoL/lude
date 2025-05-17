#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
因子组合保存器模块
负责保存和加载高绩效因子组合
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from lude.config.paths import HIGH_PERFORMANCE_FACTORS_PATH
from lude.utils.logger import optimization_logger as logger


def save_high_performance_factors(
    factors: List[Dict[str, Any]], 
    cagr: float, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """保存高绩效因子组合到文件
    
    Args:
        factors: 因子组合列表，每个元素为包含name,description,weight,ascending的字典
        cagr: 年化收益率
        metadata: 额外的元数据信息，如开始日期、结束日期、策略名称等
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        # 确保结果目录存在
        os.makedirs(os.path.dirname(HIGH_PERFORMANCE_FACTORS_PATH), exist_ok=True)
        
        # 当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建新的因子组合记录
        factor_record = {
            "timestamp": current_time,
            "cagr": cagr,
            "factors": factors
        }
        
        # 添加可选元数据
        if metadata:
            factor_record.update(metadata)
            
        # 尝试加载现有文件
        existing_records = []
        if os.path.exists(HIGH_PERFORMANCE_FACTORS_PATH):
            try:
                with open(HIGH_PERFORMANCE_FACTORS_PATH, 'r', encoding='utf-8') as f:
                    existing_records = json.load(f)
                    # 确保加载的是列表
                    if not isinstance(existing_records, list):
                        existing_records = []
            except json.JSONDecodeError:
                logger.warning(f"加载现有因子组合文件失败，将创建新文件")
                existing_records = []
                
        # 添加新记录
        existing_records.append(factor_record)
        
        # 写入文件
        with open(HIGH_PERFORMANCE_FACTORS_PATH, 'w', encoding='utf-8') as f:
            json.dump(existing_records, f, ensure_ascii=False, indent=2)
            
        logger.info(f"已保存高绩效因子组合 (CAGR: {cagr:.6f}) 到文件")
        return True
        
    except Exception as e:
        logger.error(f"保存高绩效因子组合时出错: {e}")
        return False


def load_high_performance_factors() -> List[Dict[str, Any]]:
    """加载所有保存的高绩效因子组合
    
    Returns:
        因子组合记录列表，每个记录包含timestamp, cagr, factors等信息
    """
    if not os.path.exists(HIGH_PERFORMANCE_FACTORS_PATH):
        logger.warning(f"高绩效因子组合文件不存在: {HIGH_PERFORMANCE_FACTORS_PATH}")
        return []
        
    try:
        with open(HIGH_PERFORMANCE_FACTORS_PATH, 'r', encoding='utf-8') as f:
            records = json.load(f)
            
        if not isinstance(records, list):
            logger.warning(f"因子组合文件格式不正确，应为列表")
            return []
            
        return records
    except Exception as e:
        logger.error(f"加载高绩效因子组合时出错: {e}")
        return []


def find_similar_factor_combination(
    factors: List[Dict[str, Any]], 
    threshold: float = 0.8
) -> Optional[Dict[str, Any]]:
    """查找类似的因子组合
    
    比较两个因子组合的相似度，如果相似度高于阈值，则认为是类似的组合
    相似度计算基于因子名称、权重和排序方向的匹配程度
    
    Args:
        factors: 要查找的因子组合
        threshold: 相似度阈值，默认0.8
        
    Returns:
        如果找到类似组合，返回该组合记录；否则返回None
    """
    records = load_high_performance_factors()
    if not records:
        return None
        
    factor_names = set(f['name'] for f in factors)
    factor_dict = {f['name']: (f['weight'], f['ascending']) for f in factors}
    
    for record in records:
        record_factors = record.get('factors', [])
        record_factor_names = set(f['name'] for f in record_factors)
        
        # 计算名称交集占比
        name_intersection = len(factor_names.intersection(record_factor_names))
        name_union = len(factor_names.union(record_factor_names))
        name_similarity = name_intersection / name_union if name_union > 0 else 0
        
        # 如果名称相似度不够，继续检查下一个
        if name_similarity < threshold:
            continue
            
        # 计算权重和排序方向的匹配度
        weight_direction_matches = 0
        total_comparisons = 0
        
        for name in factor_names.intersection(record_factor_names):
            current_weight, current_asc = factor_dict[name]
            
            # 查找相应因子
            for rf in record_factors:
                if rf['name'] == name:
                    record_weight, record_asc = rf['weight'], rf['ascending']
                    
                    # 权重相同加0.5分，方向相同加0.5分
                    if current_weight == record_weight:
                        weight_direction_matches += 0.5
                    if current_asc == record_asc:
                        weight_direction_matches += 0.5
                        
                    total_comparisons += 1
                    break
        
        weight_dir_similarity = weight_direction_matches / total_comparisons if total_comparisons > 0 else 0
        
        # 计算综合相似度
        combined_similarity = (name_similarity + weight_dir_similarity) / 2
        
        if combined_similarity >= threshold:
            return record
            
    return None
