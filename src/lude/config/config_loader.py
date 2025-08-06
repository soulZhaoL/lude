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

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器类 - 严格模式：禁止任何默认配置
    
    用于加载和访问YAML配置文件中的配置项
    支持缓存，严格要求所有配置文件和配置项都必须存在
    """
    
    _config_cache: Dict[str, Any] = {}
    
    @classmethod
    def load_config(cls, config_path: str) -> Dict[str, Any]:
        """加载指定路径的配置文件 - 严格模式
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            Exception: 配置文件加载失败
        """
        # 检查缓存
        if config_path in cls._config_cache:
            return cls._config_cache[config_path]
        
        # 🚨 严格原则：配置文件必须存在
        if not os.path.exists(config_path):
            error_msg = f"配置文件不存在: {config_path}。严格模式：禁止使用任何默认配置！"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # 加载YAML文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 🚨 严格原则：配置文件不能为空
            if config is None:
                error_msg = f"配置文件为空或格式错误: {config_path}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 缓存配置
            cls._config_cache[config_path] = config
            logger.debug(f"成功加载配置文件: {config_path}")
            return config
            
        except Exception as e:
            error_msg = f"加载配置文件失败: {config_path}. 错误: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    @classmethod  
    def get_config_value(cls, config_path: str, key_path: str) -> Any:
        """获取配置值 - 严格模式：配置项必须存在
        
        Args:
            config_path: 配置文件路径
            key_path: 键路径，使用点号分隔，如 "notification.dingtalk.cagr_threshold"
            
        Returns:
            配置值
            
        Raises:
            KeyError: 配置项不存在
        """
        config = cls.load_config(config_path)
        
        # 按点号分隔键路径
        keys = key_path.split('.')
        
        # 逐层查找键值 - 严格模式：每一层都必须存在
        current = config
        for i, key in enumerate(keys):
            if not isinstance(current, dict):
                error_msg = f"配置路径错误: '{'.'.join(keys[:i])}' 不是字典类型。配置文件: {config_path}"
                logger.error(error_msg)
                raise KeyError(error_msg)
                
            if key not in current:
                error_msg = f"配置项不存在: '{key_path}' (缺少键: '{key}')。配置文件: {config_path}"
                logger.error(error_msg)
                raise KeyError(error_msg)
                
            current = current[key]
            
        return current

# 便捷函数，直接从优化配置文件获取配置 - 严格模式
def get_optimization_config(key_path: str) -> Any:
    """从优化配置文件获取配置 - 严格模式：配置项必须存在
    
    Args:
        key_path: 配置键路径，使用点号分隔
        
    Returns:
        配置值
        
    Raises:
        KeyError: 配置项不存在
        FileNotFoundError: 配置文件不存在
    """
    return ConfigLoader.get_config_value(OPTIMIZATION_CONFIG_PATH, key_path)
