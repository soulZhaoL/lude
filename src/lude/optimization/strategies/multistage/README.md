# 多阶段语义化优化策略架构文档

## 📋 概述

多阶段语义化优化策略是一个创新的可转债因子优化系统，将传统的无意义索引选择转换为有业务含义的投资策略选择。该系统解决了Optuna动态参数空间问题，同时提供了更好的可解释性。

## 🏗️ 架构设计

### 核心特性

1. **语义化策略驱动**：从6大投资策略（价值、成长、动量、流动性、逆向、平衡）中选择
2. **固定参数空间**：196个预定义参数，彻底解决Optuna动态空间问题
3. **两阶段优化**：70%探索 + 30%精调的平衡策略
4. **智能因子选择**：基于投资策略的因子组合，而非随机选择

### 文件结构

```
multistage/
├── __init__.py              # 模块导出定义
├── config.py                # 策略配置管理器
├── coordinator.py           # 多阶段优化主协调器
├── semantic_objective_v1.py # 动态参数版本（已弃用）
├── semantic_objective_v2.py # 固定参数版本（推荐）
└── README.md               # 本文档
```

## 📊 技术实现

### 1. 固定参数空间设计（v2版本）

```python
# 参数构成：196个固定参数
基础参数(4个):
- primary_strategy      # 主策略选择
- use_mixed_strategy   # 是否混合策略
- secondary_strategy   # 次要策略
- enable_auxiliary     # 是否启用辅助因子

因子参数(192个 = 48因子 × 4参数):
- weight_{factor}              # 权重 [1-5]
- ascending_{factor}           # 排序方向
- enable_secondary_{factor}   # 次策略启用开关
- enable_aux_{factor}         # 辅助因子启用开关
```

### 2. 两阶段优化流程

#### 第一阶段：语义化策略探索（70%试验）
```python
目标：发现最佳投资策略组合
- 完全探索所有策略组合
- 识别有效的因子组合模式
- 收集策略性能统计信息
```

#### 第二阶段：平衡精调（30%试验）
```python
目标：在探索与指导间取得平衡
- 70%指导模式：基于第一阶段发现优化
- 30%探索模式：保持创新能力
- 软约束而非硬性限制
```

### 3. 策略配置体系

从`strategy_config.yaml`加载的配置包括：

```yaml
investment_strategies:
  value:                    # 价值投资策略
    core_factors: [...]     # 核心因子
    weight_range: [1, 5]    # 权重范围
    preferred_directions:   # 偏好方向
  growth: ...              # 成长策略
  momentum: ...            # 动量策略
  liquidity: ...           # 流动性策略
  contrarian: ...          # 逆向策略
  balanced: ...            # 平衡策略

strategy_combination_rules:
  allowed_combinations: [...] # 允许的策略组合
  discouraged_combinations: [...] # 不建议的组合
  min_core_factors: 6        # 最少核心因子数
  max_mixed_factors: 12      # 最多混合因子数
```

## 🔧 核心组件详解

### StrategyConfig 类（config.py）

```python
class StrategyConfig:
    """策略配置管理器"""
    
    def __init__(self, config_path=None)
        # 加载策略配置文件
        
    def get_strategy(strategy_name) -> Dict
        # 获取特定策略配置
        
    def is_valid_combination(primary, secondary) -> bool
        # 验证策略组合有效性
        
    def check_factor_conflicts(rank_factors) -> bool
        # 检查因子冲突
```

### 目标函数（semantic_objective_v2.py）

#### create_fixed_semantic_objective_function
```python
功能：创建第一阶段探索目标函数
特点：
- 196个固定参数
- 语义化策略选择
- 业务规则验证
- 因子冲突检测
```

#### create_fixed_refined_objective_function
```python
功能：创建第二阶段精调目标函数
特点：
- 探索vs指导模式（30%/70%）
- 策略偏好分析
- 权重软指导
- 方向偏好学习
```

#### analyze_best_strategies
```python
功能：分析优化结果
输出：
- 最佳策略组合
- 因子权重分布
- 性能指标统计
```

## 💡 关键创新点

### 1. 解决Optuna动态参数问题

**问题**：Optuna不支持试验间的动态参数空间变化
**解决**：预定义所有48个因子的所有参数，通过enable开关控制使用

### 2. 语义化提升可解释性

**传统方式**：因子索引选择，无业务含义
**新方式**：投资策略驱动，符合业务逻辑

### 3. 平衡探索与利用

**第一阶段**：广泛探索，发现模式
**第二阶段**：30%探索 + 70%指导，平衡创新与优化

## 📈 使用指南

### 基础使用

```python
from lude.optimization.strategies.multistage import (
    StrategyConfig,
    create_fixed_semantic_objective_function,
    create_fixed_refined_objective_function,
    analyze_best_strategies
)

# 1. 初始化配置
config = StrategyConfig()

# 2. 创建第一阶段目标函数
objective1 = create_fixed_semantic_objective_function(df, args, config)

# 3. 运行第一阶段优化
study1 = optuna.create_study(direction='maximize')
study1.optimize(objective1, n_trials=700)

# 4. 分析第一阶段结果
best_strategies = analyze_best_strategies(study1, top_n=10)

# 5. 创建第二阶段目标函数
objective2 = create_fixed_refined_objective_function(
    df, best_strategies, args, config
)

# 6. 运行第二阶段优化
study2 = optuna.create_study(direction='maximize')
study2.optimize(objective2, n_trials=300)
```

### 集成到主优化流程

```python
from lude.optimization.strategies.multistage import run_semantic_multistage_optimization

# 在multistage.py中调用
best_value, best_params = run_semantic_multistage_optimization(
    df=data,
    args=args,
    strategy_config=config
)
```

## 🧪 测试覆盖

### 测试文件：test_semantic_objective_v2.py

1. **固定参数空间验证**
   - 确认196个参数完全固定
   - 验证参数名称和类型

2. **精调指导模式测试**
   - 验证30%/70%探索指导比例
   - 测试策略偏好学习

3. **权重方向指导测试**
   - 验证权重软约束机制
   - 测试方向偏好传递

4. **因子选择逻辑测试**
   - 验证策略驱动的因子选择
   - 测试因子数量约束

5. **策略验证机制测试**
   - 测试策略组合验证
   - 验证因子冲突检测

## 🚀 性能优化

### 内存管理
- 使用gc_after_trial自动清理
- 批量处理减少内存峰值

### 并行优化
- 支持多进程并行试验
- Redis分布式存储支持

### 计算效率
- 固定参数空间减少解析开销
- 预计算策略配置避免重复加载

## ⚠️ 注意事项

1. **版本选择**
   - 推荐使用v2（固定参数空间）
   - v1仅保留用于对比和回退

2. **参数调优**
   - 第一阶段试验数≥700保证充分探索
   - 第二阶段试验数≥300确保精调效果

3. **策略配置**
   - 定期更新strategy_config.yaml
   - 根据市场变化调整策略权重

## 📝 维护指南

### 添加新策略

1. 在strategy_config.yaml中定义新策略
2. 配置core_factors和preferred_directions
3. 更新allowed_combinations规则
4. 运行测试验证兼容性

### 调整优化参数

1. 修改两阶段试验比例（默认70%/30%）
2. 调整指导模式比例（默认70%指导）
3. 更新权重范围和因子数量限制

## 🔍 故障排除

### 常见问题

1. **"CategoricalDistribution does not support dynamic value space"**
   - 原因：使用了v1动态参数版本
   - 解决：切换到v2固定参数版本

2. **因子数量不足**
   - 原因：策略配置的核心因子太少
   - 解决：检查strategy_config.yaml配置

3. **策略组合被拒绝**
   - 原因：选择了不兼容的策略组合
   - 解决：查看discouraged_combinations配置

## 📚 参考资料

- [Optuna官方文档](https://optuna.readthedocs.io/)
- [贝叶斯优化原理](https://arxiv.org/abs/1807.02811)
- [多目标优化策略](https://doi.org/10.1007/978-3-319-07124-4)

## 🎯 未来规划

1. **动态策略权重**：根据市场状态自动调整策略权重
2. **在线学习**：实时更新策略偏好
3. **多目标优化**：同时优化CAGR、夏普比率、最大回撤
4. **自适应探索**：根据收敛情况动态调整探索比例

---

*最后更新：2024-12-16*
*版本：2.0.0*
*作者：PromptX团队*