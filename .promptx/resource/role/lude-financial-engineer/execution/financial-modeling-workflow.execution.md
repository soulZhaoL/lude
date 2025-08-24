<execution>
  <constraint>
    ## lude项目数学计算约束
    - **精度要求**：CAGR计算精度至少保持到小数点后6位
    - **性能约束**：单次CAGR计算不超过1ms，批量计算支持向量化
    - **数值稳定性**：必须处理0值、负值、无穷大等边界情况
    - **内存限制**：大规模数据处理时内存使用不超过可用内存的80%
    - **环境依赖**：必须在conda lude环境中运行，确保数值库版本一致
  </constraint>

  <rule>
    ## 金融建模强制规则
    - **数学验证规则**：所有公式实现前必须手工验证至少3个测试案例
    - **边界测试规则**：必须测试零值、负值、极大值、极小值等边界情况
    - **精度验证规则**：与已知基准结果的误差不超过1e-6
    - **性能基准规则**：新实现的算法性能不能低于现有方法90%
    - **代码审查规则**：数值计算相关代码必须经过同行评审
  </rule>

  <guideline>
    ## 金融建模指导原则
    - **数学优先**：优先保证数学正确性，再考虑工程优化
    - **渐进开发**：从简单版本开始，逐步增加复杂特性
    - **文档驱动**：每个公式和算法都要有完整的数学文档
    - **测试先行**：先写测试用例，再实现具体算法
    - **性能意识**：时刻关注计算复杂度和内存使用
  </guideline>

  <process>
    ## lude项目CAGR建模标准流程
    
    ### Step 1: 数学基础研究和设计
    
    ```mermaid
    flowchart TD
        A[需求分析] --> B[文献调研]
        B --> C[数学推导]
        C --> D[算法设计]
        D --> E[复杂度分析]
        E --> F[设计文档]
        
        A1["明确CAGR计算的具体要求<br/>• 时间窗口范围<br/>• 精度要求<br/>• 性能目标"]
        B1["研究现有CAGR计算方法<br/>• 标准公式<br/>• 数值稳定版本<br/>• 优化算法"]
        C1["推导数学公式<br/>• 基础CAGR公式<br/>• 数值稳定化变换<br/>• 边界条件处理"]
        D1["设计算法流程<br/>• 输入验证<br/>• 计算步骤<br/>• 输出格式"]
        E1["分析时间和空间复杂度<br/>• 最坏情况分析<br/>• 平均情况分析<br/>• 内存使用估算"]
        
        A -.-> A1
        B -.-> B1
        C -.-> C1
        D -.-> D1
        E -.-> E1
    ```
    
    ### Step 2: 核心算法实现
    
    ```mermaid
    flowchart LR
        A[基础实现] --> B[边界处理]
        B --> C[精度优化]
        C --> D[性能优化]
        D --> E[集成测试]
        
        subgraph 实现技术
            F[Decimal高精度计算]
            G[NumPy向量化]
            H[异常处理机制]
            I[缓存策略]
        end
        
        A --> F
        B --> H
        C --> F
        D --> G
        D --> I
    ```
    
    ### Step 3: CAGR计算器的具体实现模式
    
    ```mermaid
    graph TD
        A[输入数据] --> B{数据验证}
        B -->|通过| C[计算准备]
        B -->|失败| D[抛出异常]
        
        C --> E{计算方法选择}
        E -->|标准方法| F[几何平均计算]
        E -->|对数方法| G[对数线性化计算]
        E -->|稳健方法| H[数值稳定计算]
        
        F --> I[结果验证]
        G --> I
        H --> I
        
        I --> J{结果合理?}
        J -->|是| K[返回结果]
        J -->|否| L[切换方法重算]
        L --> E
        
        subgraph 验证规则
            M[非空检查]
            N[数值范围检查]
            O[时间序列检查]
            P[精度验证]
        end
        
        B --> M
        B --> N
        B --> O
        I --> P
    ```
    
    ### Step 4: 标准实现模板
    
    ```python
    # lude项目CAGR计算标准模板
    
    from decimal import Decimal, getcontext
    import numpy as np
    import pandas as pd
    from typing import Union, Optional
    from lude.utils.logger import get_logger
    
    class CAGRCalculator:
        """CAGR计算器 - lude项目标准实现"""
        
        def __init__(self, precision: int = 10):
            """初始化计算器
            
            Args:
                precision: 计算精度，默认10位小数
            """
            getcontext().prec = precision
            self.logger = get_logger(__name__)
            
        def calculate_standard_cagr(self, 
                                  start_value: float, 
                                  end_value: float, 
                                  periods: float) -> float:
            """标准CAGR计算方法"""
            try:
                # 输入验证
                self._validate_inputs(start_value, end_value, periods)
                
                # 边界情况处理
                if start_value <= 0:
                    return self._handle_zero_start_value(end_value, periods)
                
                # 标准公式计算
                ratio = Decimal(str(end_value)) / Decimal(str(start_value))
                power = Decimal('1') / Decimal(str(periods))
                cagr = float(ratio ** power - 1)
                
                # 结果验证
                self._validate_result(cagr)
                
                return cagr
                
            except Exception as e:
                self.logger.error(f"CAGR计算失败: {e}")
                raise
                
        def calculate_log_cagr(self, returns: pd.Series) -> float:
            """基于对数收益的CAGR计算"""
            log_returns = np.log(1 + returns)
            periods_per_year = self._get_periods_per_year(returns.index)
            annual_log_return = log_returns.mean() * periods_per_year
            return float(np.exp(annual_log_return) - 1)
            
        def _validate_inputs(self, start_value, end_value, periods):
            """输入验证"""
            if periods <= 0:
                raise ValueError("时间周期必须为正数")
            if pd.isna(start_value) or pd.isna(end_value):
                raise ValueError("输入值不能为NaN")
                
        def _validate_result(self, cagr):
            """结果验证"""
            if pd.isna(cagr) or np.isinf(cagr):
                raise ValueError("CAGR计算结果无效")
    ```
    
    ### Step 5: 性能基准测试
    
    ```mermaid
    flowchart TD
        A[准备测试数据] --> B[单次计算基准]
        B --> C[批量计算基准]
        C --> D[内存使用基准]
        D --> E[精度对比基准]
        E --> F[生成性能报告]
        
        subgraph 基准指标
            G[计算时间]
            H[内存峰值]
            I[精度误差]
            J[稳定性]
        end
        
        B --> G
        C --> G
        D --> H
        E --> I
        F --> J
    ```
    
    ### 标准测试脚本模板
    
    ```python
    # 性能基准测试脚本
    import time
    import numpy as np
    from memory_profiler import profile
    
    def benchmark_cagr_performance():
        """CAGR计算性能基准测试"""
        
        # 测试数据准备
        test_cases = [
            (100, 150, 2),    # 标准情况
            (1e-6, 1e6, 10),  # 极值情况
            (100, 50, 3),     # 负收益情况
        ]
        
        calculator = CAGRCalculator()
        
        # 单次计算性能测试
        for start, end, periods in test_cases:
            start_time = time.perf_counter()
            result = calculator.calculate_standard_cagr(start, end, periods)
            end_time = time.perf_counter()
            
            print(f"计算时间: {(end_time - start_time) * 1000:.3f}ms")
            print(f"CAGR结果: {result:.6f}")
            
        # 批量计算性能测试
        n_calculations = 10000
        start_values = np.random.uniform(50, 200, n_calculations)
        end_values = np.random.uniform(100, 300, n_calculations)
        periods = np.random.uniform(1, 10, n_calculations)
        
        start_time = time.perf_counter()
        results = [calculator.calculate_standard_cagr(s, e, p) 
                  for s, e, p in zip(start_values, end_values, periods)]
        end_time = time.perf_counter()
        
        avg_time = (end_time - start_time) / n_calculations * 1000
        print(f"批量计算平均时间: {avg_time:.3f}ms per calculation")
    ```
  </process>

  <criteria>
    ## 金融建模质量标准
    
    ### 数学正确性标准
    - ✅ 公式推导有完整的数学证明
    - ✅ 边界条件处理逻辑正确
    - ✅ 数值精度满足业务要求(6位小数)
    - ✅ 与已知基准结果误差 < 1e-6
    - ✅ 通过所有单元测试用例

    ### 性能效率标准
    - ✅ 单次CAGR计算 < 1ms
    - ✅ 支持向量化批量计算
    - ✅ 内存使用合理(< 80%可用内存)
    - ✅ 大数据集处理不出现内存泄露
    - ✅ 算法时间复杂度可接受

    ### 工程质量标准
    - ✅ 代码结构清晰，注释完整
    - ✅ 异常处理覆盖全面
    - ✅ 日志记录详细有用
    - ✅ 与项目架构良好集成
    - ✅ 遵循项目编码规范

    ### 稳健性标准
    - ✅ 处理各种边界输入情况
    - ✅ 数值计算稳定不溢出
    - ✅ 在不同数据规模下表现一致
    - ✅ 对输入噪声有合理容忍度
    - ✅ 长时间运行不出现精度漂移
  </criteria>
</execution>