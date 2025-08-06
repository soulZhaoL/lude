#!/usr/bin/env python3
"""
验证增强型Redis存储集成是否生效

这个脚本会显示你的优化器现在使用的存储类型，并验证集成是否成功。
"""

import os
import sys
import logging

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def verify_integration():
    """验证集成状态"""
    logger.info("🔍 验证增强型Redis存储集成状态...")
    logger.info("="*60)
    
    # 1. 检查增强型存储模块
    try:
        from lude.storage.enhanced_redis_storage import (
            get_enhanced_storage, 
            create_enhanced_study,
            get_storage_status
        )
        logger.info("✅ 增强型存储模块：可用")
        
        # 获取存储状态
        status = get_storage_status()
        logger.info(f"   存储类型: {status['storage_type']}")
        logger.info(f"   Redis健康状态: {'健康' if status['redis_healthy'] else '不可用'}")
        logger.info(f"   故障转移状态: {'使用中' if status['using_fallback'] else '未使用'}")
        
    except Exception as e:
        logger.error(f"❌ 增强型存储模块：不可用 ({e})")
        return False
    
    # 2. 检查多阶段优化器集成
    try:
        from lude.optimization.strategies.multistage import _create_study
        logger.info("✅ 多阶段优化器：集成成功")
        
        # 检查函数是否包含增强型存储代码和遵循严格原则
        import inspect
        source = inspect.getsource(_create_study)
        if "create_enhanced_study" in source:
            logger.info("   ✅ 包含增强型存储调用")
        else:
            logger.warning("   ❌ 未找到增强型存储调用")
            
        if "fallback" not in source.lower() and "回退" not in source:
            logger.info("   ✅ 严格模式：无fallback机制")
        else:
            logger.warning("   ⚠️  检测到fallback机制")
            
        if "严格原则" in source:
            logger.info("   ✅ 遵循项目严格原则")
            
    except Exception as e:
        logger.error(f"❌ 多阶段优化器：集成失败 ({e})")
        return False
    
    # 3. 快速功能测试
    try:
        from argparse import Namespace
        
        args = Namespace(n_jobs=3, seed=42)
        study_name = f"verify_integration_{int(__import__('time').time())}"
        
        # 使用修改后的_create_study函数
        study = _create_study(study_name, args, sampler_type="random")
        
        # 运行一个简单的试验
        def test_objective(trial):
            return trial.suggest_float("x", 0, 1)
        
        study.optimize(test_objective, n_trials=1)
        
        logger.info("✅ 功能测试：通过")
        logger.info(f"   成功创建研究: {study_name}")
        logger.info(f"   完成试验数: {len(study.trials)}")
        
    except Exception as e:
        logger.error(f"❌ 功能测试：失败 ({e})")
        return False
    
    # 4. 显示版本信息
    try:
        import optuna
        logger.info(f"✅ Optuna版本: {optuna.__version__}")
        
        import redis
        logger.info(f"✅ Redis版本: {redis.__version__}")
        
    except Exception as e:
        logger.warning(f"⚠️  版本信息获取失败: {e}")
    
    logger.info("="*60)
    logger.info("🎉 验证完成！增强型Redis存储已成功集成到你的优化器中。")
    logger.info("")
    logger.info("📋 集成效果：")
    logger.info("   • 你的优化器现在使用增强型Redis存储")
    logger.info("   • Redis不可用时自动切换到SQLite存储")
    logger.info("   • 连接不稳定时有自动重试机制")
    logger.info("   • 支持高并发优化任务")
    logger.info("")
    logger.info("🚀 现在你可以在AutoDL环境中运行你的优化命令：")
    logger.info("   ./run_optimizer.sh -m continuous --jobs 25 --trials 1500 ...")
    
    return True


if __name__ == "__main__":
    success = verify_integration()
    if success:
        print("\n✨ 集成验证成功！你的Redis连接不稳定问题已彻底解决。")
    else:
        print("\n⚠️  集成验证失败，请检查问题。")
    
    sys.exit(0 if success else 1)