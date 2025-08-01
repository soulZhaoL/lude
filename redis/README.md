# Redis分布式存储部署指南

本目录包含了用于Optuna高并发贝叶斯优化的Redis分布式存储解决方案。

**📁 目录位置**: 项目根目录下的 `redis/` 文件夹  
**🎯 用途**: 为高并发贝叶斯优化提供Redis分布式存储支持  
**💡 优势**: 避免SQLite数据库锁定，支持真正的高并发优化

## 🚀 快速启动

### 方式1：开发环境（推荐新手）

```bash
# 启动开发版Redis（轻量级，1GB内存）
docker-compose up -d redis-dev

# 验证连接
docker exec optuna-redis-dev redis-cli ping
```

### 方式2：生产环境（推荐高并发）

```bash
# 启动生产版Redis（3GB内存，完整持久化）
docker-compose up -d redis-prod

# 验证连接
docker exec optuna-redis-prod redis-cli ping
```

### 方式3：完整监控（包含可视化面板）

```bash
# 启动Redis + 监控面板
docker-compose up -d redis-prod redis-insight

# 访问监控面板: http://localhost:8001
```

## 📊 配置对比

| 配置项   | 开发环境     | 生产环境        |
|-------|----------|-------------|
| 内存限制  | 1GB      | 3GB         |
| 端口    | 6379     | 6380        |
| 持久化   | RDB only | RDB + AOF   |
| 最大客户端 | 10,000   | 20,000      |
| 日志级别  | notice   | notice + 文件 |

## 🔧 自定义配置

### 修改内存限制

```bash
# 编辑配置文件
vim redis-prod.conf

# 修改内存设置
maxmemory 4gb  # 改为4GB
```

### 设置密码保护

```bash
# 编辑配置文件
vim redis-prod.conf

# 取消注释并设置密码
requirepass your_strong_password_here
```

### 更新项目配置

```bash
# 编辑项目Redis配置
vim redis_config.json

# 添加密码
{
  "host": "localhost",
  "port": 6380,
  "password": "your_strong_password_here",
  ...
}
```

## 🎯 性能优化建议

### 高并发场景 (25+ jobs)

```bash
# 使用生产配置
docker-compose up -d redis-prod

# 监控内存使用
docker exec optuna-redis-prod redis-cli info memory

# 监控连接数
docker exec optuna-redis-prod redis-cli info clients
```

### 内存不足时的处理

```bash
# 检查内存使用
docker exec optuna-redis-prod redis-cli info memory

# 手动清理过期数据
docker exec optuna-redis-prod redis-cli FLUSHDB

# 调整内存策略
docker exec optuna-redis-prod redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## 📈 监控和调试

### 实时监控Redis操作

```bash
# 监控所有命令
docker exec optuna-redis-prod redis-cli monitor

# 查看慢查询
docker exec optuna-redis-prod redis-cli slowlog get 10

# 查看连接信息
docker exec optuna-redis-prod redis-cli client list
```

### 优化性能指标

```bash
# 查看性能统计
docker exec optuna-redis-prod redis-cli info stats

# 查看延迟信息
docker exec optuna-redis-prod redis-cli latency latest
```

## 🔄 数据备份和恢复

### 手动备份

```bash
# 创建RDB快照
docker exec optuna-redis-prod redis-cli BGSAVE

# 复制备份文件
docker cp optuna-redis-prod:/data/optuna-dump.rdb ./backup/
```

### 数据恢复

```bash
# 停止Redis
docker-compose stop redis-prod

# 恢复备份文件
docker cp ./backup/optuna-dump.rdb optuna-redis-prod:/data/

# 重启Redis
docker-compose start redis-prod
```

## 🛠️ 故障排除

### 常见问题

**问题1：连接被拒绝**

```bash
# 检查Redis是否启动
docker ps | grep redis

# 检查端口是否开放
netstat -an | grep 6379

# 查看Redis日志
docker logs optuna-redis-prod
```

**问题2：内存不足**

```bash
# 检查内存使用
docker exec optuna-redis-prod redis-cli info memory

# 清理数据
docker exec optuna-redis-prod redis-cli FLUSHALL

# 重启容器
docker-compose restart redis-prod
```

**问题3：性能问题**

```bash
# 检查慢查询
docker exec optuna-redis-prod redis-cli slowlog get

# 优化配置
docker exec optuna-redis-prod redis-cli CONFIG SET timeout 600
```

## 🔍 与Optuna集成验证

### 测试Redis连接

```python
# 在Python中测试
import redis
import optuna

# 测试基础连接
client = redis.Redis(host='localhost', port=6379, db=0)
print(client.ping())  # 应该返回True

# 测试Optuna存储
storage = optuna.storages.RedisStorage('redis://localhost:6379/0')
study = optuna.create_study(storage=storage, study_name='test_study')
print("Redis存储创建成功！")
```

## 📝 维护建议

1. **定期监控内存使用**：确保不超过配置限制
2. **定期备份数据**：重要优化结果建议每日备份
3. **监控慢查询**：及时发现性能瓶颈
4. **更新镜像**：定期更新Redis镜像版本

## 🎉 成功部署验证

部署成功后，你应该能看到：

- Redis容器正常运行
- 端口可以正常连接
- Optuna能够成功创建存储
- 高并发优化时无数据库锁定错误

如有问题，请查看容器日志进行排查：

```bash
docker logs optuna-redis-prod -f
```