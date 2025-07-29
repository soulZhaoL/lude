# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 首先,在做任何交互时,请使用中文沟通!!! 不要在Think时 使用英文.

# 每次都用审视的目光，仔细看我输入的潜在问题，你要指出我的问题，并给出明显在我思考框架之外的建议.如果你觉得我说的太离谱了，你就骂回来，帮我瞬间清醒

# 在代码实现时,禁止使用(尤其在except Exception)兜底/fallback策略去进行逻辑降级. 如果有异常应该直接抛出或者打印日志及时介入,而不是使用错误的或替代的方案

# 🚨 关键原则：问题根源分析和根本解决
# 当遇到错误时，必须：
# 1. 分析问题的根本原因，而不是症状
# 2. 解决根本原因，而不是用try-except掩盖问题  
# 3. 绝对禁止用替代方案、降级处理、容错机制来掩盖真正的bug
# 4. 宁可程序报错失败，也不要返回错误的结果
# 这是系统可靠性的基础！

# 🚨 重要：Python环境要求
# 当你需要执行python程序时, 必须使用conda下名称为"lude"的环境！
# 正确的命令格式：
# source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python [your_script.py]
# 
# 错误示例：直接使用 python [script.py] - 会导致NumPy兼容性错误和依赖包版本冲突
# 正确示例：source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python [script.py]
#
# 原因：
# 1. lude环境配置了正确的NumPy、pandas、pyarrow等包版本组合
# 2. 避免NumPy 2.x与pyarrow的兼容性问题
# 3. 确保所有依赖包版本一致，防止运行时错误
# 
# 如果不使用lude环境，你将看到如下错误：
# - "A module that was compiled using NumPy 1.x cannot be run in NumPy 2.1.3"
# - "AttributeError: _ARRAY_API not found"
# - 其他依赖包版本冲突错误


本文件为Claude Code (claude.ai/code) 在该代码仓库中工作时提供指导。

## 项目概述

这是一个可转债多因子优化系统，使用贝叶斯优化来寻找可转债选择策略的最优因子组合。系统以复合年增长率(CAGR)作为主要性能指标。

## 开发环境设置

### 安装
```bash
# 开发模式安装
pip install -e .

# 或使用安装脚本
chmod +x install_dev.sh
./install_dev.sh
```

### 测试
```bash
# 🚨 重要：所有测试命令都必须在lude环境中运行
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude

# 运行测试
pytest tests/

# 运行特定测试文件
pytest tests/test_cagr_calculator.py
pytest tests/test_performance_metrics.py

# 运行修复验证测试
python test_fix_validation.py
```

### 代码质量检查
```bash
# 🚨 重要：代码质量检查也必须在lude环境中运行
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude

# 代码规范检查 (来自pyproject.toml的dev依赖)
flake8 src/

# 类型检查
mypy src/
```

## 关键命令

### 运行优化
```bash
# 单次优化运行
./run_optimizer.sh -m single --trials 500

# 持续优化
./run_optimizer.sh -m continuous --trials 200

# 完整优化带特定参数
./run_optimizer.sh -m continuous --method tpe --strategy multistage \
  --start 20220729 --end 20240607 --min 100 --max 150 \
  --jobs 5 --trials 3000 --hold 15 --factors 3

# 获取帮助
./run_optimizer.sh --help
```

### 查看结果
```bash
# 查看最佳模型
./view_model.sh

# 列出所有模型
./view_model.sh --list

# 按索引查看特定模型
./view_model.sh --index 1

# 查看模型详情
./view_model.sh --detailed
```

## 架构

### 核心组件

1. **配置系统** (`src/lude/config/`)
   - `config_loader.py`: 加载YAML配置文件
   - `optimization_config.yaml`: 主要优化参数和阈值
   - `paths.py`: 集中路径管理

2. **优化引擎** (`src/lude/optimization/`)
   - `optimization_engine.py`: 主要优化协调器
   - `continuous_optimizer.py`: 持续优化逻辑
   - `domain_knowledge_optimizer.py`: 领域特定优化策略

3. **因子策略** (`src/lude/strategies/`)
   - `factor_strategies.py`: 因子选择和组合策略
   - `multistage_optimizer.py`: 多阶段优化实现

4. **数据处理** (`src/lude/data/`)
   - 可转债数据的Parquet文件
   - 按因子数量组织的因子性能结果 (fac4_1, fac5_1, etc.)

5. **工具集** (`src/lude/utils/`)
   - `cagr_utils.py`: CAGR计算工具
   - `performance_metrics.py`: 性能评估指标
   - `dingtalk/`: 结果钉钉通知系统
   - `logger.py`: 集中日志配置

### 关键数据结构

- **因子映射**: JSON文件映射英文因子名到中文名
- **优化结果**: 存储在`optimization_results/`中，使用joblib格式
- **性能数据**: Excel文件包含因子性能分析

### 优化策略

1. **领域知识**: 使用业务知识对因子进行分类和选择
2. **预筛选**: 在组合优化前评估单个因子
3. **多阶段**: 两阶段优化（广泛探索+精细优化）
4. **过滤**: 基于业务规则移除冗余因子

## 重要文件

- `pyproject.toml`: 项目配置及依赖
- `requirements.txt`: 生产环境特定包版本
- `factor_mapping.json`: 英中文因子名映射
- `optimization_results/best_record.json`: 最佳优化结果记录

## 开发注意事项

- 🚨 **最重要**：所有Python相关操作都必须在conda lude环境中执行
- 系统使用Optuna进行贝叶斯优化，采用TPE（Tree-structured Parzen Estimator）
- 数据以Parquet格式存储以提高处理效率
- 结果自动保存，高性能模型可触发钉钉通知
- 代码库支持优化任务的并行处理
- 所有因子组合在优化前都要经过业务规则验证

## 常见错误和解决方案

### NumPy兼容性错误
```
错误: "A module that was compiled using NumPy 1.x cannot be run in NumPy 2.1.3"
错误: "AttributeError: _ARRAY_API not found"
```
**解决方案**: 必须使用conda lude环境
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude
```

### 参数分布错误（已修复）
```
错误: "The value 5000 of parameter 'amount_val_0' isn't contained in the distribution FloatDistribution(high=1000.0, low=-1000.0)"
```
**修复状态**: ✅ 已通过动态分布调整解决（multistage_optimizer.py:464-479）

### 排除因子冗余条件问题（已修复）
```
问题: 生成重复的条件组合，如：
- amount (2个条件): 条件1: >= 10000.0, 条件2: >= 500.0 (两个都是>=)  
- bias_5 (2个条件): 条件1: >= 0.003, 条件2: >= -0.001 (两个都是>=)
```
**根本原因**: `filter_strategies.py`在生成双条件时没有确保操作符逻辑互补

**修复状态**: ✅ 已通过后处理逻辑解决（filter_strategies.py:398-451）
- 保持Optuna参数空间一致性
- 后处理检测并修正冗余操作符
- 自动转换为互补条件（一个>=一个<=）  
- 确保数值逻辑合理（下限值 <= 上限值）

**修复效果**: 现在生成合理的范围条件：
- amount: >= 1000 和 <= 20000
- bias_5: >= -0.005 和 <= -0.003

### 环境激活问题
如果conda activate失败，确保conda已正确初始化：
```bash
conda init bash  # 或者 conda init zsh
source ~/.bashrc  # 或者 source ~/.zshrc
```