# 可转债多因子优化框架 - 项目结构说明

## 文件结构概览

```
optuna_search/new_test/
├── domain_knowledge_optimizer.py  # 主入口文件
├── optimization_engine.py         # 优化引擎
├── utils/
│   ├── __init__.py
│   └── common_utils.py            # 通用工具函数
├── strategies/
│   ├── __init__.py
│   ├── factor_strategies.py       # 因子策略
│   └── multistage_optimizer.py    # 多阶段优化
└── notification/
    ├── __init__.py
    └── dingtalk_notifier.py       # 钉钉通知
```

## 模块功能说明

### 1. 主入口文件 (domain_knowledge_optimizer.py)
- **功能**: 程序的主入口点，负责解析命令行参数并启动优化流程
- **主要组件**:
  - `parse_args()`: 解析命令行参数
  - `main()`: 主函数，加载数据并调用优化引擎

### 2. 通用工具模块 (utils/common_utils.py)
- **功能**: 提供各种通用工具函数
- **主要组件**:
  - `load_data()`: 加载数据
  - `create_sampler()`: 创建优化采样器
  - `save_optimization_result()`: 保存优化结果
  - `filter_redundant_factors()`: 过滤冗余因子

### 3. 因子策略模块 (strategies/factor_strategies.py)
- **功能**: 实现不同的因子选择和组合策略
- **主要组件**:
  - `domain_knowledge_factors()`: 基于领域知识对因子进行分类
  - `domain_knowledge_combinations()`: 使用领域知识生成因子组合
  - `prescreen_factors()`: 预筛选最有潜力的单因子
  - `choose_strategy()`: 根据选择的策略生成因子组合

### 4. 多阶段优化模块 (strategies/multistage_optimizer.py)
- **功能**: 实现多阶段优化的核心逻辑
- **主要组件**:
  - `multistage_optimization()`: 多阶段优化策略
  - `objective()`: 优化目标函数

### 5. 优化引擎模块 (optimization_engine.py)
- **功能**: 负责执行优化过程的核心逻辑
- **主要组件**:
  - `run_optimization()`: 运行优化过程

### 6. 钉钉通知模块 (notification/dingtalk_notifier.py)
- **功能**: 负责将优化结果发送到钉钉
- **主要组件**:
  - `load_factor_mapping()`: 加载因子中英文映射
  - `get_factor_chinese_name()`: 获取因子的中文名称
  - `send_optimization_result_to_dingtalk()`: 发送优化结果到钉钉

## 优化策略说明

### 1. 领域知识策略 (domain)
- 基于领域知识对因子进行分类，从不同类别中选择因子组合
- 确保每个组合包含多样化的因子类型

### 2. 预筛选策略 (prescreen)
- 先评估每个单因子的性能
- 选择表现最好的因子进行组合优化

### 3. 多阶段策略 (multistage)
- 第一阶段：广泛探索不同的因子组合
- 第二阶段：聚焦于最佳因子组合，优化权重和排序方向

### 4. 过滤冗余策略 (filter)
- 根据业务知识过滤掉冗余因子
- 使用过滤后的因子集合生成组合

## 使用方法

### 基本用法
```bash
python domain_knowledge_optimizer.py --strategy multistage --n_factors 3 --n_trials 3000
```

### 主要参数
- `--method`: 优化方法 (tpe, random, cmaes)
- `--n_trials`: 优化迭代次数
- `--n_factors`: 因子数量 (3, 4, 5)
- `--start_date`: 回测开始日期
- `--end_date`: 回测结束日期
- `--price_min`: 价格下限
- `--price_max`: 价格上限
- `--hold_num`: 持仓数量
- `--n_jobs`: 并行任务数
- `--strategy`: 优化策略 (domain, prescreen, multistage, filter)
- `--seed`: 随机种子

## 代码改进说明

1. **代码模块化**：按功能将代码拆分到不同文件，降低了单文件的复杂度
2. **降低耦合度**：各模块之间通过清晰的接口进行交互
3. **提高可维护性**：每个模块专注于单一职责，便于后续维护和扩展
4. **优化错误处理**：增强了异常处理，提高了系统稳定性
5. **改进并行处理**：优化了多阶段优化中的并行处理逻辑，减少竞争条件
