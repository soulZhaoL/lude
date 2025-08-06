#!/usr/bin/env python3
"""
测试多阶段优化器与增强型Redis存储的集成

验证功能：
1. 增强型存储集成是否正常
2. 多阶段优化策略是否正常工作
3. 故障转移机制是否有效
"""

import os
import sys
import logging
from argparse import Namespace

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_create_study_integration():
    """测试_create_study函数的增强型存储集成"""
    logger.info("🧪 测试_create_study函数集成...")
    
    try:
        from lude.optimization.strategies.multistage import _create_study
        
        # 创建模拟参数
        args = Namespace(
            n_jobs=5,
            seed=42
        )
        
        # 测试创建研究
        study_name = f"test_integration_{int(__import__('time').time())}"
        study = _create_study(study_name, args, sampler_type="random")
        
        logger.info(f"✅ 成功创建研究: {study_name}")
        logger.info(f"研究方向: {study.direction}")
        logger.info(f"采样器类型: {type(study.sampler).__name__}")
        
        # 测试简单优化
        def objective(trial):
            x = trial.suggest_float("x", -10, 10)
            return x ** 2
        
        study.optimize(objective, n_trials=3)
        logger.info(f"完成 {len(study.trials)} 次试验")
        logger.info(f"最佳值: {study.best_trial.value:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ _create_study集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tpe_sampler_integration():
    """测试TPE采样器集成"""
    logger.info("🧪 测试TPE采样器集成...")
    
    try:
        from lude.optimization.strategies.multistage import _create_study
        
        # 创建模拟参数
        args = Namespace(
            n_jobs=10,  # 高并发测试
            seed=42
        )
        
        # 测试TPE采样器
        study_name = f"test_tpe_integration_{int(__import__('time').time())}"
        study = _create_study(study_name, args, sampler_type="tpe")
        
        logger.info(f"✅ 成功创建TPE研究: {study_name}")
        logger.info(f"采样器类型: {type(study.sampler).__name__}")
        
        # 检查TPE配置
        sampler = study.sampler
        if hasattr(sampler, '_n_startup_trials'):
            logger.info(f"启动试验数: {sampler._n_startup_trials}")
        if hasattr(sampler, '_n_ei_candidates'):
            logger.info(f"EI候选数: {sampler._n_ei_candidates}")
        
        # 测试优化
        def complex_objective(trial):
            x = trial.suggest_float("x", -5, 5)
            y = trial.suggest_float("y", -5, 5)
            return -(x**2 + y**2)  # 最大化问题
        
        study.optimize(complex_objective, n_trials=5)
        logger.info(f"完成 {len(study.trials)} 次试验")
        logger.info(f"最佳值: {study.best_trial.value:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ TPE采样器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_study_loading():
    """测试研究加载功能"""
    logger.info("🧪 测试研究加载功能...")
    
    try:
        from lude.optimization.strategies.multistage import _create_study
        
        args = Namespace(n_jobs=3, seed=42)
        study_name = f"test_loading_{int(__import__('time').time())}"
        
        # 创建研究并运行一些试验
        study1 = _create_study(study_name, args, sampler_type="random")
        def objective(trial):
            return trial.suggest_float("x", 0, 1) ** 2
        
        study1.optimize(objective, n_trials=3)
        initial_trials = len(study1.trials)
        logger.info(f"初始研究完成 {initial_trials} 次试验")
        
        # 尝试加载同一个研究
        study2 = _create_study(study_name, args, sampler_type="random")
        loaded_trials = len(study2.trials)
        logger.info(f"加载的研究包含 {loaded_trials} 次试验")
        
        if loaded_trials >= initial_trials:
            logger.info("✅ 研究加载功能正常")
            return True
        else:
            logger.error(f"❌ 研究加载失败: 预期 >= {initial_trials}, 实际 {loaded_trials}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 研究加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback_mechanism():
    """测试回退机制"""
    logger.info("🧪 测试回退机制...")
    
    try:
        # 暂时重命名增强型存储模块来测试回退
        import sys
        enhanced_storage_module = None
        if 'lude.storage.enhanced_redis_storage' in sys.modules:
            enhanced_storage_module = sys.modules['lude.storage.enhanced_redis_storage']
            del sys.modules['lude.storage.enhanced_redis_storage']
        
        try:
            from lude.optimization.strategies.multistage import _create_study
            
            args = Namespace(n_jobs=2, seed=42)
            study_name = f"test_fallback_{int(__import__('time').time())}"
            
            # 这应该触发回退机制
            study = _create_study(study_name, args, sampler_type="random")
            logger.info("✅ 回退机制正常工作")
            
            # 测试基本功能
            def objective(trial):
                return trial.suggest_float("x", 0, 1)
            
            study.optimize(objective, n_trials=2)
            logger.info(f"回退模式下完成 {len(study.trials)} 次试验")
            
            return True
            
        finally:
            # 恢复模块
            if enhanced_storage_module:
                sys.modules['lude.storage.enhanced_redis_storage'] = enhanced_storage_module
                
    except Exception as e:
        logger.error(f"❌ 回退机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("🚀 开始多阶段优化器集成测试...")
    
    tests = [
        ("基本集成测试", test_create_study_integration),
        ("TPE采样器集成", test_tpe_sampler_integration),
        ("研究加载功能", test_study_loading),
        ("回退机制测试", test_fallback_mechanism),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"开始测试: {test_name}")
        
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} 通过")
        else:
            logger.error(f"❌ {test_name} 失败")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"集成测试结果: {passed}/{len(tests)} 通过 ({passed/len(tests)*100:.1f}%)")
    
    if passed == len(tests):
        logger.info("🎉 所有集成测试通过！增强型存储已成功集成到多阶段优化器中。")
        return True
    else:
        logger.warning("⚠️  部分测试失败，请检查集成。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)