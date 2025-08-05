#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
内存监控工具
提供内存使用情况监控和预警功能
"""

import os
from lude.utils.logger import optimization_logger as logger

# 可选依赖：psutil用于内存监控
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil模块未安装，内存监控功能将被禁用")


def get_memory_info():
    """获取当前内存使用信息"""
    if not PSUTIL_AVAILABLE:
        return {
            'process_memory_mb': 0,
            'system_memory_percent': 0,
            'system_available_gb': 0,
            'system_total_gb': 0
        }
    
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    system_memory = psutil.virtual_memory()
    
    return {
        'process_memory_mb': memory_info.rss / 1024 / 1024,  # 进程内存使用(MB)
        'system_memory_percent': system_memory.percent,       # 系统内存使用率
        'system_available_gb': system_memory.available / 1024 / 1024 / 1024,  # 可用内存(GB)
        'system_total_gb': system_memory.total / 1024 / 1024 / 1024  # 总内存(GB)
    }


def check_memory_warning(warning_threshold=80.0, critical_threshold=90.0):
    """检查内存使用情况并发出预警
    
    Args:
        warning_threshold: 警告阈值（百分比）
        critical_threshold: 严重阈值（百分比）
        
    Returns:
        str: 内存状态 ('normal', 'warning', 'critical')
    """
    if not PSUTIL_AVAILABLE:
        logger.debug("psutil不可用，跳过内存检查")
        return 'normal'
    
    memory_info = get_memory_info()
    
    if memory_info['system_memory_percent'] >= critical_threshold:
        logger.error(f"🚨 内存使用严重警告: {memory_info['system_memory_percent']:.1f}% "
                    f"(可用: {memory_info['system_available_gb']:.1f}GB, "
                    f"进程: {memory_info['process_memory_mb']:.0f}MB)")
        logger.error("建议立即: 1) 减少并发数 2) 重启优化器 3) 检查系统资源")
        return 'critical'
    elif memory_info['system_memory_percent'] >= warning_threshold:
        logger.warning(f"⚠️  内存使用警告: {memory_info['system_memory_percent']:.1f}% "
                      f"(可用: {memory_info['system_available_gb']:.1f}GB, "
                      f"进程: {memory_info['process_memory_mb']:.0f}MB)")
        logger.warning("建议: 1) 监控内存变化 2) 考虑减少并发数")
        return 'warning'
    else:
        logger.info(f"✅ 内存使用正常: {memory_info['system_memory_percent']:.1f}% "
                   f"(可用: {memory_info['system_available_gb']:.1f}GB, "
                   f"进程: {memory_info['process_memory_mb']:.0f}MB)")
        return 'normal'


def log_memory_stats():
    """记录详细的内存统计信息"""
    if not PSUTIL_AVAILABLE:
        logger.info("=" * 50)
        logger.info("内存监控: psutil模块不可用，无法获取内存统计信息")
        logger.info("如需内存监控功能，请安装: pip install psutil")
        logger.info("=" * 50)
        return
        
    memory_info = get_memory_info()
    logger.info("=" * 50)
    logger.info("内存使用统计:")
    logger.info(f"  系统总内存: {memory_info['system_total_gb']:.1f} GB")
    logger.info(f"  系统可用内存: {memory_info['system_available_gb']:.1f} GB")
    logger.info(f"  系统内存使用率: {memory_info['system_memory_percent']:.1f}%")
    logger.info(f"  当前进程内存: {memory_info['process_memory_mb']:.0f} MB")
    logger.info("=" * 50)