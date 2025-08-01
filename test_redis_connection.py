#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Redis连接和Optuna存储测试脚本
"""

import time
import json
import redis
import optuna
from datetime import datetime


def test_basic_redis_connection():
    """测试基础Redis连接"""
    print("🔍 测试基础Redis连接...")

    try:
        # 尝试连接开发环境
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        client.ping()
        print("✅ 开发环境Redis连接成功 (端口6379)")
        return client, 6379
    except:
        try:
            # 尝试连接生产环境
            client = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
            client.ping()
            print("✅ 生产环境Redis连接成功 (端口6380)")
            return client, 6380
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            print("请确保Redis服务已启动:")
            print("  开发环境: ./start_redis.sh dev")
            print("  生产环境: ./start_redis.sh prod")
            return None, None


def test_redis_performance(client):
    """测试Redis性能"""
    print("\n🚀 测试Redis性能...")

    # 写入测试
    start_time = time.time()
    for i in range(1000):
        client.set(f"test_key_{i}", f"test_value_{i}")
    write_time = time.time() - start_time
    print(f"  写入1000个key: {write_time:.3f}s ({1000 / write_time:.0f} ops/s)")

    # 读取测试
    start_time = time.time()
    for i in range(1000):
        client.get(f"test_key_{i}")
    read_time = time.time() - start_time
    print(f"  读取1000个key: {read_time:.3f}s ({1000 / read_time:.0f} ops/s)")

    # 清理测试数据
    client.flushdb()
    print("  测试数据已清理")


def test_optuna_storage(port):
    """测试Optuna存储"""
    print(f"\n🎯 测试Optuna Redis存储 (端口{port})...")

    try:
        # 创建Redis存储
        storage_url = f"redis://localhost:{port}/0"
        storage = optuna.storages.RedisStorage(storage_url)
        print(f"✅ Redis存储创建成功: {storage_url}")

        # 创建研究
        study_name = f"test_study_{int(time.time())}"
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            direction='maximize',
            load_if_exists=True
        )
        print(f"✅ Optuna研究创建成功: {study_name}")

        # 运行简单优化
        def objective(trial):
            x = trial.suggest_float('x', -10, 10)
            y = trial.suggest_float('y', -10, 10)
            return -(x ** 2 + y ** 2)  # 最大化 -(x²+y²)

        print("🔄 运行测试优化 (10次试验)...")
        study.optimize(objective, n_trials=10)

        print(f"✅ 优化完成! 最佳值: {study.best_value:.6f}")
        print(f"  最佳参数: {study.best_params}")
        print(f"  试验次数: {len(study.trials)}")

        # 测试并发性能
        print("\n⚡ 测试并发性能 (25个jobs模拟)...")
        start_time = time.time()
        study.optimize(objective, n_trials=50, n_jobs=1)  # 串行作为基准
        serial_time = time.time() - start_time

        # 注意：在测试环境中我们使用较小的并发数
        start_time = time.time()
        study.optimize(objective, n_trials=50, n_jobs=4)  # 并行测试
        parallel_time = time.time() - start_time

        speedup = serial_time / parallel_time if parallel_time > 0 else 1
        print(f"  串行时间: {serial_time:.2f}s")
        print(f"  并行时间: {parallel_time:.2f}s")
        print(f"  加速比: {speedup:.2f}x")

    except Exception as e:
        print(f"❌ Optuna存储测试失败: {e}")
        return False

    return True


def test_memory_usage(client):
    """测试内存使用情况"""
    print("\n💾 检查Redis内存使用...")

    try:
        info = client.info('memory')
        used_memory = info.get('used_memory_human', 'N/A')
        max_memory = info.get('maxmemory_human', 'N/A')

        print(f"  已使用内存: {used_memory}")
        print(f"  最大内存限制: {max_memory}")

        # 获取键空间信息
        keyspace_info = client.info('keyspace')
        if keyspace_info:
            for db, stats in keyspace_info.items():
                print(f"  {db}: {stats}")
        else:
            print("  当前无数据存储")

    except Exception as e:
        print(f"⚠️  内存信息获取失败: {e}")


def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 Redis + Optuna 连接和性能测试")
    print("=" * 60)

    # 基础连接测试
    client, port = test_basic_redis_connection()
    if not client:
        return False

    # 性能测试
    test_redis_performance(client)

    # 内存使用测试
    test_memory_usage(client)

    # Optuna存储测试
    success = test_optuna_storage(port)

    print("\n" + "=" * 60)
    if success:
        print("🎉 所有测试通过! Redis + Optuna 配置正确")
        print("\n推荐配置:")
        print(f"  - Redis端口: {port}")
        print(f"  - 存储URL: redis://localhost:{port}/0")
        print("  - 适合高并发贝叶斯优化")
    else:
        print("❌ 测试失败，请检查配置")
        return False

    print("=" * 60)
    return True


if __name__ == "__main__":
    main()
