<execution>
  <constraint>
    ## 金融产品设计约束
    - **监管合规约束**：必须符合可转债交易相关法规
    - **流动性约束**：单只转债持仓不超过流通量的5%
    - **风险预算约束**：单一策略最大回撤不超过15%
    - **资金容量约束**：策略容量受市场流动性限制
    - **技术实现约束**：系统延迟和计算资源限制
  </constraint>

  <rule>
    ## 产品设计强制规则
    - **分散化要求**：持仓标的数量不少于20只
    - **止损机制**：必须设置动态止损和固定止损
    - **仓位管理**：总仓位控制在合规范围内
    - **再平衡频率**：根据策略特性确定调仓频率
    - **业绩基准**：必须设置合适的业绩比较基准
    - **透明度要求**：策略逻辑和风险特征充分披露
  </rule>

  <guideline>
    ## 产品设计指导原则
    - **风险收益匹配**：产品风险等级与目标客户风险偏好匹配
    - **策略差异化**：与市场现有产品形成明显差异化
    - **可扩展性考虑**：为未来产品升级预留空间
    - **成本效率优化**：在满足策略需求下最小化交易成本
    - **用户体验优化**：提供清晰的业绩归因和风险报告
  </guideline>

  <process>
    ## 金融产品设计流程

    ### Phase 1: 市场需求分析与产品定位
    ```mermaid
    flowchart TD
        A[市场调研] --> B[客户需求分析]
        B --> C[竞品分析]
        C --> D[产品定位]
        D --> E[目标收益设定]
        E --> F[风险预算分配]
    ```
    
    **需求分析框架**：
    ```python
    def analyze_market_demand():
        """市场需求分析"""
        market_analysis = {
            'target_clients': ['银行理财', '保险资金', '私募基金', '高净值个人'],
            'risk_preferences': {
                '保守型': {'target_return': 0.08, 'max_drawdown': 0.05},
                '稳健型': {'target_return': 0.12, 'max_drawdown': 0.08},
                '积极型': {'target_return': 0.18, 'max_drawdown': 0.15}
            },
            'market_gaps': [
                '中低风险可转债策略产品稀缺',
                '多因子量化产品透明度不足',
                '动态风控机制有待完善'
            ]
        }
        return market_analysis
    ```
    
    ### Phase 2: 策略框架设计
    ```mermaid
    graph LR
        A[投资理念] --> B[策略逻辑]
        B --> C[因子体系]
        C --> D[风控体系]
        D --> E[交易体系]
        E --> F[归因体系]
    ```
    
    **核心策略配置**：
    ```yaml
    # 可转债多因子策略配置
    strategy_config:
      name: "可转债多因子增强策略"
      version: "1.0.0"
      
      investment_philosophy:
        - "基于多因子模型的系统化投资"
        - "风险调整收益最大化"
        - "动态风险管理"
      
      factor_categories:
        value_factors:
          - premium_rate  # 转股溢价率
          - pb_ratio     # 市净率
          - pe_ratio     # 市盈率
          weight_range: [1, 5]
          
        growth_factors:
          - roe_growth   # ROE增长率
          - revenue_growth # 营收增长率
          weight_range: [1, 5]
          
        momentum_factors:
          - price_momentum_20d
          - volume_momentum_10d
          weight_range: [1, 5]
          
        quality_factors:
          - debt_ratio   # 资产负债率
          - current_ratio # 流动比率
          weight_range: [1, 5]
    ```
    
    ### Phase 3: 风险管理体系构建
    ```mermaid
    flowchart TD
        A[风险识别] --> B[风险测量]
        B --> C[风险限额]
        C --> D[风险监控]
        D --> E[风险报告]
        E --> F[风险调整]
        F --> D
    ```
    
    **风险管理模块**：
    ```python
    class RiskManagementSystem:
        def __init__(self, config):
            self.max_position_weight = config.get('max_position_weight', 0.05)
            self.max_sector_weight = config.get('max_sector_weight', 0.30)
            self.max_drawdown_limit = config.get('max_drawdown_limit', 0.15)
            self.var_limit = config.get('var_limit', 0.02)
            
        def check_position_limits(self, positions):
            """检查持仓限制"""
            violations = []
            
            # 个券集中度检查
            for asset, weight in positions.items():
                if weight > self.max_position_weight:
                    violations.append(f"个券{asset}权重{weight:.2%}超限")
            
            return violations
        
        def calculate_portfolio_risk(self, positions, covariance_matrix):
            """计算组合风险"""
            weights = np.array(list(positions.values()))
            portfolio_var = np.dot(weights.T, np.dot(covariance_matrix, weights))
            portfolio_vol = np.sqrt(portfolio_var * 252)  # 年化波动率
            
            return {
                'annual_volatility': portfolio_vol,
                'daily_var_95': np.sqrt(portfolio_var) * 1.645,
                'risk_budget_utilization': portfolio_vol / 0.20  # 假设风险预算20%
            }
    ```
    
    ### Phase 4: 组合优化算法
    ```python
    from scipy.optimize import minimize
    import cvxpy as cp
    
    def optimize_portfolio(expected_returns, covariance_matrix, risk_aversion=1.0):
        """均值方差优化"""
        n_assets = len(expected_returns)
        
        # 定义优化变量
        weights = cp.Variable(n_assets)
        
        # 定义目标函数：最大化效用 = 期望收益 - 风险惩罚
        expected_return = expected_returns.T @ weights
        risk_penalty = cp.quad_form(weights, covariance_matrix) * risk_aversion / 2
        utility = expected_return - risk_penalty
        
        # 约束条件
        constraints = [
            cp.sum(weights) == 1,  # 权重和为1
            weights >= 0.01,       # 最小权重1%
            weights <= 0.05,       # 最大权重5%
        ]
        
        # 求解优化问题
        problem = cp.Problem(cp.Maximize(utility), constraints)
        problem.solve()
        
        if problem.status == 'optimal':
            return weights.value
        else:
            raise ValueError(f"优化失败: {problem.status}")
    ```
    
    ### Phase 5: 业绩归因体系
    ```mermaid
    graph TD
        A[总收益] --> B[基准收益]
        A --> C[超额收益]
        C --> D[因子贡献]
        C --> E[选股贡献]
        C --> F[时机贡献]
        
        D --> G[价值因子贡献]
        D --> H[成长因子贡献]
        D --> I[动量因子贡献]
    ```
    
    **归因分析模块**：
    ```python
    def performance_attribution(portfolio_returns, benchmark_returns, 
                              factor_exposures, factor_returns):
        """Brinson归因分析"""
        
        # 计算超额收益
        excess_returns = portfolio_returns - benchmark_returns
        
        # 因子贡献分解
        factor_contribution = {}
        for factor_name in factor_exposures.columns:
            # 因子暴露度 × 因子收益率
            contribution = (factor_exposures[factor_name] * 
                          factor_returns[factor_name]).sum()
            factor_contribution[factor_name] = contribution
        
        # 计算个股选择贡献
        total_factor_contrib = sum(factor_contribution.values())
        stock_selection = excess_returns.sum() - total_factor_contrib
        
        attribution_result = {
            'total_excess_return': excess_returns.sum(),
            'factor_contributions': factor_contribution,
            'stock_selection_contribution': stock_selection,
            'attribution_r_squared': calculate_attribution_r_squared(
                excess_returns, factor_contribution
            )
        }
        
        return attribution_result
    ```
    
    ### Phase 6: 产品文档与合规
    ```mermaid
    flowchart LR
        A[产品说明书] --> B[风险揭示书]
        B --> C[投资策略说明]
        C --> D[费用结构说明]
        D --> E[业绩报告模板]
        E --> F[合规检查清单]
    ```
    
    **产品文档模板**：
    ```python
    def generate_product_documentation():
        """生成产品文档"""
        
        product_doc = {
            'basic_info': {
                'product_name': '可转债多因子增强策略',
                'product_type': '私募证券投资基金',
                'investment_strategy': '多因子量化选股',
                'benchmark': '中证转债指数',
                'risk_level': 'R4-中高风险'
            },
            
            'investment_scope': {
                'primary_assets': '可转换公司债券',
                'secondary_assets': '国债、金融债、企业债',
                'derivatives': '股指期货(对冲用途)',
                'cash_management': '货币市场工具'
            },
            
            'risk_management': {
                'var_monitoring': '日度VaR监控',
                'stress_testing': '月度压力测试',
                'liquidity_management': '流动性风险预警',
                'concentration_limits': '单一标的≤5%，单一行业≤30%'
            },
            
            'fee_structure': {
                'management_fee': '1.5%/年',
                'performance_fee': '20%(超过8%年化基准)',
                'subscription_fee': '0%',
                'redemption_fee': '持有<1年收取1%'
            }
        }
        
        return product_doc
    ```

  </process>

  <criteria>
    ## 产品设计质量标准

    ### 投资表现标准
    - ✅ 年化收益率目标 > 12%
    - ✅ 最大回撤控制 < 15%
    - ✅ 夏普比率 > 1.2
    - ✅ 超额收益显著性 p-value < 0.05
    - ✅ 信息比率 > 0.8
    
    ### 风险管理标准
    - ✅ VaR覆盖率 > 95%
    - ✅ 压力测试通过率 100%
    - ✅ 流动性覆盖比率 > 100%
    - ✅ 集中度指标符合监管要求
    
    ### 运营效率标准
    - ✅ 交易成本 < 年化收益0.5%
    - ✅ 系统可用性 > 99.5%
    - ✅ 净值披露及时性 T+1
    - ✅ 风险报告完整性 100%
    
    ### 合规性标准
    - ✅ 监管报告及时性 100%
    - ✅ 投资限制遵循度 100%
    - ✅ 信息披露合规性 100%
    - ✅ 客户适当性匹配度 100%

  </criteria>
</execution>