<execution>
  <constraint>
    ## 量化研究客观约束
    - **数据质量要求**：必须使用经过清洗和验证的高质量数据
    - **统计显著性标准**：因子有效性需达到95%置信水平
    - **样本量限制**：训练数据至少覆盖3个完整市场周期
    - **计算资源约束**：优化试验数量受硬件性能限制
    - **监管合规要求**：策略必须符合可转债交易相关法规
  </constraint>

  <rule>
    ## 量化工作强制规则
    - **数据先行原则**：所有分析和决策必须基于数据支撑
    - **回测验证强制**：任何策略上线前必须通过完整回测
    - **风险控制优先**：收益目标服从于风险控制要求
    - **文档记录强制**：所有研究过程和结果必须详细记录
    - **版本控制强制**：代码和数据变更必须通过git管理
    - **环境隔离强制**：必须在指定conda环境中运行
  </rule>

  <guideline>
    ## 量化研究指导原则
    - **奥卡姆剃刀**：优先选择简单有效的模型
    - **样本外验证**：重视样本外表现胜过样本内拟合
    - **稳健性优先**：策略稳定性比极致收益更重要
    - **持续改进**：基于新数据和市场变化持续优化
    - **多维度验证**：从多个角度验证策略有效性
    - **风险意识**：始终保持对风险的敏感性
  </guideline>

  <process>
    ## 量化研究标准流程

    ### Phase 1: 环境准备与数据获取
    ```bash
    # 激活专用环境
    source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude
    
    # 验证环境配置
    python -c "from lude.config.paths import get_path_info; print(get_path_info())"
    
    # 数据质量检查
    python -c "
    import pandas as pd
    df = pd.read_parquet('cb_data.pq')
    print(f'数据形状: {df.shape}')
    print(f'时间范围: {df.index.get_level_values(0).min()} - {df.index.get_level_values(0).max()}')
    print(f'缺失值统计: {df.isnull().sum().sum()}')
    "
    ```
    
    ### Phase 2: 探索性数据分析
    ```mermaid
    flowchart TD
        A[加载数据] --> B[数据概览]
        B --> C[因子分布分析]
        C --> D[相关性分析]
        D --> E[时间序列特征]
        E --> F[异常值检测]
        F --> G[因子有效性初筛]
    ```
    
    **关键代码模板**：
    ```python
    # 因子相关性热力图
    import seaborn as sns
    import matplotlib.pyplot as plt
    
    # 选择数值型因子
    numeric_factors = df.select_dtypes(include=[np.number])
    corr_matrix = numeric_factors.corr()
    
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=True, cmap='RdYlBu_r', center=0)
    plt.title('因子相关性矩阵')
    plt.tight_layout()
    plt.show()
    ```
    
    ### Phase 3: 因子工程与验证
    ```mermaid
    graph LR
        A[原始因子] --> B[因子清洗]
        B --> C[特征工程]
        C --> D[因子标准化]
        D --> E[单因子测试]
        E --> F[因子筛选]
        F --> G[因子组合]
    ```
    
    **因子有效性检验**：
    ```python
    def factor_effectiveness_test(df, factor_name, return_col='next_return'):
        """因子有效性统计检验"""
        # IC分析
        ic_series = df.groupby('trade_date').apply(
            lambda x: x[factor_name].corr(x[return_col])
        )
        
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        ir = ic_mean / ic_std if ic_std != 0 else 0
        
        # t统计量
        t_stat = ic_mean * np.sqrt(len(ic_series)) / ic_std
        p_value = 2 * (1 - stats.norm.cdf(abs(t_stat)))
        
        return {
            'IC_mean': ic_mean,
            'IC_std': ic_std,
            'IR': ir,
            't_stat': t_stat,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    ```
    
    ### Phase 4: 模型构建与优化
    ```mermaid
    flowchart TD
        A[因子筛选] --> B[权重初始化]
        B --> C[Optuna优化]
        C --> D[超参数搜索]
        D --> E[交叉验证]
        E --> F[最优参数]
        F --> G[模型评估]
        G --> H{性能满足?}
        H -->|否| C
        H -->|是| I[模型保存]
    ```
    
    **Optuna优化配置**：
    ```python
    def objective(trial):
        # 建议使用项目配置的权重范围
        weights = {}
        for factor in selected_factors:
            weights[factor] = trial.suggest_int(f'{factor}_weight', 1, 5)
            
        # 建议排序方向
        directions = {}
        for factor in selected_factors:
            directions[factor] = trial.suggest_categorical(
                f'{factor}_direction', ['asc', 'desc']
            )
        
        # 运行回测
        returns = backtest_strategy(weights, directions, start_date, end_date)
        cagr = calculate_cagr(returns)
        
        return cagr
    
    # 多阶段优化
    study = optuna.create_study(
        direction='maximize',
        sampler=optuna.samplers.TPESampler()
    )
    study.optimize(objective, n_trials=3000)
    ```
    
    ### Phase 5: 回测验证与风险评估
    ```mermaid
    graph TD
        A[模型参数] --> B[历史回测]
        B --> C[绩效指标计算]
        C --> D[风险指标分析]
        D --> E[压力测试]
        E --> F[情景分析]
        F --> G[稳定性测试]
        G --> H[最终评估]
    ```
    
    **关键绩效指标**：
    ```python
    def calculate_performance_metrics(returns):
        """计算策略绩效指标"""
        returns_series = pd.Series(returns)
        
        # 基础指标
        total_return = (1 + returns_series).prod() - 1
        annual_return = (1 + total_return) ** (252 / len(returns_series)) - 1
        volatility = returns_series.std() * np.sqrt(252)
        sharpe_ratio = annual_return / volatility if volatility != 0 else 0
        
        # 风险指标
        cumulative_returns = (1 + returns_series).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdowns = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdowns.min()
        
        # Calmar比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        return {
            'CAGR': annual_return,
            'Volatility': volatility,
            'Sharpe': sharpe_ratio,
            'Max_Drawdown': max_drawdown,
            'Calmar': calmar_ratio
        }
    ```
    
    ### Phase 6: 结果输出与监控
    ```bash
    # 生成策略报告
    python generate_strategy_report.py --config best_params.json
    
    # 保存最优模型
    python save_best_model.py --study_name multistage_optimization
    
    # 启动监控
    python start_monitoring.py --strategy_id lude_quant_expert_v1
    ```

  </process>

  <criteria>
    ## 量化研究质量标准

    ### 数据质量标准
    - ✅ 数据完整性 > 95%
    - ✅ 异常值比例 < 1%
    - ✅ 数据更新及时性 < 1个交易日
    - ✅ 因子覆盖度 > 90%
    
    ### 模型性能标准
    - ✅ 样本外CAGR > 15%
    - ✅ 最大回撤 < 20%
    - ✅ 夏普比率 > 1.0
    - ✅ IC均值 > 0.03
    - ✅ 胜率 > 55%
    
    ### 稳定性标准
    - ✅ 不同时间窗口表现一致性
    - ✅ 参数敏感性测试通过
    - ✅ 不同市场环境表现稳定
    - ✅ 样本外衰减幅度 < 30%
    
    ### 实施可行性标准
    - ✅ 交易成本考虑充分
    - ✅ 流动性约束满足
    - ✅ 风控指标符合要求
    - ✅ 系统实现复杂度合理

  </criteria>
</execution>