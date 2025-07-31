#!/bin/bash
# 开发模式安装脚本

# 确保在项目根目录下运行
cd "$(dirname "$0")"

# 检测当前环境
echo "当前Python路径: $(which python)"
echo "当前Python版本: $(python --version)"

# 安装项目（开发模式）到当前激活的Python环境
echo "正在安装项目依赖..."
# 首先尝试使用国内镜像源安装
if ! python -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple/ --timeout=300; then
    echo "清华镜像安装失败，尝试阿里云镜像..."
    if ! python -m pip install -e . -i https://mirrors.aliyun.com/pypi/simple/ --timeout=300; then
        echo "镜像安装均失败，尝试默认源（可能较慢）..."
        python -m pip install -e . --timeout=300 --retries=5
    fi
fi

echo "开发模式安装完成。现在可以从当前Python环境导入lude包。"

# 设置项目环境变量
echo ""
echo "正在设置LUDE项目环境变量..."
if [ -f "./set_env.sh" ]; then
    # 使用source命令执行set_env.sh，这样环境变量会在当前shell会话中生效
    if source ./set_env.sh; then
        echo "✅ 环境变量设置成功"
        echo ""
        echo "🎉 项目初始化完成！"
        echo "📋 下一步操作："
        echo "   1. 确保你在正确的conda环境中 (推荐使用'lude'环境)"
        echo "   2. 运行测试: pytest tests/"
        echo "   3. 开始优化: ./run_optimizer.sh --help"
        echo ""
        echo "💡 提示: 环境变量 LUDE_PROJECT_ROOT 已设置为: $LUDE_PROJECT_ROOT"
        echo "   如果需要在新的shell会话中使用，请运行: source set_env.sh"
    else
        echo "⚠️  环境变量设置失败，但不影响项目使用"
        echo "   你可以稍后手动运行: source set_env.sh"
    fi
else
    echo "⚠️  未找到set_env.sh文件，跳过环境变量设置"
    echo "   项目仍可正常使用，但建议检查set_env.sh文件是否存在"
fi

echo ""
echo "安装日志记录完成。"
