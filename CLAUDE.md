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

# 🚨 绝对严格原则：禁止任何默认配置

# 代码实现中严禁使用任何形式的默认配置，必须：

# 1. 所有配置都必须来自独立的配置文件，禁止代码中硬编码默认值

# 2. 配置文件不存在时必须直接抛出异常，禁止使用fallback默认配置

# 3. 配置项缺失时必须直接报错，禁止使用.get(key, default_value)的默认值

# 4. 禁止使用 or 运算符设置默认值，如 config = param or "default"

# 5. 所有配置必须显式声明和验证，确保系统行为完全可预测

# 6. 违反此原则的代码必须立即修复，无论是新代码还是已有代码

# 这确保了系统配置的明确性和可维护性！

* [ ] 🚨 重要：Python环境要求

# 当你需要执行python程序时, 必须使用conda下名称为"lude"的环境！

# 正确的命令格式：

# source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python [your_script.py]

# 错误示例：直接使用 python [script.py] - 会导致NumPy兼容性错误和依赖包版本冲突

# 正确示例：source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python [script.py]

# 原因：

# 1. lude环境配置了正确的NumPy、pandas、pyarrow等包版本组合

# 2. 避免NumPy 2.x与pyarrow的兼容性问题

# 3. 确保所有依赖包版本一致，防止运行时错误

# 如果不使用lude环境，你将看到如下错误：

# - "A module that was compiled using NumPy 1.x cannot be run in NumPy 2.1.3"

# - "AttributeError: _ARRAY_API not found"

# - 其他依赖包版本冲突错误

# 🚨 重要：项目路径配置

# 项目已升级为更稳健的路径配置系统，支持多种路径发现方式：

# 1. 环境变量方式（推荐用于生产环境）：

# export LUDE_PROJECT_ROOT="/path/to/your/lude/project"

# 或使用提供的脚本：source set_env.sh

# 2. 自动发现方式（默认）：

# 系统会自动查找包含 pyproject.toml、setup.py 等标志文件的目录作为项目根目录

# 3. 路径验证：

# 可以通过以下代码验证路径配置是否正确：

# from lude.config.paths import get_path_info

# print(get_path_info())

本文件为Claude Code (claude.ai/code) 在该代码仓库中工作时提供指导。

## 项目概述

这是一个可转债多因子优化系统，使用贝叶斯优化（Optuna + TPE）来寻找可转债选择策略的最优因子组合。系统支持：

- 多种因子（价格、溢价率、市盈率等）的权重和排序方向优化
- 数据筛选条件优化（上市天数、赎回状态、剩余期限、价格区间等）
- 复合年增长率(CAGR)作为主要性能指标
- 分布式计算支持（Redis + SQLite双存储）

## 开发环境设置

### 安装

```bash
# 开发模式安装
pip install -e .

# 或使用安装脚本（推荐，会自动设置环境变量）
chmod +x install_dev.sh
./install_dev.sh
```

**注意**: 安装脚本 `install_dev.sh` 现在会自动调用 `set_env.sh` 来设置项目环境变量 `LUDE_PROJECT_ROOT`
，确保路径配置的稳健性。如果你手动安装项目，请记得运行 `source set_env.sh` 来设置环境变量。

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

### 项目原则
1. **禁止默认配置**: 所有配置必须来自配置文件，不允许硬编码默认值
2. **错误处理**: 分析根本原因，禁止用try-except掩盖bug
3. **路径配置**: 使用 `source set_env.sh` 设置LUDE_PROJECT_ROOT

## 核心架构

### 系统概述
可转债多因子优化系统，使用贝叶斯优化（Optuna + TPE）寻找最优因子组合。

### 关键组件
1. **CAGR计算器** (`src/lude/core/cagr_calculator.py`)
   - 止盈逻辑在284-310行


2. **优化引擎** (`src/lude/optimization/`)
   - `unified_optimizer.py`: 统一入口
   - `strategies/multistage.py`: 语义化多阶段优化
   - 6大投资策略，51个因子

3. **数据结构**
   - MultiIndex DataFrame: (trade_date, code)
   - Parquet格式存储: `cb_data.pq`
   - 因子评分模式: `rank(ascending) * weight`

## 常用命令

### 日常开发
```bash
# 安装
./install_dev.sh

# 运行测试
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && pytest tests/
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && pytest tests/test_cagr_calculator.py -v

# 代码质量
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && flake8 src/
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && mypy src/
```

### 运行优化

```bash
# 标准多阶段优化
./run_optimizer.sh -m continuous --method tpe --strategy multistage \
  --start 20220729 --end 20240607 --min 100 --max 150 \
  --jobs 5 --trials 3000 --hold 15

# 后台运行
./run_optimizer.sh -m continuous -b -l optimization.log

# 查看状态
./run_optimizer.sh --status
./run_optimizer.sh --stop
```

### 结果分析

```bash
# 查看最佳模型
./view_model.sh
./view_model.sh --list
./view_model.sh --index 1 --detailed

# 对比平台结果
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python compare_daily_details_with_platform.py
```

### Redis管理（并发>10时需要）

```bash
./redis/start_redis.sh dev    # 开发环境
./redis/start_redis.sh stop   # 停止
./redis/start_redis.sh status # 状态
```

## 配置文件

- `src/lude/config/optimization_config.yaml`: CAGR阈值（保存>0.40，通知>0.45）
- `src/lude/config/strategy_config.yaml`: 6大投资策略定义，整数权重[1,5]
- `factor_mapping.json`: 因子中英文映射

## 语义化多阶段优化

### 投资策略

- **value**: 价值投资（低溢价、高纯债价值）
- **growth**: 成长投资（强基本面、高市值）
- **momentum**: 动量交易（技术指标、趋势）
- **liquidity**: 流动性策略（高成交、大规模）
- **contrarian**: 逆向投资（被低估、安全边际）
- **balanced**: 均衡配置（多因子综合）

### 优化流程

1. **第一阶段（70%试验）**: 探索最佳策略组合
2. **第二阶段（30%试验）**: 精调优化，30%探索+70%指导

### 测试验证

```bash
# 语义化策略测试
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python test_semantic_multistage.py

# 综合集成测试
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python test_comprehensive_semantic_integration.py
```

## 调试命令

```bash
# 查看优化日志
tail -f logs/optimization.log

# 验证路径配置
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python -c "from lude.config.paths import get_path_info; print(get_path_info())"

# 分析因子分布
source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude && python -m lude.utils.factor_distribution_analyzer
```

## 已解决的问题

1. **NumPy兼容性**: 使用conda lude环境
2. **参数分布错误**: multistage_optimizer.py:464-479动态调整
3. **冗余过滤条件**: filter_strategies.py:398-451后处理修正

## 性能监控

- CAGR > 0.45: 自动钉钉通知
- CAGR > 0.40: 自动保存模型
- 结果目录: `optimization_results/`
- 最佳记录: `optimization_results/best_record.json`
