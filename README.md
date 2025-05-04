# 可转债多因子优化系统

基于多因子模型的可转债筛选与优化系统，支持因子组合优化、权重优化和排序方向优化。

## 特点

- 数据筛选：根据上市天数、赎回状态、剩余期限、价格区间等条件筛选可转债
- 多因子评分：支持多种因子（价格、溢价率、市盈率等）的组合，每个因子有权重和排序方向
- 贝叶斯优化：使用Optuna库进行贝叶斯优化，寻找最优的因子组合和参数
- 回测框架：计算策略的年化收益率(CAGR)

## 安装

```bash
# 开发模式安装
pip install -e .

或者
# 添加执行权限
chmod +x install_dev.sh

# 运行安装脚本
./install_dev.sh
```

## 使用方法

```python
# 示例代码
from lude.optimization.engine import OptimizationEngine
from lude.strategies.factor_strategies import domain_knowledge_factors

# 配置优化引擎
engine = OptimizationEngine(
    data_path="path/to/data.pq",
    start_date="2020-01-01",
    end_date="2022-12-31",
    hold_num=15
)

# 运行优化
engine.optimize()
```
