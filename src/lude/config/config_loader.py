#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置加载模块
负责加载和管理YAML配置文件
"""

import os
import yaml
from typing import Dict, Any, Optional

from lude.config.paths import OPTIMIZATION_CONFIG_PATH
from lude.utils.logger import logging

class ConfigLoader:
    """配置加载器类
    
    用于加载和访问YAML配置文件中的配置项
    支持缓存和默认值
    """
    
    _config_cache: Dict[str, Any] = {}
    
    @classmethod
    def load_config(cls, config_path: str) -> Dict[str, Any]:
        """加载指定路径的配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        # 检查缓存
        if config_path in cls._config_cache:
            return cls._config_cache[config_path]
        
        try:
            # 检查文件是否存在
            if not os.path.exists(config_path):
                logger.error(f"配置文件不存在: {config_path}")
                return {}
                
            # 加载YAML文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 缓存配置
            cls._config_cache[config_path] = config
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    @classmethod
    def get_config_value(cls, config_path: str, key_path: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            config_path: 配置文件路径
            key_path: 键路径，使用点号分隔，如 "notification.dingtalk.cagr_threshold"
            default: 默认值，如果配置项不存在则返回此值
            
        Returns:
            配置值或默认值
        """
        config = cls.load_config(config_path)
        if not config:
            return default
            
        # 按点号分隔键路径
        keys = key_path.split('.')
        
        # 逐层查找键值
        current = config
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
            
        return current

# 便捷函数，直接从优化配置文件获取配置
def get_optimization_config(key_path: str, default: Any = None) -> Any:
    """从优化配置文件获取配置
    
    Args:
        key_path: 配置键路径，使用点号分隔
        default: 默认值
        
    Returns:
        配置值或默认值
    """
    return ConfigLoader.get_config_value(OPTIMIZATION_CONFIG_PATH, key_path, default)
