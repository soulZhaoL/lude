<execution>
  <constraint>
    ## lude项目量化研究约束
    - **策略配置约束**：必须使用`strategy_config.yaml`中定义的6大投资策略
    - **因子范围约束**：只能使用项目定义的51个标准因子
    - **优化框架约束**：使用Optuna TPE算法进行贝叶斯优化
    - **计算资源约束**：单次优化试验数量建议3000以内
    - **环境依赖约束**：必须在conda lude环境中执行优化任务
  </constraint>

  <rule>
    ## 量化研究强制规则  
    - **语义化规则**：因子选择必须基于投资策略语义，不能随机选择
    - **多阶段规则**：必须使用两阶段优化流程(70%探索 + 30%精调)
    - **验证规则**：策略结果必须通过样本外验证和稳健性测试
    - **文档规则**：每个策略必须有清晰的投资逻辑说明
    - **风险控制规则**：CAGR优化不能以过度风险暴露为代价
  </rule>

  <guideline>
    ## 量化研究指导原则
    - **逻辑驱动**：先有投资逻辑，再做数据验证
    - **简洁有效**：优先简单稳健的策略，避免过度复杂化
    - **持续迭代**：基于市场反馈和新数据持续优化
    - **风险平衡**：收益目标与风险控制并重
    - **可解释性**：策略结果要能给出合理的经济学解释
  </guideline>

  <process>
    ## lude项目量化策略研究标准流程
    
    ### Step 1: 策略假设和逻辑梳理
    
    ```mermaid
    flowchart TD
        A[市场观察] --> B[投资假设形成]
        B --> C[选择匹配的投资策略]
        C --> D[确定核心因子]
        D --> E[设计验证方案]
        
        A1["观察市场现象<br/>• 可转债溢价率变化<br/>• 市场情绪波动<br/>• 基本面变化趋势"]
        B1["提出投资假设<br/>• 低溢价率标的收益更高?<br/>• 成长性因子有效性?<br/>• 动量效应存在性?"]
        C1["选择投资策略<br/>• Value: 溢价率相关<br/>• Growth: 成长指标<br/>• Momentum: 价格动量"]
        D1["确定因子组合<br/>• 主要因子选择<br/>• 权重范围设定<br/>• 方向性确定"]
        
        A -.-> A1
        B -.-> B1
        C -.-> C1  
        D -.-> D1
    ```
    
    ### Step 2: 语义化多阶段优化执行
    
    ```mermaid
    graph TD
        A[配置优化参数] --> B[第一阶段：语义化探索]
        B --> C[分析第一阶段结果]
        C --> D[第二阶段：平衡精调]
        D --> E[结果合并和排序]
        E --> F[最优策略提取]
        
        subgraph 第一阶段参数
            B1[trials: 70%总数]
            B2[策略导向权重]
            B3[因子来源约束]
        end
        
        subgraph 第二阶段参数  
            D1[trials: 30%总数]
            D2[探索-指导平衡]
            D3[精细参数调整]
        end
        
        B --> B1
        B --> B2
        B --> B3
        D --> D1
        D --> D2  
        D --> D3
    ```
    
    ### Step 3: 优化执行的具体命令
    
    ```mermaid
    flowchart LR
        A[设置环境] --> B[配置参数]
        B --> C[启动优化]
        C --> D[监控进度]
        D --> E[结果分析]
        
        A1["source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude"]
        B1["设置时间窗口、因子数量、试验次数等"]
        C1["./run_optimizer.sh -m continuous --strategy multistage"]
        D1["查看实时优化日志和中间结果"]
        E1["分析最优策略的投资逻辑和风险特征"]
        
        A -.-> A1
        B -.-> B1
        C -.-> C1
        D -.-> D1
        E -.-> E1
    ```
    
    ### Step 4: 策略验证和分析流程
    
    ```mermaid
    graph TD
        A[获取最优策略] --> B[样本外验证]
        B --> C[风险指标计算]
        C --> D[因子贡献分析]  
        D --> E[稳健性测试]
        E --> F[经济意义解释]
        F --> G[实施可行性评估]
        
        subgraph 验证指标
            H[CAGR]
            I[最大回撤]
            J[夏普比率]
            K[信息比率]
            L[胜率]
        end
        
        C --> H
        C --> I
        C --> J
        C --> K
        C --> L
    ```
    
    ### Step 5: 标准执行脚本模板
    
    ```python
    # lude项目量化策略研究执行模板
    
    import yaml
    import pandas as pd
    from lude.optimization.unified_optimizer import UnifiedOptimizer
    from lude.config.paths import get_path_info
    from lude.utils.logger import get_logger
    
    def execute_quantitative_research():
        """量化策略研究标准执行流程"""
        
        logger = get_logger(__name__)
        paths = get_path_info()
        
        # 1. 加载策略配置
        config_path = paths['config'] / 'strategy_config.yaml'
        with open(config_path, 'r', encoding='utf-8') as f:
            strategy_config = yaml.safe_load(f)
        
        logger.info("策略配置加载完成")
        
        # 2. 设置优化参数
        optimization_params = {
            'method': 'tpe',
            'strategy': 'multistage', 
            'start_date': '20220729',
            'end_date': '20240607',
            'min_factors': 100,
            'max_factors': 150,
            'n_jobs': 5,
            'n_trials': 3000,
            'hold_days': 15
        }
        
        # 3. 创建优化器
        optimizer = UnifiedOptimizer(
            **optimization_params,
            config=strategy_config
        )
        
        # 4. 执行多阶段优化
        logger.info("开始语义化多阶段优化")
        study = optimizer.optimize()
        
        # 5. 分析最优结果
        best_trial = study.best_trial
        best_cagr = best_trial.value
        best_params = best_trial.params
        
        logger.info(f"最优CAGR: {best_cagr:.4f}")
        logger.info(f"最优参数: {best_params}")
        
        # 6. 策略解释和验证
        analyze_strategy_semantics(best_params, strategy_config)
        
        return study, best_trial
    
    def analyze_strategy_semantics(params, config):
        """分析策略的语义含义"""
        
        # 提取投资策略信息
        primary_strategy = params.get('primary_strategy')
        secondary_strategy = params.get('secondary_strategy')
        
        print(f"\n=== 最优策略语义分析 ===")
        print(f"主策略: {primary_strategy}")
        if secondary_strategy:
            print(f"次策略: {secondary_strategy}")
            
        # 提取因子信息
        factors_info = []
        for key, value in params.items():
            if key.startswith('factor_') and key.endswith('_name'):
                factor_idx = key.split('_')[1]
                factor_name = value
                weight = params.get(f'factor_{factor_idx}_weight', 'Unknown')
                direction = params.get(f'factor_{factor_idx}_direction', 'Unknown')
                
                # 查找因子来源策略
                source_strategy = find_factor_source(factor_name, config)
                
                factors_info.append({
                    'factor': factor_name,
                    'weight': weight, 
                    'direction': '降序' if direction == 0 else '升序',
                    'source': source_strategy
                })
        
        print(f"\n📊 因子组合:")
        for i, info in enumerate(factors_info, 1):
            print(f"  {i}. {info['factor']}: 权重={info['weight']}, "
                  f"方向={info['direction']}, 来源={info['source']}")
                  
    def find_factor_source(factor_name, config):
        """查找因子所属的投资策略"""
        for strategy, details in config['investment_strategies'].items():
            if factor_name in details.get('core_factors', []):
                return strategy
        return 'unknown'
    ```
    
    ### Step 6: 高级分析和监控
    
    ```mermaid
    flowchart TD
        A[基础策略结果] --> B[深度分析]
        B --> C[风险分解]
        C --> D[归因分析]
        D --> E[敏感性测试]
        E --> F[监控Dashboard]
        
        subgraph 深度分析内容
            G[单因子贡献度]
            H[策略稳定性]
            I[市场环境适应性]
            J[容量和成本分析]
        end
        
        B --> G
        B --> H
        B --> I
        B --> J
    ```
    
    ### 持续优化和迭代机制
    
    ```python
    def setup_strategy_monitoring():
        """设置策略监控和迭代机制"""
        
        # 设置定期重新优化
        schedule_reoptimization = {
            'frequency': 'monthly',  # 月度重新优化
            'trigger_conditions': [
                'CAGR下降超过10%',
                '最大回撤超过阈值', 
                '新因子数据可用'
            ]
        }
        
        # 设置实时监控指标
        monitoring_metrics = [
            'real_time_cagr',
            'current_drawdown', 
            'factor_effectiveness',
            'strategy_deviation'
        ]
        
        return schedule_reoptimization, monitoring_metrics
    ```
  </process>

  <criteria>
    ## 量化研究质量标准
    
    ### 策略逻辑标准
    - ✅ 投资假设有清晰的经济学基础
    - ✅ 因子选择与投资策略语义匹配
    - ✅ 策略组合逻辑自洽不矛盾
    - ✅ 风险收益特征符合预期
    - ✅ 策略可以用简单语言解释

    ### 技术实现标准
    - ✅ 优化过程使用标准的多阶段流程
    - ✅ 贝叶斯优化参数设置合理
    - ✅ 代码在项目环境中正常运行
    - ✅ 计算结果可重现和验证
    - ✅ 异常情况处理完善

    ### 研究深度标准  
    - ✅ 样本内外结果一致性良好
    - ✅ 不同市场环境下稳健性测试
    - ✅ 因子贡献度分析清晰
    - ✅ 风险来源识别准确
    - ✅ 实施成本和容量评估

    ### 业务价值标准
    - ✅ CAGR提升有统计和经济显著性
    - ✅ 策略复杂度与收益改善匹配
    - ✅ 风险调整后收益有竞争力
    - ✅ 策略在实际投资中可执行
    - ✅ 为投资决策提供有价值洞察
  </criteria>
</execution>