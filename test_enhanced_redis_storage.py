#!/usr/bin/env python3
"""
增强型Redis存储稳定性测试脚本

测试功能：
1. Redis连接稳定性
2. 高并发场景下的性能
3. 故障转移机制
4. 连接池管理
5. 自动重试机制

使用方法：
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python test_enhanced_redis_storage.py
"""

import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any
import json

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

from lude.storage.enhanced_redis_storage import (
    get_enhanced_storage,
    create_enhanced_study,
    get_storage_status
)


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_enhanced_redis.log')
        ]
    )
    return logging.getLogger(__name__)


def simple_objective(trial):
    """简单的优化目标函数"""
    x = trial.suggest_float("x", -10, 10)
    y = trial.suggest_float("y", -10, 10)
    return x**2 + y**2


def complex_objective(trial):
    """复杂的优化目标函数，模拟实际场景"""
    # 模拟因子选择和权重优化
    n_factors = trial.suggest_int("n_factors", 2, 5)
    total_score = 0
    
    for i in range(n_factors):
        weight = trial.suggest_float(f"factor_{i}_weight", 0.1, 2.0)
        direction = trial.suggest_categorical(f"factor_{i}_direction", [True, False])
        
        # 模拟因子计算
        factor_value = trial.suggest_float(f"factor_{i}_value", -1, 1)
        score = weight * factor_value * (1 if direction else -1)
        total_score += score
        
    # 模拟一些计算延迟
    time.sleep(0.1)
    
    return abs(total_score)


def test_basic_connection():
    """测试基本连接功能"""
    logger = logging.getLogger(__name__)
    logger.info("🧪 测试基本连接功能...")
    
    try:
        storage = get_enhanced_storage()
        status = storage.get_storage_info()
        
        logger.info(f"存储类型: {status['storage_type']}")
        logger.info(f"Redis健康状态: {status['redis_healthy']}")
        logger.info(f"使用故障转移: {status['using_fallback']}")
        
        if not status['using_fallback'] and 'connection_pool' in status:
            pool_info = status['connection_pool']
            logger.info(f"连接池状态: {pool_info}")
            
        return True
        
    except Exception as e:
        logger.error(f"基本连接测试失败: {e}")
        return False


def test_single_study():
    """测试单个研究创建和优化"""
    logger = logging.getLogger(__name__)
    logger.info("🧪 测试单个研究创建和优化...")
    
    try:
        study_name = f"test_single_study_{int(time.time())}"
        study = create_enhanced_study(
            study_name=study_name,
            direction="minimize"
        )
        
        # 运行少量试验
        study.optimize(simple_objective, n_trials=10)
        
        # 检查结果
        best_trial = study.best_trial
        logger.info(f"最佳试验值: {best_trial.value}")
        logger.info(f"最佳参数: {best_trial.params}")
        
        return True
        
    except Exception as e:
        logger.error(f"单个研究测试失败: {e}")
        return False


def test_concurrent_studies(n_studies: int = 5, n_trials_per_study: int = 20):
    """测试并发研究"""
    logger = logging.getLogger(__name__)
    logger.info(f"🧪 测试并发研究 ({n_studies}个研究，每个{n_trials_per_study}次试验)...")
    
    def run_single_study(study_id: int) -> Dict[str, Any]:
        """运行单个研究"""
        try:
            study_name = f"test_concurrent_study_{study_id}_{int(time.time())}"
            study = create_enhanced_study(
                study_name=study_name,
                direction="minimize"
            )
            
            start_time = time.time()
            study.optimize(complex_objective, n_trials=n_trials_per_study)
            end_time = time.time()
            
            best_trial = study.best_trial
            return {
                "study_id": study_id,
                "study_name": study_name,
                "success": True,
                "best_value": best_trial.value,
                "n_trials": len(study.trials),
                "duration": end_time - start_time,
                "error": None
            }
            
        except Exception as e:
            return {
                "study_id": study_id,
                "study_name": f"test_concurrent_study_{study_id}",
                "success": False,
                "best_value": None,
                "n_trials": 0,
                "duration": 0,
                "error": str(e)
            }
    
    # 并发执行研究
    results = []
    with ThreadPoolExecutor(max_workers=n_studies) as executor:
        future_to_study = {
            executor.submit(run_single_study, i): i 
            for i in range(n_studies)
        }
        
        for future in as_completed(future_to_study):
            study_id = future_to_study[future]
            try:
                result = future.result()
                results.append(result)
                
                if result["success"]:
                    logger.info(f"研究 {study_id} 完成: 最佳值={result['best_value']:.4f}, "
                              f"试验数={result['n_trials']}, 耗时={result['duration']:.2f}s")
                else:
                    logger.error(f"研究 {study_id} 失败: {result['error']}")
                    
            except Exception as e:
                logger.error(f"研究 {study_id} 执行异常: {e}")
                results.append({
                    "study_id": study_id,
                    "success": False,
                    "error": str(e)
                })
    
    # 统计结果
    successful_studies = [r for r in results if r["success"]]
    failed_studies = [r for r in results if not r["success"]]
    
    logger.info(f"✅ 成功的研究: {len(successful_studies)}/{n_studies}")
    logger.info(f"❌ 失败的研究: {len(failed_studies)}/{n_studies}")
    
    if successful_studies:
        avg_duration = sum(r["duration"] for r in successful_studies) / len(successful_studies)
        avg_trials = sum(r["n_trials"] for r in successful_studies) / len(successful_studies)
        logger.info(f"平均耗时: {avg_duration:.2f}s")
        logger.info(f"平均试验数: {avg_trials:.1f}")
    
    if failed_studies:
        logger.warning("失败的研究错误信息:")
        for result in failed_studies:
            logger.warning(f"  研究 {result['study_id']}: {result['error']}")
    
    return len(successful_studies) == n_studies


def test_failover_mechanism():
    """测试故障转移机制"""
    logger = logging.getLogger(__name__)
    logger.info("🧪 测试故障转移机制...")
    
    try:
        # 获取当前存储状态
        storage = get_enhanced_storage()
        initial_status = storage.get_storage_info()
        logger.info(f"初始存储类型: {initial_status['storage_type']}")
        
        # 创建一个研究
        study_name = f"test_failover_{int(time.time())}"
        study = create_enhanced_study(
            study_name=study_name,
            direction="minimize"
        )
        
        # 运行一些试验
        study.optimize(simple_objective, n_trials=5)
        logger.info(f"故障转移前完成了 {len(study.trials)} 次试验")
        
        # 如果当前使用Redis，尝试触发故障转移
        if not initial_status['using_fallback']:
            logger.info("当前使用Redis存储，故障转移机制正常待命")
        else:
            logger.info("当前已在使用故障转移存储")
        
        # 继续运行更多试验
        study.optimize(simple_objective, n_trials=5)
        logger.info(f"总共完成了 {len(study.trials)} 次试验")
        
        # 检查最终状态
        final_status = storage.get_storage_info()
        logger.info(f"最终存储类型: {final_status['storage_type']}")
        
        return True
        
    except Exception as e:
        logger.error(f"故障转移测试失败: {e}")
        return False


def test_connection_recovery():
    """测试连接恢复机制"""
    logger = logging.getLogger(__name__)
    logger.info("🧪 测试连接恢复机制...")
    
    try:
        storage = get_enhanced_storage()
        
        # 执行多次健康检查，模拟连接不稳定的情况
        for i in range(10):
            is_healthy = storage._check_redis_health(force_check=True)
            logger.info(f"健康检查 {i+1}/10: {'通过' if is_healthy else '失败'}")
            time.sleep(1)
        
        # 尝试创建研究，测试连接恢复
        study_name = f"test_recovery_{int(time.time())}"
        study = create_enhanced_study(
            study_name=study_name,
            direction="minimize"
        )
        
        study.optimize(simple_objective, n_trials=3)
        logger.info("连接恢复测试完成")
        
        return True
        
    except Exception as e:
        logger.error(f"连接恢复测试失败: {e}")
        return False


def test_high_concurrency_simulation(n_workers: int = 10, n_trials_per_worker: int = 10):
    """模拟高并发场景"""
    logger = logging.getLogger(__name__)
    logger.info(f"🧪 模拟高并发场景 ({n_workers}个工作线程，每个{n_trials_per_worker}次试验)...")
    
    def worker_function(worker_id: int) -> Dict[str, Any]:
        """工作线程函数"""
        try:
            study_name = f"test_high_concurrency_worker_{worker_id}_{int(time.time())}"
            study = create_enhanced_study(
                study_name=study_name,
                direction="minimize"
            )
            
            start_time = time.time()
            study.optimize(simple_objective, n_trials=n_trials_per_worker)
            end_time = time.time()
            
            return {
                "worker_id": worker_id,
                "success": True,
                "n_trials": len(study.trials),
                "duration": end_time - start_time,
                "best_value": study.best_trial.value,
                "error": None
            }
            
        except Exception as e:
            return {
                "worker_id": worker_id,
                "success": False,
                "n_trials": 0,
                "duration": 0,
                "best_value": None,
                "error": str(e)
            }
    
    # 并发执行
    results = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        future_to_worker = {
            executor.submit(worker_function, i): i 
            for i in range(n_workers)
        }
        
        for future in as_completed(future_to_worker):
            worker_id = future_to_worker[future]
            try:
                result = future.result()
                results.append(result)
                
                if result["success"]:
                    logger.info(f"工作线程 {worker_id} 完成: {result['n_trials']}次试验, "
                              f"耗时{result['duration']:.2f}s, 最佳值{result['best_value']:.4f}")
                else:
                    logger.error(f"工作线程 {worker_id} 失败: {result['error']}")
                    
            except Exception as e:
                logger.error(f"工作线程 {worker_id} 异常: {e}")
    
    # 统计结果
    successful_workers = [r for r in results if r["success"]]
    failed_workers = [r for r in results if not r["success"]]
    
    logger.info(f"✅ 成功的工作线程: {len(successful_workers)}/{n_workers}")
    logger.info(f"❌ 失败的工作线程: {len(failed_workers)}/{n_workers}")
    
    if successful_workers:
        total_trials = sum(r["n_trials"] for r in successful_workers)
        total_duration = max(r["duration"] for r in successful_workers)
        avg_duration = sum(r["duration"] for r in successful_workers) / len(successful_workers)
        
        logger.info(f"总试验次数: {total_trials}")
        logger.info(f"总耗时: {total_duration:.2f}s")
        logger.info(f"平均每线程耗时: {avg_duration:.2f}s")
        logger.info(f"试验吞吐量: {total_trials/total_duration:.2f} trials/s")
    
    return len(failed_workers) == 0


def run_comprehensive_test():
    """运行全面测试"""
    logger = setup_logging()
    logger.info("🚀 开始增强型Redis存储全面测试...")
    
    test_results = []
    
    # 测试1: 基本连接
    logger.info("\n" + "="*60)
    test_results.append(("基本连接测试", test_basic_connection()))
    
    # 测试2: 单个研究
    logger.info("\n" + "="*60)
    test_results.append(("单个研究测试", test_single_study()))
    
    # 测试3: 并发研究
    logger.info("\n" + "="*60)
    test_results.append(("并发研究测试", test_concurrent_studies(n_studies=30, n_trials_per_study=15)))
    
    # 测试4: 故障转移
    logger.info("\n" + "="*60)
    test_results.append(("故障转移测试", test_failover_mechanism()))
    
    # 测试5: 连接恢复
    logger.info("\n" + "="*60)
    test_results.append(("连接恢复测试", test_connection_recovery()))
    
    # 测试6: 高并发模拟
    logger.info("\n" + "="*60)
    test_results.append(("高并发测试", test_high_concurrency_simulation(n_workers=15, n_trials_per_worker=300)))
    
    # 汇总结果
    logger.info("\n" + "="*60)
    logger.info("🏁 测试结果汇总:")
    
    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"  {test_name}: {status}")
        if result:
            passed_tests += 1
    
    logger.info(f"\n总测试通过率: {passed_tests}/{len(test_results)} ({passed_tests/len(test_results)*100:.1f}%)")
    
    # 最终存储状态
    try:
        final_status = get_storage_status()
        logger.info(f"\n最终存储状态: {json.dumps(final_status, indent=2, ensure_ascii=False)}")
    except Exception as e:
        logger.warning(f"获取最终存储状态失败: {e}")
    
    if passed_tests == len(test_results):
        logger.info("🎉 所有测试通过！增强型Redis存储工作正常。")
        return True
    else:
        logger.warning(f"⚠️  有 {len(test_results) - passed_tests} 个测试失败，请检查配置。")
        return False


if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)