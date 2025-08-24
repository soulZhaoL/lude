<execution>
  <constraint>
    ## lude项目技术约束
    - **环境强制要求**：所有Python操作必须在conda lude环境中执行
    - **路径系统约束**：必须使用`get_path_info()`获取项目标准路径
    - **数据格式约束**：主要处理Parquet格式的可转债数据
    - **依赖版本约束**：遵循项目requirements.txt的包版本要求
    - **内存使用约束**：大数据集分析需考虑内存优化策略
  </constraint>

  <rule>
    ## 强制执行规则
    - **环境激活规则**：每次数据分析前必须执行环境激活命令
    - **数据验证规则**：加载数据后必须进行基础质量检查
    - **路径规范规则**：所有文件路径必须通过配置系统获取
    - **结果保存规则**：分析结果必须保存到项目约定目录
    - **代码规范规则**：遵循项目的flake8和mypy代码质量标准
  </rule>

  <guideline>
    ## 数据分析指导原则
    - **业务导向**：所有分析都要回答具体的投资问题
    - **可视化优先**：用图表让复杂数据关系一目了然
    - **可重现性**：确保分析步骤可以被他人重复执行
    - **性能意识**：选择高效的数据处理方法
    - **增量分析**：基于现有分析结果进行渐进式深入
  </guideline>

  <process>
    ## lude项目数据分析标准流程
    
    ### Step 1: 环境准备和数据加载
    
    ```mermaid
    flowchart TD
        A[激活conda环境] --> B[导入必要包]
        B --> C[获取项目路径]
        C --> D[加载数据文件]
        D --> E[初步数据检查]
        
        A1["source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude"]
        B1["import pandas as pd<br/>import numpy as np<br/>from lude.config.paths import get_path_info"]
        C1["paths = get_path_info()"]
        D1["df = pd.read_parquet(paths['data'] / 'cb_data.pq')"]
        E1["print(df.info())<br/>print(df.describe())"]
        
        A -.-> A1
        B -.-> B1  
        C -.-> C1
        D -.-> D1
        E -.-> E1
    ```
    
    ### Step 2: 探索性数据分析
    
    ```mermaid
    flowchart LR
        A[单变量分析] --> B[缺失值分析]
        B --> C[分布形态分析]
        C --> D[异常值检测]
        D --> E[基础统计概述]
        
        subgraph 可视化工具
            F[histogram plots]
            G[box plots] 
            H[correlation heatmap]
            I[scatter plots]
        end
        
        A --> F
        B --> G
        C --> H
        D --> I
    ```
    
    ### Step 3: 因子分析专项流程
    
    ```mermaid
    graph TD
        A[加载因子映射] --> B[因子分组分析]
        B --> C[因子相关性分析]
        C --> D[因子有效性验证]
        D --> E[因子组合效果评估]
        
        A1["with open('factor_mapping.json') as f:<br/>    factor_map = json.load(f)"]
        B1["价格类、价值类、规模类、技术类<br/>分别进行统计分析"]
        C1["计算因子间相关系数矩阵<br/>识别高相关因子对"]
        D1["单因子IC分析<br/>因子单调性检验"]
        E1["因子组合回测<br/>CAGR性能评估"]
        
        A -.-> A1
        B -.-> B1
        C -.-> C1
        D -.-> D1  
        E -.-> E1
    ```
    
    ### Step 4: 结果可视化和报告
    
    ```mermaid
    flowchart TD
        A[生成核心图表] --> B[撰写分析总结]
        B --> C[提出业务建议]
        C --> D[保存分析结果]
        
        subgraph 标准图表类型
            E[因子分布直方图]
            F[相关性热力图]
            G[时序趋势线图]
            H[收益归因分析图]
        end
        
        A --> E
        A --> F
        A --> G  
        A --> H
    ```
    
    ### 标准执行模板脚本
    
    ```python
    # 1. 环境激活 (在终端执行)
    # source ~/miniconda3/etc/profile.d/conda.sh && conda activate lude
    
    # 2. Python分析脚本
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from lude.config.paths import get_path_info
    
    # 3. 数据加载
    paths = get_path_info()
    cb_data = pd.read_parquet(paths['data'] / 'cb_data.pq')
    
    # 4. 基础分析
    print("=== 数据基础信息 ===")
    print(f"数据形状: {cb_data.shape}")
    print(f"时间范围: {cb_data.index.min()} ~ {cb_data.index.max()}")
    print(f"因子数量: {len([col for col in cb_data.columns if col != 'date'])}")
    
    # 5. 质量检查
    missing_summary = cb_data.isnull().sum().sort_values(ascending=False)
    print("=== 缺失值统计 ===")
    print(missing_summary[missing_summary > 0])
    
    # 6. 保存结果
    results_path = paths['project_root'] / 'analysis_results' 
    results_path.mkdir(exist_ok=True)
    ```
  </process>

  <criteria>
    ## 数据分析质量标准
    
    ### 技术质量指标
    - ✅ 代码在conda lude环境中成功运行
    - ✅ 数据加载和处理无错误
    - ✅ 分析结果可重现
    - ✅ 图表清晰美观、信息丰富
    - ✅ 遵循项目代码规范

    ### 分析深度指标  
    - ✅ 发现了非显而易见的数据模式
    - ✅ 识别了潜在的数据质量问题
    - ✅ 提供了有业务价值的洞察
    - ✅ 量化了关键因子的影响程度
    - ✅ 给出了可执行的建议

    ### 可视化质量指标
    - ✅ 图表类型与数据特征匹配  
    - ✅ 坐标轴标签和图例清晰
    - ✅ 颜色搭配合理易读
    - ✅ 图表传达的信息准确
    - ✅ 复杂关系得到直观展示

    ### 业务价值指标
    - ✅ 分析结果能指导投资决策
    - ✅ 识别了新的投资机会或风险
    - ✅ 为策略优化提供了数据支撑
    - ✅ 验证或推翻了现有假设
    - ✅ 为后续研究指明了方向
  </criteria>
</execution>