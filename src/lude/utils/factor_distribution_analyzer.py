import os
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from scipy import stats
from lude.config.paths import DATA_DIR

class FactorDistributionAnalyzer:
    """
    因子数值分布分析工具类
    
    用于分析可转债因子的数值分布特征，包括统计指标、分布图形等
    """
    
    def __init__(self, data_path: Optional[str] = None):
        """
        初始化分析器
        
        Args:
            data_path: 数据文件路径，默认使用cb_data.pq
        """
        if data_path is None:
            self.data_path = os.path.join(DATA_DIR, 'cb_data.pq')
        else:
            self.data_path = data_path
        
        self.df = None
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        try:
            self.df = pd.read_parquet(self.data_path)
            print(f"数据加载成功: {self.df.shape[0]}行, {self.df.shape[1]}列")
        except Exception as e:
            print(f"数据加载失败: {e}")
            raise
    
    def get_basic_stats(self, factor_name: str) -> Dict[str, Any]:
        """
        获取因子的基础统计信息
        
        Args:
            factor_name: 因子名称
            
        Returns:
            包含统计信息的字典
        """
        if factor_name not in self.df.columns:
            raise ValueError(f"因子 '{factor_name}' 不存在于数据中")
        
        series = self.df[factor_name].dropna()
        
        if len(series) == 0:
            return {"error": "该因子无有效数据"}
        
        stats_dict = {
            "数据总数": len(self.df[factor_name]),
            "有效数据": len(series),
            "缺失数据": len(self.df[factor_name]) - len(series),
            "缺失率": (len(self.df[factor_name]) - len(series)) / len(self.df[factor_name]) * 100,
            "均值": series.mean(),
            "中位数": series.median(),
            "标准差": series.std(),
            "方差": series.var(),
            "偏度": series.skew(),
            "峰度": series.kurtosis(),
            "最小值": series.min(),
            "最大值": series.max(),
            "极差": series.max() - series.min(),
            "25%分位数": series.quantile(0.25),
            "75%分位数": series.quantile(0.75),
            "四分位距": series.quantile(0.75) - series.quantile(0.25),
            "变异系数": series.std() / series.mean() if series.mean() != 0 else np.inf
        }
        
        # 添加正态性检验
        if len(series) >= 3:
            try:
                shapiro_stat, shapiro_p = stats.shapiro(series.sample(min(5000, len(series))))
                stats_dict["Shapiro正态性检验统计量"] = shapiro_stat
                stats_dict["Shapiro正态性检验p值"] = shapiro_p
                stats_dict["是否正态分布"] = shapiro_p > 0.05
            except:
                stats_dict["正态性检验"] = "无法执行"
        
        return stats_dict
    
    def print_basic_stats(self, factor_name: str):
        """
        打印因子的基础统计信息
        
        Args:
            factor_name: 因子名称
        """
        stats = self.get_basic_stats(factor_name)
        
        if "error" in stats:
            print(f"错误: {stats['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"因子 '{factor_name}' 的分布统计信息")
        print(f"{'='*60}")
        
        print(f"\n【数据概况】")
        print(f"  数据总数: {stats['数据总数']:,}")
        print(f"  有效数据: {stats['有效数据']:,}")
        print(f"  缺失数据: {stats['缺失数据']:,}")
        print(f"  缺失率: {stats['缺失率']:.2f}%")
        
        print(f"\n【中心趋势】")
        print(f"  均值: {stats['均值']:.6f}")
        print(f"  中位数: {stats['中位数']:.6f}")
        
        print(f"\n【离散程度】")
        print(f"  标准差: {stats['标准差']:.6f}")
        print(f"  方差: {stats['方差']:.6f}")
        print(f"  变异系数: {stats['变异系数']:.6f}")
        print(f"  极差: {stats['极差']:.6f}")
        print(f"  四分位距: {stats['四分位距']:.6f}")
        
        print(f"\n【分布形状】")
        print(f"  偏度: {stats['偏度']:.6f}")
        print(f"  峰度: {stats['峰度']:.6f}")
        
        print(f"\n【极值信息】")
        print(f"  最小值: {stats['最小值']:.6f}")
        print(f"  最大值: {stats['最大值']:.6f}")
        print(f"  25%分位数: {stats['25%分位数']:.6f}")
        print(f"  75%分位数: {stats['75%分位数']:.6f}")
        
        if "Shapiro正态性检验p值" in stats:
            print(f"\n【正态性检验】")
            print(f"  Shapiro统计量: {stats['Shapiro正态性检验统计量']:.6f}")
            print(f"  p值: {stats['Shapiro正态性检验p值']:.6f}")
            print(f"  是否正态分布: {'是' if stats['是否正态分布'] else '否'}")
    
    def get_distribution_values(self, factor_name: str, sample_mode: str = 'percentile') -> Dict[str, Any]:
        """
        获取因子的分布数值
        
        Args:
            factor_name: 因子名称
            sample_mode: 采样模式，'percentile' 为分位数模式，'head_tail' 为头尾模式
            
        Returns:
            包含分布数值的字典
        """
        if factor_name not in self.df.columns:
            raise ValueError(f"因子 '{factor_name}' 不存在于数据中")
        
        series = self.df[factor_name].dropna()
        
        if len(series) == 0:
            return {"error": "该因子无有效数据"}
        
        if sample_mode == 'percentile':
            # 按分位数采样
            percentiles = [0, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
            result = {}
            
            for p in percentiles:
                result[f"{p}%分位数"] = series.quantile(p/100)
            
            return result
            
        elif sample_mode == 'head_tail':
            # 头部/尾部 + 分位数模式
            sorted_series = series.sort_values()
            result = {}
            
            # 头部数据 (前10个)
            head_count = min(10, len(sorted_series))
            for i in range(head_count):
                result[f"头部第{i+1}小"] = sorted_series.iloc[i]
            
            # 尾部数据 (后10个)
            tail_count = min(10, len(sorted_series))
            for i in range(tail_count):
                result[f"尾部第{i+1}大"] = sorted_series.iloc[-(i+1)]
            
            # 分位数
            percentiles = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]
            for p in percentiles:
                result[f"{p}%分位数"] = series.quantile(p/100)
            
            return result
        
        else:
            raise ValueError("sample_mode参数必须是 'percentile' 或 'head_tail'")
    
    def print_distribution_values(self, factor_name: str, sample_mode: str = 'percentile'):
        """
        打印因子的分布数值
        
        Args:
            factor_name: 因子名称
            sample_mode: 采样模式
        """
        values = self.get_distribution_values(factor_name, sample_mode)
        
        if "error" in values:
            print(f"错误: {values['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"因子 '{factor_name}' 的分布数值")
        print(f"{'='*60}")
        
        if sample_mode == 'head_tail':
            # 先打印头部数据
            print(f"\n【头部数据 (最小值)】")
            for key, value in values.items():
                if "头部" in key:
                    print(f"  {key}: {value:.6f}")
            
            # 再打印尾部数据
            print(f"\n【尾部数据 (最大值)】")
            for key, value in values.items():
                if "尾部" in key:
                    print(f"  {key}: {value:.6f}")
        
        # 打印分位数
        print(f"\n【分位数分布】")
        for key, value in values.items():
            if "分位数" in key:
                print(f"  {key}: {value:.6f}")
    
    def get_percentile_analysis(self, factor_name: str, percentiles: List[float] = None) -> Dict[str, float]:
        """
        获取因子的分位数分析
        
        Args:
            factor_name: 因子名称
            percentiles: 分位数列表，默认为[1, 5, 10, 25, 50, 75, 90, 95, 99]
            
        Returns:
            分位数字典
        """
        if percentiles is None:
            percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        
        if factor_name not in self.df.columns:
            raise ValueError(f"因子 '{factor_name}' 不存在于数据中")
        
        series = self.df[factor_name].dropna()
        
        if len(series) == 0:
            return {"error": "该因子无有效数据"}
        
        percentile_dict = {}
        for p in percentiles:
            percentile_dict[f"{p}%分位数"] = series.quantile(p/100)
        
        return percentile_dict
    
    def print_percentile_analysis(self, factor_name: str, percentiles: List[float] = None):
        """
        打印因子的分位数分析
        
        Args:
            factor_name: 因子名称
            percentiles: 分位数列表
        """
        percentile_dict = self.get_percentile_analysis(factor_name, percentiles)
        
        if "error" in percentile_dict:
            print(f"错误: {percentile_dict['error']}")
            return
        
        print(f"\n【分位数分析】")
        for key, value in percentile_dict.items():
            print(f"  {key}: {value:.6f}")
    
    def detect_outliers(self, factor_name: str, method: str = 'iqr') -> Dict[str, Any]:
        """
        检测异常值
        
        Args:
            factor_name: 因子名称
            method: 检测方法，'iqr' 或 'zscore'
            
        Returns:
            异常值分析结果
        """
        if factor_name not in self.df.columns:
            raise ValueError(f"因子 '{factor_name}' 不存在于数据中")
        
        series = self.df[factor_name].dropna()
        
        if len(series) == 0:
            return {"error": "该因子无有效数据"}
        
        if method == 'iqr':
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = series[(series < lower_bound) | (series > upper_bound)]
            
            return {
                "方法": "IQR方法",
                "下界": lower_bound,
                "上界": upper_bound,
                "异常值数量": len(outliers),
                "异常值比例": len(outliers) / len(series) * 100,
                "异常值": outliers.tolist() if len(outliers) <= 20 else "异常值过多，仅显示统计信息"
            }
        
        elif method == 'zscore':
            z_scores = np.abs(stats.zscore(series))
            threshold = 3
            outliers = series[z_scores > threshold]
            
            return {
                "方法": "Z-Score方法",
                "阈值": threshold,
                "异常值数量": len(outliers),
                "异常值比例": len(outliers) / len(series) * 100,
                "异常值": outliers.tolist() if len(outliers) <= 20 else "异常值过多，仅显示统计信息"
            }
        
        else:
            raise ValueError("method参数必须是 'iqr' 或 'zscore'")
    
    def print_outlier_analysis(self, factor_name: str, method: str = 'iqr'):
        """
        打印异常值分析
        
        Args:
            factor_name: 因子名称
            method: 检测方法
        """
        outlier_info = self.detect_outliers(factor_name, method)
        
        if "error" in outlier_info:
            print(f"错误: {outlier_info['error']}")
            return
        
        print(f"\n【异常值检测 - {outlier_info['方法']}】")
        
        if method == 'iqr':
            print(f"  下界: {outlier_info['下界']:.6f}")
            print(f"  上界: {outlier_info['上界']:.6f}")
        else:
            print(f"  Z-Score阈值: {outlier_info['阈值']}")
        
        print(f"  异常值数量: {outlier_info['异常值数量']}")
        print(f"  异常值比例: {outlier_info['异常值比例']:.2f}%")
        
        if isinstance(outlier_info['异常值'], list) and len(outlier_info['异常值']) > 0:
            print(f"  异常值样本: {outlier_info['异常值'][:10]}")  # 只显示前10个
    
    def comprehensive_analysis(self, factor_name: str, include_head_tail: bool = False):
        """
        综合分析某个因子
        
        Args:
            factor_name: 因子名称
            include_head_tail: 是否包含头尾数据
        """
        print(f"\n🔍 开始对因子 '{factor_name}' 进行综合分析...")
        
        # 基础统计信息
        self.print_basic_stats(factor_name)
        
        # 分布数值分析
        if include_head_tail:
            self.print_distribution_values(factor_name, 'head_tail')
        else:
            self.print_distribution_values(factor_name, 'percentile')
        
        # 异常值检测 (IQR方法)
        self.print_outlier_analysis(factor_name, 'iqr')
        
        print(f"\n✅ 因子 '{factor_name}' 分析完成!")
    
    def batch_analysis(self, factor_names: List[str], include_head_tail: bool = False):
        """
        批量分析多个因子
        
        Args:
            factor_names: 因子名称列表
            include_head_tail: 是否包含头尾数据
        """
        print(f"\n🚀 开始批量分析 {len(factor_names)} 个因子...")
        
        for i, factor_name in enumerate(factor_names, 1):
            print(f"\n{'='*80}")
            print(f"正在分析第 {i}/{len(factor_names)} 个因子: {factor_name}")
            print(f"{'='*80}")
            
            try:
                self.comprehensive_analysis(factor_name, include_head_tail=include_head_tail)
            except Exception as e:
                print(f"❌ 分析因子 '{factor_name}' 时出错: {e}")
                continue
        
        print(f"\n🎉 批量分析完成!")


if __name__ == "__main__":
    # 创建分析器实例
    analyzer = FactorDistributionAnalyzer()
    
    # 设置要分析的因子名称
    # 可以根据需要修改这里的因子名称
    target_factors = [
        'theory_bias',          
        # 'amount',          # 金额相关
        # 'conv_prem',       # 转换溢价率
        # 'bias_5',          # 5日偏差
        # 'price_ratio',   # 价格比率 (如果存在的话)
        # 'volume_ratio',  # 成交量比率 (如果存在的话)
    ]
    
    print("📊 因子数值分布分析工具")
    print("=" * 50)
    
    # 单个因子详细分析示例
    if target_factors:
        print(f"\n🎯 对因子 '{target_factors[0]}' 进行分位数分析:")
        analyzer.print_distribution_values(target_factors[0], 'percentile')
        
        # print(f"\n🎯 对因子 '{target_factors[0]}' 进行头尾+分位数分析:")
        # analyzer.print_distribution_values(target_factors[0], 'head_tail')
    
    # 批量分析示例 (注释掉，需要时可取消注释)
    # print(f"\n📈 批量分析所有目标因子:")
    # analyzer.batch_analysis(target_factors)
    
    # 可用因子列表 (方便参考)
    # print(f"\n📋 数据中的所有因子列表 (共{len(analyzer.df.columns)}个):")
    # for i, col in enumerate(analyzer.df.columns):
    #     if i % 5 == 0:
    #         print()
    #     print(f"{col:20}", end="")
    print("\n")
    
    print("\n💡 使用提示:")
    print("1. 修改 target_factors 列表来分析不同的因子")
    print("2. 使用 analyzer.print_distribution_values('因子名', 'percentile') 查看分位数")
    print("3. 使用 analyzer.print_distribution_values('因子名', 'head_tail') 查看头尾+分位数")
    print("4. 取消注释批量分析代码来分析多个因子")