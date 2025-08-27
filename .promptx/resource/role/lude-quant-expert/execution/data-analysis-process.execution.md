<execution>
  <constraint>
    ## 数据分析客观约束
    - **计算资源限制**：内存使用不超过16GB，单次计算时间不超过4小时
    - **数据质量要求**：缺失值比例不超过5%，异常值比例不超过1%
    - **统计显著性要求**：假设检验显著性水平设置为α=0.05
    - **样本量限制**：时间序列数据至少包含36个月，截面数据至少1000个样本
    - **实时性约束**：关键指标计算延迟不超过30分钟
  </constraint>

  <rule>
    ## 数据分析强制规则
    - **数据来源验证**：所有数据必须有明确来源和更新机制
    - **预处理标准化**：必须按照统一的预处理流程处理数据
    - **结果可复现性**：所有分析结果必须可复现，设置随机种子
    - **异常值处理**：异常值必须标记和说明，不能直接删除
    - **缺失值处理**：缺失值处理方法必须与数据特性匹配
    - **版本控制**：数据和代码变更必须通过版本控制管理
  </rule>

  <guideline>
    ## 数据分析指导原则
    - **探索优先**：先进行充分的探索性数据分析
    - **假设驱动**：基于明确的业务假设进行分析
    - **多角度验证**：从不同角度验证分析结论
    - **业务导向**：分析结果必须与业务目标紧密结合
    - **可解释性**：复杂模型必须有可解释的业务逻辑
    - **迭代改进**：根据反馈持续改进分析方法
  </guideline>

  <process>
    ## 数据分析标准流程

    ### Phase 1: 数据探索与理解
    ```mermaid
    flowchart TD
        A[数据加载] --> B[数据概览]
        B --> C[数据结构分析]
        C --> D[缺失值分析]
        D --> E[数据分布分析]
        E --> F[相关性分析]
        F --> G[时间序列特征]
        G --> H[业务逻辑验证]
    ```
    
    **数据探索代码模板**：
    ```python
    def comprehensive_data_exploration(df):
        """全面的数据探索分析"""
        
        print("=== 数据基本信息 ===")
        print(f"数据形状: {df.shape}")
        print(f"数据类型分布: {df.dtypes.value_counts()}")
        print(f"内存使用: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        
        print("\n=== 缺失值分析 ===")
        missing_stats = df.isnull().sum()
        missing_pct = (missing_stats / len(df)) * 100
        missing_summary = pd.DataFrame({
            'Missing_Count': missing_stats,
            'Missing_Percentage': missing_pct
        }).sort_values('Missing_Count', ascending=False)
        print(missing_summary[missing_summary['Missing_Count'] > 0])
        
        print("\n=== 数值型变量描述性统计 ===")
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        print(df[numeric_cols].describe())
        
        print("\n=== 分类变量分布 ===")
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols[:5]:  # 显示前5个分类变量
            print(f"\n{col}:")
            print(df[col].value_counts().head(10))
        
        # 检查数据质量问题
        quality_issues = []
        
        # 检查重复行
        duplicate_rows = df.duplicated().sum()
        if duplicate_rows > 0:
            quality_issues.append(f"发现 {duplicate_rows} 行重复数据")
        
        # 检查异常值（数值型变量）
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            outliers = ((df[col] < Q1 - 1.5*IQR) | (df[col] > Q3 + 1.5*IQR)).sum()
            if outliers > len(df) * 0.01:  # 异常值超过1%
                quality_issues.append(f"{col}: {outliers} 个异常值 ({outliers/len(df)*100:.1f}%)")
        
        if quality_issues:
            print("\n=== 数据质量问题 ===")
            for issue in quality_issues:
                print(f"⚠️  {issue}")
        
        return {
            'shape': df.shape,
            'missing_summary': missing_summary,
            'numeric_summary': df[numeric_cols].describe(),
            'quality_issues': quality_issues
        }
    ```
    
    ### Phase 2: 数据预处理与清洗
    ```mermaid
    graph LR
        A[原始数据] --> B[缺失值处理]
        B --> C[异常值处理]
        C --> D[数据类型转换]
        D --> E[特征工程]
        E --> F[数据标准化]
        F --> G[数据验证]
    ```
    
    **数据预处理管道**：
    ```python
    from sklearn.preprocessing import StandardScaler, RobustScaler
    from sklearn.impute import SimpleImputer, KNNImputer
    
    class DataPreprocessingPipeline:
        def __init__(self, config):
            self.config = config
            self.scalers = {}
            self.imputers = {}
            
        def handle_missing_values(self, df, strategy='median'):
            """处理缺失值"""
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            categorical_cols = df.select_dtypes(include=['object']).columns
            
            # 数值型变量缺失值处理
            if len(numeric_cols) > 0:
                if strategy == 'knn':
                    imputer = KNNImputer(n_neighbors=5)
                else:
                    imputer = SimpleImputer(strategy=strategy)
                
                df_numeric = pd.DataFrame(
                    imputer.fit_transform(df[numeric_cols]),
                    columns=numeric_cols,
                    index=df.index
                )
                self.imputers['numeric'] = imputer
            
            # 分类变量缺失值处理
            if len(categorical_cols) > 0:
                imputer = SimpleImputer(strategy='most_frequent')
                df_categorical = pd.DataFrame(
                    imputer.fit_transform(df[categorical_cols]),
                    columns=categorical_cols,
                    index=df.index
                )
                self.imputers['categorical'] = imputer
            
            # 合并处理后的数据
            result_df = df.copy()
            if len(numeric_cols) > 0:
                result_df[numeric_cols] = df_numeric
            if len(categorical_cols) > 0:
                result_df[categorical_cols] = df_categorical
                
            return result_df
        
        def handle_outliers(self, df, method='iqr', factor=1.5):
            """处理异常值"""
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            result_df = df.copy()
            
            outlier_info = {}
            
            for col in numeric_cols:
                if method == 'iqr':
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - factor * IQR
                    upper_bound = Q3 + factor * IQR
                    
                elif method == 'zscore':
                    mean = df[col].mean()
                    std = df[col].std()
                    lower_bound = mean - factor * std
                    upper_bound = mean + factor * std
                
                # 标记异常值而不直接删除
                outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
                outlier_count = outliers.sum()
                
                if outlier_count > 0:
                    outlier_info[col] = {
                        'count': outlier_count,
                        'percentage': outlier_count / len(df) * 100,
                        'lower_bound': lower_bound,
                        'upper_bound': upper_bound
                    }
                    
                    # 将异常值设为边界值（Winsorization）
                    result_df[col] = df[col].clip(lower_bound, upper_bound)
            
            return result_df, outlier_info
        
        def feature_engineering(self, df):
            """特征工程"""
            result_df = df.copy()
            
            # 可转债特定的特征工程
            if 'CB_PRICE' in df.columns and 'STOCK_PRICE' in df.columns:
                # 计算转股价值
                if 'CONVERSION_RATIO' in df.columns:
                    result_df['conversion_value'] = (df['STOCK_PRICE'] * 
                                                   df['CONVERSION_RATIO'])
                    
                # 计算转股溢价率
                if 'conversion_value' in result_df.columns:
                    result_df['conversion_premium'] = (
                        (df['CB_PRICE'] - result_df['conversion_value']) / 
                        result_df['conversion_value']
                    )
            
            # 时间相关特征
            if df.index.name == 'trade_date' or 'trade_date' in df.columns:
                date_col = df.index if df.index.name == 'trade_date' else df['trade_date']
                result_df['year'] = date_col.year
                result_df['month'] = date_col.month
                result_df['quarter'] = date_col.quarter
                result_df['weekday'] = date_col.weekday
            
            # 滞后特征
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in ['CB_PRICE', 'VOLUME', 'TURNOVER_RATE']:
                if col in numeric_cols:
                    result_df[f'{col}_lag1'] = df.groupby(level=1)[col].shift(1)
                    result_df[f'{col}_lag5'] = df.groupby(level=1)[col].shift(5)
                    
                    # 移动平均
                    result_df[f'{col}_ma5'] = (df.groupby(level=1)[col]
                                             .rolling(5).mean().reset_index(0, drop=True))
                    result_df[f'{col}_ma20'] = (df.groupby(level=1)[col]
                                              .rolling(20).mean().reset_index(0, drop=True))
            
            return result_df
        
        def normalize_data(self, df, method='standard'):
            """数据标准化"""
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            result_df = df.copy()
            
            if method == 'standard':
                scaler = StandardScaler()
            elif method == 'robust':
                scaler = RobustScaler()
            else:
                raise ValueError(f"Unsupported normalization method: {method}")
            
            # 对数值型列进行标准化
            scaled_data = scaler.fit_transform(df[numeric_cols])
            result_df[numeric_cols] = scaled_data
            
            self.scalers[method] = scaler
            
            return result_df
    ```
    
    ### Phase 3: 探索性数据分析(EDA)
    ```mermaid
    flowchart TD
        A[单变量分析] --> B[双变量分析]
        B --> C[多变量分析]
        C --> D[时间序列分析]
        D --> E[分组分析]
        E --> F[相关性分析]
        F --> G[假设检验]
    ```
    
    **EDA可视化工具**：
    ```python
    import matplotlib.pyplot as plt
    import seaborn as sns
    from scipy import stats
    
    class EDAVisualizer:
        def __init__(self, figsize=(12, 8)):
            self.figsize = figsize
            plt.style.use('seaborn-v0_8')
            
        def plot_distribution_analysis(self, df, columns, n_cols=3):
            """分布分析可视化"""
            n_plots = len(columns)
            n_rows = (n_plots - 1) // n_cols + 1
            
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*4, n_rows*3))
            axes = axes.flatten() if n_plots > 1 else [axes]
            
            for i, col in enumerate(columns):
                if i < len(axes):
                    # 直方图 + 密度曲线
                    axes[i].hist(df[col].dropna(), bins=50, density=True, 
                               alpha=0.7, color='skyblue', edgecolor='black')
                    
                    # 添加正态分布拟合
                    mu, sigma = stats.norm.fit(df[col].dropna())
                    x = np.linspace(df[col].min(), df[col].max(), 100)
                    axes[i].plot(x, stats.norm.pdf(x, mu, sigma), 'r-', 
                               label=f'Normal fit (μ={mu:.2f}, σ={sigma:.2f})')
                    
                    axes[i].set_title(f'{col} Distribution')
                    axes[i].set_xlabel(col)
                    axes[i].set_ylabel('Density')
                    axes[i].legend()
            
            # 隐藏多余的子图
            for i in range(n_plots, len(axes)):
                axes[i].set_visible(False)
                
            plt.tight_layout()
            plt.show()
        
        def plot_correlation_heatmap(self, df, method='pearson'):
            """相关性热力图"""
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            corr_matrix = df[numeric_cols].corr(method=method)
            
            plt.figure(figsize=self.figsize)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
            
            sns.heatmap(corr_matrix, mask=mask, annot=True, cmap='RdYlBu_r',
                       center=0, square=True, linewidths=0.5, 
                       cbar_kws={"shrink": 0.5})
            plt.title(f'Correlation Matrix ({method.capitalize()})')
            plt.tight_layout()
            plt.show()
            
            return corr_matrix
        
        def plot_time_series_analysis(self, df, columns, date_col='trade_date'):
            """时间序列分析"""
            if date_col in df.columns:
                df_ts = df.set_index(date_col)
            else:
                df_ts = df
            
            n_cols = 2
            n_rows = (len(columns) - 1) // n_cols + 1
            
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, n_rows*4))
            axes = axes.flatten() if len(columns) > 1 else [axes]
            
            for i, col in enumerate(columns):
                if col in df_ts.columns and i < len(axes):
                    # 时间序列图
                    axes[i].plot(df_ts.index, df_ts[col], linewidth=1)
                    axes[i].set_title(f'{col} Time Series')
                    axes[i].set_xlabel('Date')
                    axes[i].set_ylabel(col)
                    axes[i].grid(True, alpha=0.3)
                    
                    # 添加趋势线
                    z = np.polyfit(range(len(df_ts)), df_ts[col].fillna(0), 1)
                    p = np.poly1d(z)
                    axes[i].plot(df_ts.index, p(range(len(df_ts))), 
                               "r--", alpha=0.8, label='Trend')
                    axes[i].legend()
            
            plt.tight_layout()
            plt.show()
        
        def plot_factor_analysis(self, df, factor_col, return_col, bins=10):
            """因子分析图"""
            # 计算分位数分组
            df_analysis = df[[factor_col, return_col]].dropna()
            df_analysis['factor_quantile'] = pd.qcut(df_analysis[factor_col], 
                                                   bins, labels=False) + 1
            
            # 计算各分位数组的统计指标
            quantile_stats = df_analysis.groupby('factor_quantile')[return_col].agg([
                'mean', 'std', 'count'
            ]).round(4)
            
            # 可视化
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            
            # 分位数收益率
            axes[0].bar(quantile_stats.index, quantile_stats['mean'])
            axes[0].set_title(f'{factor_col} Quantile Returns')
            axes[0].set_xlabel('Quantile')
            axes[0].set_ylabel('Mean Return')
            
            # 散点图
            axes[1].scatter(df_analysis[factor_col], df_analysis[return_col], 
                          alpha=0.5)
            z = np.polyfit(df_analysis[factor_col], df_analysis[return_col], 1)
            p = np.poly1d(z)
            axes[1].plot(df_analysis[factor_col], 
                        p(df_analysis[factor_col]), "r--", alpha=0.8)
            axes[1].set_title(f'{factor_col} vs {return_col}')
            axes[1].set_xlabel(factor_col)
            axes[1].set_ylabel(return_col)
            
            # 相关系数随时间变化
            if 'trade_date' in df.columns:
                rolling_corr = df.set_index('trade_date')[[factor_col, return_col]].rolling(60).corr().iloc[0::2, -1]
                axes[2].plot(rolling_corr.index, rolling_corr.values)
                axes[2].set_title('Rolling Correlation (60D)')
                axes[2].set_xlabel('Date')
                axes[2].set_ylabel('Correlation')
                axes[2].axhline(y=0, color='black', linestyle='--', alpha=0.5)
            
            plt.tight_layout()
            plt.show()
            
            # 计算IC和IR
            ic = df_analysis[factor_col].corr(df_analysis[return_col])
            print(f"\n{factor_col} 因子分析结果:")
            print(f"IC (Information Coefficient): {ic:.4f}")
            print(f"IC绝对值: {abs(ic):.4f}")
            
            return quantile_stats, ic
    ```
    
    ### Phase 4: 统计分析与假设检验
    ```python
    def statistical_tests_suite(df, factor_cols, return_col):
        """统计检验套件"""
        
        results = {}
        
        for factor in factor_cols:
            factor_data = df[[factor, return_col]].dropna()
            
            # 正态性检验
            shapiro_stat, shapiro_p = stats.shapiro(
                factor_data[factor].sample(min(5000, len(factor_data)))
            )
            
            # 平稳性检验 (ADF Test)
            from statsmodels.tsa.stattools import adfuller
            adf_result = adfuller(factor_data[factor].dropna())
            
            # 因子有效性检验
            ic = factor_data[factor].corr(factor_data[return_col])
            
            # 分组收益率差异检验
            high_group = factor_data[factor_data[factor] > factor_data[factor].quantile(0.8)]
            low_group = factor_data[factor_data[factor] < factor_data[factor].quantile(0.2)]
            
            ttest_stat, ttest_p = stats.ttest_ind(
                high_group[return_col], low_group[return_col]
            )
            
            results[factor] = {
                'normality_test': {
                    'shapiro_stat': shapiro_stat,
                    'shapiro_p': shapiro_p,
                    'is_normal': shapiro_p > 0.05
                },
                'stationarity_test': {
                    'adf_stat': adf_result[0],
                    'adf_p': adf_result[1],
                    'is_stationary': adf_result[1] < 0.05
                },
                'factor_effectiveness': {
                    'ic': ic,
                    'ic_abs': abs(ic),
                    'is_significant': abs(ic) > 0.02
                },
                'group_difference_test': {
                    'ttest_stat': ttest_stat,
                    'ttest_p': ttest_p,
                    'significant_difference': ttest_p < 0.05
                }
            }
        
        return results
    ```

  </process>

  <criteria>
    ## 数据分析质量标准

    ### 数据质量标准
    - ✅ 缺失值比例 < 5%
    - ✅ 异常值处理合理性验证
    - ✅ 数据一致性检查通过
    - ✅ 时间序列连续性 > 95%
    
    ### 统计分析标准
    - ✅ 因子IC绝对值 > 0.02
    - ✅ 因子显著性检验 p < 0.05
    - ✅ 模型解释度 R² > 0.1
    - ✅ 残差正态性检验通过
    
    ### 可视化标准
    - ✅ 图表标题和标签完整
    - ✅ 图例和说明清晰
    - ✅ 颜色搭配专业美观
    - ✅ 图表逻辑关系明确
    
    ### 报告质量标准
    - ✅ 分析逻辑清晰完整
    - ✅ 结论有数据支撑
    - ✅ 风险点充分识别
    - ✅ 业务建议具体可操作

  </criteria>
</execution>