<execution>
  <constraint>
    ## Optuna技术约束
    - **版本兼容性**：确保optuna版本与项目依赖兼容（通常>=3.0）
    - **存储后端限制**：SQLite不支持并发写入，Redis需要额外服务
    - **内存限制**：大规模Study历史会消耗大量内存
    - **采样算法约束**：TPE需要足够的历史试验才能有效工作
    
    ## 计算资源约束
    - **并发限制**：>10 jobs时必须使用分布式存储避免锁竞争
    - **trial超时**：单个trial不应超过合理时间避免资源浪费
    - **存储空间**：optimization_results目录需要足够空间存储模型
  </constraint>
  
  <rule>
    ## Optuna使用强制规则
    - **Study命名规范**：使用有意义的study_name便于管理和调试
    - **存储选择规则**：jobs > 10强制Redis，jobs <= 10使用SQLite
    - **目标函数返回**：必须返回float类型，NaN时应raise TrialPruned
    - **参数定义完整性**：所有suggest_*调用必须在objective函数内部
    - **异常处理规范**：捕获异常时使用trial.set_user_attr记录错误信息
    
    ## 性能优化规则
    - **Pruner强制使用**：MedianPruner用于提前终止无希望的trial
    - **采样器参数调优**：n_startup_trials设为总trial数的10-20%
    - **批量提交**：使用enqueue_trial批量提交已知的良好起始点
  </rule>
  
  <guideline>
    ## Optuna最佳实践指南
    
    ### Study设计指南
    ```mermaid
    flowchart TD
        A[定义目标函数] --> B{目标类型}
        B -->|单目标| C[direction=minimize/maximize]
        B -->|多目标| D[directions=['minimize', 'maximize']]
        C --> E[选择合适的Sampler]
        D --> E
        E --> F{历史数据}
        F -->|有| G[enqueue已知好解]
        F -->|无| H[纯随机启动]
        G --> I[开始优化]
        H --> I
    ```
    
    ### 参数空间设计指南
    - **数值参数**：优先使用suggest_float，注意log=True适用于跨数量级搜索
    - **离散参数**：suggest_int用于整数，suggest_categorical用于枚举
    - **条件参数**：使用if语句实现参数间的依赖关系
    - **边界设置**：基于领域知识设定合理边界，避免过大搜索空间
    
    ### 监控和调试指南
    - **进度可视化**：定期输出best_value和best_params
    - **中间结果记录**：使用trial.report记录训练过程指标
    - **用户属性**：trial.set_user_attr保存额外的调试信息
    - **日志记录**：在objective函数中记录关键步骤和异常
  </guideline>
  
  <process>
    ## 标准Optuna优化工作流
    
    ### Step 1: 环境准备与配置验证 (5分钟)
    ```python
    # 环境激活和依赖检查
    source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude
    
    # 验证Optuna安装和版本
    import optuna
    print(f"Optuna版本: {optuna.__version__}")
    
    # 存储后端选择
    if jobs > 10:
        storage = "redis://localhost:6379/0"
        # 确保Redis服务运行
        ./redis/start_redis.sh dev
    else:
        storage = "sqlite:///optuna_study.db"
    ```
    
    ### Step 2: 目标函数设计与参数空间定义 (15分钟)
    ```mermaid
    graph TD
        A[分析业务目标] --> B[设计CAGR目标函数]
        B --> C[定义因子权重参数]
        C --> D[设置筛选条件参数]
        D --> E[添加约束条件检查]
        E --> F[异常处理机制]
        F --> G[返回值验证]
    ```
    
    ### Step 3: Study创建与优化器配置 (10分钟)
    ```python
    # 创建Study对象
    study = optuna.create_study(
        study_name=f"convertible_bond_optimization_{datetime.now().strftime('%Y%m%d_%H%M')}",
        storage=storage,
        direction='maximize',  # CAGR最大化
        sampler=optuna.samplers.TPESampler(
            n_startup_trials=max(50, n_trials // 10),  # 启动试验数
            n_ei_candidates=24,  # EI候选点数
            multivariate=True,   # 多变量TPE
            warn_independent_sampling=True
        ),
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=20,
            n_warmup_steps=10,
            interval_steps=1
        )
    )
    ```
    
    ### Step 4: 优化执行与实时监控 (主要执行时间)
    ```mermaid
    flowchart LR
        A[启动优化] --> B[Trial执行]
        B --> C{性能检查}
        C -->|CAGR > 0.45| D[钉钉通知]
        C -->|CAGR > 0.40| E[保存模型]
        C -->|继续| F[下一个Trial]
        D --> F
        E --> F
        F --> G{达到试验数}
        G -->|否| B
        G -->|是| H[输出最佳结果]
    ```
    
    ### Step 5: 结果分析与验证 (15分钟)
    ```python
    # 获取最佳结果
    best_trial = study.best_trial
    best_params = study.best_params
    best_value = study.best_value
    
    # 过拟合检测
    from lude.core.overfitting_detector import detect_overfitting
    overfitting_score = detect_overfitting(best_params, historical_data)
    
    # 结果验证和保存
    if best_value > 0.40 and overfitting_score < 0.3:
        save_best_model(best_params, best_value)
        
    # 可视化分析（可选）
    optuna.visualization.plot_optimization_history(study)
    optuna.visualization.plot_param_importances(study)
    ```
    
    ### Step 6: 生产部署准备 (10分钟)
    ```mermaid
    graph LR
        A[最佳参数提取] --> B[模型序列化]
        B --> C[配置文件更新]
        C --> D[A/B测试准备]
        D --> E[监控告警设置]
    ```
  </process>
  
  <criteria>
    ## Optuna优化质量评估标准
    
    ### 收敛性评估
    - ✅ 优化历史显示明确的收敛趋势
    - ✅ 最近20%的trials中至少50%优于中位数
    - ✅ best_value在最后100个trials中有显著改善
    - ✅ 参数重要性分析结果合理（主要因子权重高）
    
    ### 稳定性验证
    - ✅ 最佳参数在多次独立运行中稳定
    - ✅ 过拟合检测分数 < 0.3（自定义阈值）
    - ✅ 交叉验证结果与优化结果一致性 > 85%
    - ✅ 关键约束条件在所有best trials中都满足
    
    ### 实用性检查
    - ✅ CAGR性能指标 > 0.40（项目要求）
    - ✅ 因子权重分布符合业务逻辑
    - ✅ 筛选条件在合理范围内
    - ✅ 可复现性验证通过
    
    ### 效率指标
    - ✅ 平均trial执行时间 < 预期阈值
    - ✅ Pruner有效性 > 30%（被剪枝的trial比例）
    - ✅ 存储和内存使用在合理范围
    - ✅ 并发效率 > 80%（实际并发/理论并发）
  </criteria>
</execution>