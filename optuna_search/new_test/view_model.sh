#!/bin/bash
# view_model.sh - 查看可转债优化模型的脚本
# 作者: Cascade AI
# 日期: 2025-04-20
# 使用方法:
#     列出所有模型
#     ./view_model.sh --list

#     查看模型列表中的第一个模型
#     ./view_model.sh --index 1

#     查看指定模型文件
#     ./view_model.sh --model best_model_multistage_tpe_3factors_20250420_103439.pkl

#     查看详细信息
#     ./view_model.sh --detailed

# 设置工作目录为脚本所在目录
cd "$(dirname "$0")"

# 确定Python解释器路径
# 优先使用conda环境中的Python
if [ -d "$HOME/miniconda3/envs/lude" ]; then
    PYTHON="$HOME/miniconda3/envs/lude/bin/python"
elif [ -n "$CONDA_PREFIX" ]; then
    PYTHON="$CONDA_PREFIX/bin/python"
else
    PYTHON=$(which python)
fi

# 显示使用帮助
function show_help() {
    echo "使用方法: $0 [选项]"
    echo "查看优化后的可转债模型文件"
    echo ""
    echo "选项:"
    echo "  --list              列出所有可用的模型文件"
    echo "  --model 文件名       查看指定的模型文件"
    echo "  --index 数字         根据列表索引查看模型"
    echo "  --detailed          显示详细信息"
    echo "  --depth 数字         查看模型内部结构的深度(默认:3)"
    echo "  --inspect           查看模型的完整内部结构"
    echo "  --help              显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --list                    # 列出所有模型"
    echo "  $0 --model best_model_xxx.pkl  # 查看指定模型"
    echo "  $0 --index 1                 # 查看列表中的第一个模型"
}

# 处理帮助参数
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_help
    exit 0
fi

# 检查joblib包是否安装
$PYTHON -c "import joblib" &>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: 缺少必要的Python包 'joblib'"
    echo "请运行以下命令安装:"
    echo "pip install joblib"
    exit 1
fi

# 执行模型查看脚本
echo "使用Python解释器: $PYTHON"
$PYTHON view_best_model.py "$@"

# 显示操作说明
if [ $? -eq 0 ] && [ "$1" != "--list" ]; then
    echo ""
    echo "提示:"
    echo "  - 使用 '$0 --list' 查看所有可用模型"
    echo "  - 使用 '$0 --detailed' 查看更详细的信息"
fi
