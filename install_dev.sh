#!/bin/bash
# 开发模式安装脚本

# 确保在项目根目录下运行
cd "$(dirname "$0")"

# 检测当前环境
echo "当前Python路径: $(which python)"
echo "当前Python版本: $(python --version)"

# 安装项目（开发模式）到当前激活的Python环境
python -m pip install -e .

echo "开发模式安装完成。现在可以从当前Python环境导入lude包。"
