#!/usr/bin/env python3
"""
简化的存储测试脚本 - 专门测试故障转移机制

此脚本在本地开发环境中测试，Redis不可用时自动使用SQLite存储。
"""

import os
import sys
import logging
import tempfile

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

from lude.storage.enhanced_redis_storage import EnhancedRedisStorage


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def simple_objective(trial):
    """简单的优化目标函数"""
    x = trial.suggest_float("x", -10, 10)
    y = trial.suggest_float("y", -10, 10)
    return x**2 + y**2


def test_fallback_storage():
    """测试故障转移存储"""
    logger = setup_logging()
    logger.info("🧪 测试故障转移存储...")
    
    # 创建临时数据库文件
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # 创建增强型存储，使用临时数据库
        storage = EnhancedRedisStorage(
            redis_url="redis://localhost:6379/0",  # 这个会失败，触发故障转移
            fallback_db_url=f"sqlite:///{temp_db_path}"
        )
        
        # 检查存储状态
        status = storage.get_storage_info()
        logger.info(f"存储类型: {status['storage_type']}")
        logger.info(f"使用故障转移: {status['using_fallback']}")
        
        # 创建研究
        study_name = "test_fallback_study"
        study = storage.create_study(
            study_name=study_name,
            direction="minimize"
        )
        
        logger.info(f"成功创建研究: {study_name}")
        
        # 运行优化
        study.optimize(simple_objective, n_trials=5)
        
        # 检查结果
        logger.info(f"完成 {len(study.trials)} 次试验")
        logger.info(f"最佳值: {study.best_trial.value:.4f}")
        logger.info(f"最佳参数: {study.best_trial.params}")
        
        # 再次检查存储状态
        final_status = storage.get_storage_info()
        logger.info(f"最终存储状态: {final_status}")
        
        logger.info("✅ 故障转移存储测试成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 故障转移存储测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)
                logger.info(f"已清理临时数据库: {temp_db_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")


def test_multiple_studies():
    """测试多个研究"""
    logger = setup_logging()
    logger.info("🧪 测试多个研究...")
    
    # 创建临时数据库文件
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        storage = EnhancedRedisStorage(
            redis_url="redis://localhost:6379/0",
            fallback_db_url=f"sqlite:///{temp_db_path}"
        )
        
        # 创建多个研究
        studies = []
        for i in range(3):
            study_name = f"test_multi_study_{i}"
            study = storage.create_study(study_name=study_name, direction="minimize")
            study.optimize(simple_objective, n_trials=3)
            studies.append(study)
            logger.info(f"研究 {i}: {len(study.trials)} 次试验, 最佳值: {study.best_trial.value:.4f}")
        
        logger.info("✅ 多个研究测试成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 多个研究测试失败: {e}")
        return False
        
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)
        except Exception:
            pass


def main():
    """主函数"""
    logger = setup_logging()
    logger.info("🚀 开始增强型存储基础功能测试...")
    
    tests = [
        ("故障转移存储", test_fallback_storage),
        ("多个研究", test_multiple_studies),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"开始测试: {test_name}")
        
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} 测试通过")
        else:
            logger.error(f"❌ {test_name} 测试失败")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"测试结果: {passed}/{len(tests)} 通过 ({passed/len(tests)*100:.1f}%)")
    
    if passed == len(tests):
        logger.info("🎉 所有基础功能测试通过！")
        return True
    else:
        logger.warning("⚠️  部分测试失败，请检查问题。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)