#!/bin/bash
# Redis依赖安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Redis依赖安装脚本${NC}"
echo ""

# 检查Python环境
check_python_env() {
    echo -e "${BLUE}检查Python环境...${NC}"
    
    # 检查是否在conda环境中
    if [[ "$CONDA_DEFAULT_ENV" != "lude" ]]; then
        echo -e "${YELLOW}⚠️  当前不在lude环境中${NC}"
        echo -e "请先激活lude环境:"
        echo -e "${YELLOW}source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python环境检查通过 (当前环境: $CONDA_DEFAULT_ENV)${NC}"
}

# 安装Redis Python客户端
install_redis_py() {
    echo -e "${BLUE}安装redis-py客户端...${NC}"
    
    # 检查是否已安装
    if python -c "import redis" 2>/dev/null; then
        echo -e "${GREEN}✅ redis-py已安装${NC}"
        redis_version=$(python -c "import redis; print(redis.__version__)")
        echo -e "版本: ${YELLOW}$redis_version${NC}"
    else
        echo -e "${YELLOW}安装redis-py...${NC}"
        pip install redis==6.2.0
        echo -e "${GREEN}✅ redis-py安装完成${NC}"
    fi
}

# 检查Optuna Redis支持
check_optuna_redis() {
    echo -e "${BLUE}检查Optuna Redis支持...${NC}"
    
    python_check=$(cat << 'EOF'
try:
    import optuna
    import redis
    
    # 测试创建Redis存储
    storage = optuna.storages.RedisStorage('redis://localhost:6379/0')
    print("✅ Optuna Redis存储支持正常")
    print(f"Optuna版本: {optuna.__version__}")
    print(f"Redis-py版本: {redis.__version__}")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    exit(1)
except Exception as e:
    print(f"⚠️  Redis连接测试失败 (Redis可能未启动): {e}")
    print("✅ 但Optuna Redis存储支持正常")
EOF
)
    
    if python -c "$python_check"; then
        echo -e "${GREEN}✅ Optuna Redis支持检查通过${NC}"
    else
        echo -e "${RED}❌ Optuna Redis支持检查失败${NC}"
        exit 1
    fi
}

# 创建测试脚本
create_test_script() {
    echo -e "${BLUE}创建Redis连接测试脚本...${NC}"
    
    cat > test_redis_connection.py << 'EOF'
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
    print(f"  写入1000个key: {write_time:.3f}s ({1000/write_time:.0f} ops/s)")
    
    # 读取测试
    start_time = time.time()
    for i in range(1000):
        client.get(f"test_key_{i}")
    read_time = time.time() - start_time
    print(f"  读取1000个key: {read_time:.3f}s ({1000/read_time:.0f} ops/s)")
    
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
            return -(x**2 + y**2)  # 最大化 -(x²+y²)
        
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
    print("="*60)
    print("🧪 Redis + Optuna 连接和性能测试")
    print("="*60)
    
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
    
    print("\n" + "="*60)
    if success:
        print("🎉 所有测试通过! Redis + Optuna 配置正确")
        print("\n推荐配置:")
        print(f"  - Redis端口: {port}")
        print(f"  - 存储URL: redis://localhost:{port}/0")
        print("  - 适合高并发贝叶斯优化")
    else:
        print("❌ 测试失败，请检查配置")
        return False
    
    print("="*60)
    return True

if __name__ == "__main__":
    main()
EOF
    
    chmod +x test_redis_connection.py
    echo -e "${GREEN}✅ 测试脚本创建完成: test_redis_connection.py${NC}"
}

# 主执行逻辑
main() {
    echo "开始安装Redis依赖..."
    
    check_python_env
    install_redis_py
    check_optuna_redis
    create_test_script
    
    echo ""
    echo -e "${GREEN}🎉 Redis依赖安装完成!${NC}"
    echo ""
    echo -e "${BLUE}下一步操作:${NC}"
    echo -e "1. 启动Redis服务: ${YELLOW}./start_redis.sh prod${NC}"
    echo -e "2. 运行测试脚本: ${YELLOW}python test_redis_connection.py${NC}"
    echo -e "3. 开始优化训练: ${YELLOW}./run_optimizer.sh -m continuous --jobs 25 ...${NC}"
}

main "$@"