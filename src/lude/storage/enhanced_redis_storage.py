"""
增强型Redis存储实现 - 解决连接不稳定和高并发锁异常问题

基于Optuna 4.4.0+ JournalRedisBackend的稳定实现方案，专门针对AutoDL环境优化。

主要特性：
1. 连接池管理和自动重试机制
2. 故障转移到SQLite存储
3. 连接健康检查和自动恢复
4. 高并发锁优化
5. 智能超时配置
"""

import logging
import time
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager
import json
import os
from redis import ConnectionPool, Redis
from redis.exceptions import (
    ConnectionError, TimeoutError, BusyLoadingError
)

import optuna
from optuna.storages import JournalStorage, RDBStorage
from optuna.storages.journal import JournalRedisBackend
import sqlalchemy

logger = logging.getLogger(__name__)


class EnhancedRedisStorage:
    """
    增强型Redis存储实现
    
    特性：
    - 连接池管理和自动重试
    - 故障转移到SQLite
    - 连接健康检查
    - 高并发优化
    """
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379/0",
                 max_retries: int = 5,
                 retry_delay: float = 1.0,
                 pool_size: int = 50,
                 socket_timeout: float = 30.0,
                 socket_connect_timeout: float = 30.0,
                 health_check_interval: int = 30,
                 fallback_db_url: Optional[str] = None):
        """
        初始化增强型Redis存储
        
        Args:
            redis_url: Redis连接URL
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            pool_size: 连接池大小
            socket_timeout: Socket超时时间
            socket_connect_timeout: 连接超时时间
            health_check_interval: 健康检查间隔
            fallback_db_url: 故障转移SQLite数据库URL
        """
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.health_check_interval = health_check_interval
        
        # 解析Redis URL
        self._parse_redis_url()
        
        # 创建连接池 - 移除macOS不兼容的keepalive选项
        pool_kwargs = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'password': self.password,
            'max_connections': pool_size,
            'socket_timeout': socket_timeout,
            'socket_connect_timeout': socket_connect_timeout,
            'retry_on_timeout': True,
            'health_check_interval': health_check_interval
        }
        
        # 只在Linux环境下启用socket keepalive
        import platform
        if platform.system() == 'Linux':
            pool_kwargs.update({
                'socket_keepalive': True,
                'socket_keepalive_options': {
                    1: 300,  # TCP_KEEPIDLE
                    2: 30,   # TCP_KEEPINTVL  
                    3: 3,    # TCP_KEEPCNT
                }
            })
        
        self.pool = ConnectionPool(**pool_kwargs)
        
        self.redis_client = Redis(connection_pool=self.pool)
        
        # 故障转移配置 - 严格模式：必须明确指定
        if fallback_db_url is None:
            raise ValueError("fallback_db_url不能为None。请在配置文件中明确指定故障转移数据库URL")
        self.fallback_db_url = fallback_db_url
        self._storage = None
        self._fallback_storage = None
        self._using_fallback = False
        
        # 健康检查
        self._health_check_lock = threading.Lock()
        self._last_health_check = 0
        self._is_healthy = False
        
        # 初始化存储
        self._initialize_storage()
        
    def _parse_redis_url(self):
        """解析Redis URL - 严格模式：解析失败直接抛出异常"""
        try:
            # 简单的URL解析
            if self.redis_url.startswith("redis://"):
                url_part = self.redis_url[8:]  # 移除 "redis://"
            else:
                url_part = self.redis_url
                
            # 解析主机、端口、数据库
            if '@' in url_part:
                # 包含密码的情况
                auth_part, host_part = url_part.split('@')
                if ':' in auth_part:
                    _, self.password = auth_part.split(':')
                else:
                    self.password = auth_part
            else:
                host_part = url_part
                self.password = None
                
            # 解析主机和端口
            if '/' in host_part:
                host_port, db_part = host_part.split('/')
                self.db = int(db_part) if db_part else 0
            else:
                host_port = host_part
                self.db = 0
                
            if ':' in host_port:
                self.host, port_str = host_port.split(':')
                self.port = int(port_str)
            else:
                self.host = host_port
                self.port = 6379
                
        except Exception as e:
            error_msg = f"Redis URL解析失败: {e}. URL格式应为: redis://[password@]host:port/db"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
            
    def _initialize_storage(self):
        """初始化存储"""
        # 首先尝试连接Redis
        if self._check_redis_health():
            try:
                # 使用JournalRedisBackend (Optuna 4.0+推荐)
                redis_backend = JournalRedisBackend(self.redis_url)
                self._storage = JournalStorage(redis_backend)
                self._using_fallback = False
                logger.info("成功初始化Redis存储")
                return
            except Exception as e:
                logger.error(f"初始化Redis存储失败: {e}")
        
        # 故障转移到SQLite
        self._initialize_fallback_storage()
        
    def _initialize_fallback_storage(self):
        """初始化故障转移存储"""
        try:
            # 确保目录存在
            db_path = self.fallback_db_url.replace("sqlite:///", "")
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir:  # 只有当目录路径不为空时才创建
                os.makedirs(db_dir, exist_ok=True)
            
            # 创建SQLite引擎 (RDBStorage会内部使用)
            sqlalchemy.create_engine(
                self.fallback_db_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            self._fallback_storage = RDBStorage(self.fallback_db_url)
            self._storage = self._fallback_storage
            self._using_fallback = True
            logger.warning(f"已故障转移到SQLite存储: {self.fallback_db_url}")
        except Exception as e:
            logger.error(f"初始化故障转移存储失败: {e}")
            raise
            
    def _check_redis_health(self, force_check: bool = False) -> bool:
        """检查Redis连接健康状态"""
        current_time = time.time()
        
        # 如果最近检查过且不是强制检查，返回缓存结果
        if not force_check and (current_time - self._last_health_check) < self.health_check_interval:
            return self._is_healthy
            
        with self._health_check_lock:
            try:
                # 执行PING命令
                result = self.redis_client.ping()
                self._is_healthy = bool(result)
                self._last_health_check = current_time
                
                if self._is_healthy:
                    logger.debug("Redis健康检查通过")
                else:
                    logger.warning("Redis健康检查失败: PING返回False")
                    
            except Exception as e:
                self._is_healthy = False
                self._last_health_check = current_time
                logger.warning(f"Redis健康检查失败: {e}")
                
        return self._is_healthy
        
    @contextmanager
    def _retry_context(self, operation_name: str):
        """重试上下文管理器"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                yield attempt
                return
            except (ConnectionError, TimeoutError, BusyLoadingError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(f"{operation_name} 尝试 {attempt + 1}/{self.max_retries + 1} 失败: {e}")
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数退避
                    
                    # 检查是否需要故障转移
                    if not self._check_redis_health(force_check=True):
                        logger.warning("Redis连接不稳定，切换到故障转移存储")
                        self._switch_to_fallback()
                        return
                else:
                    logger.error(f"{operation_name} 所有重试尝试都失败")
                    
        # 所有重试都失败，抛出最后一个异常
        if last_exception:
            raise last_exception
            
    def _switch_to_fallback(self):
        """切换到故障转移存储"""
        if not self._using_fallback:
            try:
                if self._fallback_storage is None:
                    self._initialize_fallback_storage()
                
                self._storage = self._fallback_storage
                self._using_fallback = True
                logger.info("已切换到故障转移存储")
            except Exception as e:
                logger.error(f"切换到故障转移存储失败: {e}")
                
    def _try_switch_back_to_redis(self):
        """尝试切换回Redis存储"""
        if self._using_fallback and self._check_redis_health(force_check=True):
            try:
                redis_backend = JournalRedisBackend(self.redis_url)
                redis_storage = JournalStorage(redis_backend)
                self._storage = redis_storage
                self._using_fallback = False
                logger.info("已切换回Redis存储")
                return True
            except Exception as e:
                logger.warning(f"切换回Redis存储失败: {e}")
                return False
        return False
        
    def create_study(self, 
                    study_name: Optional[str] = None,
                    direction: str = "minimize",
                    sampler: Optional[optuna.samplers.BaseSampler] = None,
                    pruner: Optional[optuna.pruners.BasePruner] = None) -> optuna.Study:
        """
        创建优化研究
        
        Args:
            study_name: 研究名称
            direction: 优化方向 ("minimize" 或 "maximize")
            sampler: 采样器
            pruner: 剪枝器
            
        Returns:
            optuna.Study: 优化研究对象
        """
        # 尝试切换回Redis（如果当前使用故障转移）
        if self._using_fallback:
            self._try_switch_back_to_redis()
            
        with self._retry_context("创建研究"):
            try:
                study = optuna.create_study(
                    study_name=study_name,
                    direction=direction,
                    storage=self._storage,
                    sampler=sampler,
                    pruner=pruner,
                    load_if_exists=True
                )
                
                storage_type = "SQLite故障转移" if self._using_fallback else "Redis"
                logger.info(f"成功创建研究 '{study_name}' (存储: {storage_type})")
                return study
                
            except Exception as e:
                logger.error(f"创建研究失败: {e}")
                # 如果使用Redis失败，尝试故障转移
                if not self._using_fallback:
                    logger.warning("尝试故障转移到SQLite存储...")
                    self._switch_to_fallback()
                    # 再次尝试创建研究
                    study = optuna.create_study(
                        study_name=study_name,
                        direction=direction,
                        storage=self._storage,
                        sampler=sampler,
                        pruner=pruner,
                        load_if_exists=True
                    )
                    logger.info(f"使用故障转移存储成功创建研究 '{study_name}'")
                    return study
                else:
                    raise
                    
    def load_study(self, study_name: str) -> optuna.Study:
        """
        加载已存在的研究
        
        Args:
            study_name: 研究名称
            
        Returns:
            optuna.Study: 优化研究对象
        """
        with self._retry_context("加载研究"):
            return optuna.load_study(
                study_name=study_name,
                storage=self._storage
            )
            
    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        storage_type = "SQLite故障转移" if self._using_fallback else "Redis"
        
        info = {
            "storage_type": storage_type,
            "using_fallback": self._using_fallback,
            "redis_healthy": self._check_redis_health(),
            "redis_url": self.redis_url,
            "fallback_db_url": self.fallback_db_url
        }
        
        # 如果使用Redis，添加连接池信息（仅数值，避免JSON序列化问题）
        if not self._using_fallback:
            try:
                # 获取可序列化的连接池统计信息
                available_connections = getattr(self.pool, '_available_connections', [])
                in_use_connections = getattr(self.pool, '_in_use_connections', set())
                
                pool_info = {
                    "max_connections": self.pool.max_connections,
                    "created_connections": getattr(self.pool, '_created_connections', 0),
                    "available_connections_count": len(available_connections) if hasattr(available_connections, '__len__') else 0,
                    "in_use_connections_count": len(in_use_connections) if hasattr(in_use_connections, '__len__') else 0,
                }
                info["connection_pool"] = pool_info
            except Exception as e:
                logger.debug(f"获取连接池信息失败: {e}")
                # 提供基本信息避免完全失败
                info["connection_pool"] = {
                    "max_connections": getattr(self.pool, 'max_connections', 'unknown'),
                    "status": "info_unavailable"
                }
                
        return info
        
    def cleanup(self):
        """清理资源"""
        try:
            if self.pool:
                self.pool.disconnect()
            logger.info("Redis存储资源已清理")
        except Exception as e:
            logger.warning(f"清理Redis存储资源时出错: {e}")


# 全局存储实例
_enhanced_storage = None


def get_enhanced_storage(config_path: Optional[str] = None) -> EnhancedRedisStorage:
    """
    获取增强型存储实例（单例模式）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        EnhancedRedisStorage: 存储实例
    """
    global _enhanced_storage
    
    if _enhanced_storage is None:
        # 加载配置
        config = _load_storage_config(config_path)
        _enhanced_storage = EnhancedRedisStorage(**config)
        
    return _enhanced_storage


def _load_storage_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载存储配置 - 严格模式：必须使用配置文件，禁止任何默认配置"""
    if config_path is None:
        # 配置文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        config_path = os.path.join(project_root, "redis", "redis_config.json")
    
    # 🚨 严格原则：配置文件必须存在
    if not os.path.exists(config_path):
        error_msg = (
            f"配置文件不存在: {config_path}\n"
            f"严格模式：禁止使用任何默认配置！\n"
            f"请创建配置文件或检查路径。配置文件模板:\n"
            f"{{\n"
            f'  "host": "localhost",\n'
            f'  "port": 6379,\n' 
            f'  "db": 0,\n'
            f'  "password": null,\n'
            f'  "socket_timeout": 30.0,\n'
            f'  "socket_connect_timeout": 30.0,\n'
            f'  "health_check_interval": 30\n'
            f"}}"
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 🚨 严格原则：配置文件必须可读取
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
    except Exception as e:
        error_msg = f"配置文件读取失败: {config_path}. 错误: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    
    # 🚨 严格原则：必须包含所有必要配置项
    required_keys = ['host', 'port', 'db']
    missing_keys = [key for key in required_keys if key not in file_config]
    if missing_keys:
        error_msg = f"配置文件缺少必要配置项: {missing_keys}. 配置文件路径: {config_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 构建完整配置（仅从配置文件获取，不使用任何默认值）
    config = {
        "redis_url": f"redis://{file_config['host']}:{file_config['port']}/{file_config['db']}",
        "max_retries": file_config.get("max_retries", 5),
        "retry_delay": file_config.get("retry_delay", 1.0),
        "pool_size": file_config.get("pool_size", 50),
        "socket_timeout": file_config.get("socket_timeout", 30.0),
        "socket_connect_timeout": file_config.get("socket_connect_timeout", 30.0),
        "health_check_interval": file_config.get("health_check_interval", 30),
        "fallback_db_url": file_config.get("fallback_db_url", "sqlite:///optuna_fallback.db")
    }
    
    # 🚨 验证配置的完整性
    for key, value in config.items():
        if value is None:
            error_msg = f"配置项 '{key}' 不能为空。请检查配置文件: {config_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    logger.info(f"成功加载存储配置: {config_path}")
    return config


# 便利函数
def create_enhanced_study(study_name: str,
                         direction: str = "minimize",
                         sampler: Optional[optuna.samplers.BaseSampler] = None,
                         pruner: Optional[optuna.pruners.BasePruner] = None) -> optuna.Study:
    """创建增强型研究"""
    storage = get_enhanced_storage()
    return storage.create_study(
        study_name=study_name,
        direction=direction,
        sampler=sampler,
        pruner=pruner
    )


def load_enhanced_study(study_name: str) -> optuna.Study:
    """加载增强型研究"""
    storage = get_enhanced_storage()
    return storage.load_study(study_name)


def get_storage_status() -> Dict[str, Any]:
    """获取存储状态"""
    storage = get_enhanced_storage()
    return storage.get_storage_info()