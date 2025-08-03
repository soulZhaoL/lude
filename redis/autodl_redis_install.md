# AutoDL 平台 Redis 安装指南

本文档专门针对 AutoDL 平台的容器环境，提供直接安装 Redis 服务器的解决方案。

## 环境说明

- **平台**: AutoDL (autodl-container)
- **系统**: Ubuntu 22.04 (容器环境)
- **限制**: 无 systemd，无法运行 Docker-in-Docker
- **解决方案**: 直接安装 Redis 服务器

## 为什么不用 Docker？

在 AutoDL 容器环境中，尝试运行 Docker 会遇到以下问题：

```bash
# 典型错误
ERRO[...] failed to mount overlay: operation not permitted  storage-driver=overlay2
ERRO[...] exec: "fuse-overlayfs": executable file not found in $PATH
System has not been booted with systemd as init system (PID 1). Can't operate.
```

**根本原因**: 容器内无法挂载文件系统和运行特权操作。

## 安装步骤

### 1. 检查环境

```bash
# 确认在 AutoDL 环境
hostname
# 应显示类似: autodl-container-xxxxxxxxx

# 检查系统资源
free -h
df -h
```

### 2. 停止可能存在的 Docker 进程

```bash
# 如果之前尝试启动过 dockerd
sudo pkill dockerd
sudo pkill docker

# 清理进程
ps aux | grep docker
```

### 3. 安装 Redis 服务器

```bash
# 更新包列表
sudo apt update

# 安装 Redis 服务器和工具
sudo apt install -y redis-server redis-tools

# 验证安装
redis-server --version
redis-cli --version
```

### 4. 配置 Redis 服务

#### 备份原配置

```bash
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
```

#### 应用生产配置

```bash
# 使用项目中的生产配置
sudo cp /path/to/your/lude/redis/redis-prod.conf /etc/redis/redis.conf

# 或者手动编辑关键配置
sudo nano /etc/redis/redis.conf
```

#### 关键配置项

确保以下配置适合 AutoDL 环境：

```conf
# 网络配置 - 允许多环境访问
bind 0.0.0.0
port 6379
timeout 300

# 内存配置 - 根据 AutoDL 实例调整
maxmemory 3gb
maxmemory-policy allkeys-lru

# 连接配置 - 支持高并发
maxclients 20000
tcp-backlog 2048

# 持久化配置
appendonly yes
appendfilename "optuna-appendonly.aof"
appendfsync everysec

# 快照配置
save 1800 1
save 300 100
save 60 10000

# 日志配置
loglevel notice
logfile /var/log/redis/redis-server.log

# 性能优化
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
```

### 5. 创建日志目录

```bash
# 创建日志目录
sudo mkdir -p /var/log/redis
sudo chown redis:redis /var/log/redis
sudo chmod 755 /var/log/redis
```

### 6. 启动 Redis 服务

#### 方案A：标准服务启动（可能失败）

```bash
# 尝试标准服务启动
sudo service redis-server start

# 检查服务状态
sudo service redis-server status
```

#### 方案B：直接启动Redis（✅ 已验证成功，推荐用于AutoDL）

```bash
# 1. 创建必要目录和权限
sudo mkdir -p /var/log/redis /var/lib/redis /run/redis
sudo chown -R redis:redis /var/log/redis/ 2>/dev/null || sudo chown -R root:root /var/log/redis/
sudo chown -R redis:redis /var/lib/redis/ 2>/dev/null || sudo chown -R root:root /var/lib/redis/

# 2. 直接启动Redis（使用配置文件）
sudo redis-server /etc/redis/redis.conf --daemonize yes

# 3. 验证启动
redis-cli ping
# 应返回: PONG

ps aux | grep redis-server
# 应显示redis-server进程正在运行
```

**✅ 实践验证**: 此方案在AutoDL容器环境中已成功验证！

#### 方案C：最简启动（万能方案）

```bash
# 如果配置文件有问题，使用命令行参数直接启动
redis-server --port 6379 \
  --maxmemory 3gb \
  --maxmemory-policy allkeys-lru \
  --appendonly yes \
  --daemonize yes \
  --bind 0.0.0.0 \
  --maxclients 10000 \
  --dir /tmp/ \
  --dbfilename dump.rdb \
  --appendfilename appendonly.aof

# 验证
redis-cli ping
```

#### 方案D：简化配置文件启动

```bash
# 创建简化配置
cat > /tmp/redis-simple.conf << 'EOF'
bind 0.0.0.0
port 6379
maxmemory 3gb
maxmemory-policy allkeys-lru
maxclients 10000
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
save 900 1
save 300 10
save 60 10000
loglevel notice
dir /tmp/
daemonize yes
pidfile /tmp/redis.pid
EOF

# 使用简化配置启动
sudo redis-server /tmp/redis-simple.conf

# 验证
redis-cli ping
```

**🎯 推荐流程**：
1. **方案A失败是正常的**（显示"Starting redis-server: failed"）
2. **直接使用方案B**（✅ 已验证成功）
3. 如果方案B仍有问题，再尝试方案C或D

### 7. 验证安装

```bash
# 测试基本连接
redis-cli ping
# 应返回: PONG

# 测试写入读取
redis-cli set test_key "Hello AutoDL"
redis-cli get test_key
# 应返回: "Hello AutoDL"

# 清理测试数据
redis-cli del test_key

# 查看 Redis 信息
redis-cli info memory
redis-cli info clients
```

## 项目配置调整

### 更新 redis_config.json

```json
{
  "host": "localhost",
  "port": 6379,
  "db": 0,
  "password": null,
  "socket_connect_timeout": 30,
  "socket_timeout": 30,
  "retry_on_timeout": true,
  "health_check_interval": 30,
  "maxmemory": "3gb",
  "maxmemory_policy": "allkeys-lru",
  "description": "AutoDL环境直接Redis连接配置"
}
```

### 测试项目连接

```bash
# 进入项目目录
cd /path/to/your/lude/project

# 激活conda环境
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude

# 测试Redis连接
python test_redis_connection.py
```

## 多环境部署方案

### 目录结构

```
/opt/lude/
├── redis-shared/              # 共享Redis服务（已安装）
└── environments/
    ├── env01/
    ├── env02/
    ├── ...
    └── env20/
```

### 共享Redis配置

所有环境共享同一个Redis实例：

- **主机**: localhost
- **端口**: 6379
- **数据库**: 使用不同的study名称进行隔离
- **连接池**: 自动管理，支持20000并发连接

### 环境隔离策略

```python
# 每个环境使用唯一的study名称
study_name = f"optuna_study_env{env_id}_{strategy}_{timestamp}"

# 示例：
# env01: optuna_study_env01_multistage_20250803
# env02: optuna_study_env02_multistage_20250803
```

## 服务管理

### 常用命令

```bash
# 启动服务
sudo service redis-server start

# 停止服务
sudo service redis-server stop

# 重启服务
sudo service redis-server restart

# 查看状态
sudo service redis-server status

# 查看进程
ps aux | grep redis-server
```

### 日志查看

```bash
# 查看服务日志
sudo tail -f /var/log/redis/redis-server.log

# 查看系统日志
sudo journalctl -u redis-server -f

# 查看错误日志
sudo grep -i error /var/log/redis/redis-server.log
```

### 性能监控

```bash
# 连接信息
redis-cli info clients

# 内存使用
redis-cli info memory

# 键空间信息
redis-cli info keyspace

# 实时监控
redis-cli monitor
```

## 故障排除

### 常见问题

#### 1. 服务无法启动

```bash
# 检查配置文件语法
redis-server /etc/redis/redis.conf --test-config

# 查看详细错误
sudo service redis-server start
sudo journalctl -u redis-server --no-pager
```

#### 2. 连接被拒绝

```bash
# 检查端口监听
sudo netstat -tlnp | grep 6379

# 检查防火墙（如果有）
sudo ufw status

# 测试本地连接
telnet localhost 6379
```

#### 3. 内存不足

```bash
# 检查内存使用
redis-cli info memory | grep used_memory_human

# 调整最大内存限制
redis-cli config set maxmemory 2gb
```

#### 4. 权限问题

```bash
# 检查Redis用户权限
sudo ls -la /var/log/redis/
sudo ls -la /var/lib/redis/

# 修复权限
sudo chown -R redis:redis /var/log/redis/
sudo chown -R redis:redis /var/lib/redis/
```

## 性能优化

### AutoDL环境特定优化

```conf
# 针对容器环境的优化配置
tcp-keepalive 300
tcp-backlog 2048

# 内存优化
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
set-max-intset-entries 512

# IO优化
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

### 监控脚本

```bash
#!/bin/bash
# redis_monitor.sh - Redis监控脚本

echo "=== Redis服务状态 ==="
sudo service redis-server status

echo -e "\n=== 内存使用情况 ==="
redis-cli info memory | grep -E "(used_memory_human|maxmemory_human)"

echo -e "\n=== 客户端连接数 ==="
redis-cli info clients | grep connected_clients

echo -e "\n=== 键空间信息 ==="
redis-cli info keyspace

echo -e "\n=== 系统资源 ==="
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')"
echo "内存: $(free -h | grep Mem | awk '{print $3"/"$2}')"
```

## 备份和恢复

### 数据备份

```bash
# 创建备份目录
sudo mkdir -p /opt/lude/redis-backup

# 手动备份
sudo cp /var/lib/redis/dump.rdb /opt/lude/redis-backup/dump_$(date +%Y%m%d_%H%M%S).rdb

# 备份AOF文件
sudo cp /var/lib/redis/appendonly.aof /opt/lude/redis-backup/appendonly_$(date +%Y%m%d_%H%M%S).aof
```

### 自动备份脚本

```bash
#!/bin/bash
# backup_redis.sh - 自动备份脚本

BACKUP_DIR="/opt/lude/redis-backup"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
sudo redis-cli BGSAVE
sleep 10  # 等待备份完成

# 复制文件
sudo cp /var/lib/redis/dump.rdb $BACKUP_DIR/dump_$DATE.rdb
sudo cp /var/lib/redis/appendonly.aof $BACKUP_DIR/appendonly_$DATE.aof

# 压缩备份
tar -czf $BACKUP_DIR/redis_backup_$DATE.tar.gz -C $BACKUP_DIR dump_$DATE.rdb appendonly_$DATE.aof

# 清理临时文件
rm $BACKUP_DIR/dump_$DATE.rdb $BACKUP_DIR/appendonly_$DATE.aof

echo "备份完成: $BACKUP_DIR/redis_backup_$DATE.tar.gz"
```

## 总结

在 AutoDL 环境中：

✅ **推荐**: 直接安装 Redis 服务器（✅ 已验证方案B成功）  
❌ **不推荐**: 使用 Docker 方案  

### 🎯 验证成功的部署流程
1. **安装Redis**: `sudo apt install -y redis-server redis-tools`
2. **方案B启动**: `sudo redis-server /etc/redis/redis.conf --daemonize yes`
3. **验证成功**: `redis-cli ping` 返回 `PONG`

### 优势

- 🚀 **性能更好**: 无容器开销
- 🛡️ **更稳定**: 避免权限和文件系统问题
- 🔧 **更简单**: 标准服务管理
- 💰 **资源节省**: 降低内存和CPU消耗
- ✅ **实践验证**: 在AutoDL环境中已成功部署

### 注意事项

- 确保 Redis 配置适合你的 AutoDL 实例规格
- 定期监控内存使用情况
- 在重要实验前进行数据备份
- 多环境通过study名称进行数据隔离

---

**部署完成后，你就可以在 15-20 个 conda 环境中同时运行优化任务，所有环境共享同一个高性能 Redis 实例！**
