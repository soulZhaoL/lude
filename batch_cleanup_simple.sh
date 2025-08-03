#!/bin/bash

# 简单批量清理脚本
# 作者: Cascade
# 日期: 2025-08-03
# 用途: 删除所有项目环境中的logs文件夹和high_performance_factors.json文件

# 默认路径
BASE_DIR="/root/autodl-tmp"
DRY_RUN=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --base-dir)
            BASE_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [--base-dir PATH] [--dry-run]"
            echo "  --base-dir PATH  基础目录 (默认: $BASE_DIR)"
            echo "  --dry-run        预览模式，不实际删除"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo "🧹 批量清理日志和性能文件"
echo "基础目录: $BASE_DIR"

if [ ! -d "$BASE_DIR" ]; then
    echo "❌ 目录不存在: $BASE_DIR"
    exit 1
fi

# 查找所有 lude 项目目录
lude_dirs=$(find "$BASE_DIR" -name "lude_*" -type d 2>/dev/null)

if [ -z "$lude_dirs" ]; then
    echo "❌ 未找到任何 lude_* 目录"
    exit 1
fi

echo "找到项目环境："
echo "$lude_dirs" | while read dir; do
    echo "  📂 $(basename "$dir")"
done

echo ""

if [ "$DRY_RUN" = false ]; then
    read -p "确认清理? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo "开始清理..."

# 清理 logs 文件夹
echo "🗑️  清理 logs 文件夹..."
if [ "$DRY_RUN" = true ]; then
    find "$BASE_DIR" -path "*/lude_*/lude/logs" -type d | head -10 | while read dir; do
        echo "  [预览] 将删除: $dir"
    done
    total_logs=$(find "$BASE_DIR" -path "*/lude_*/lude/logs" -type d | wc -l)
    echo "  [预览] 总共找到 $total_logs 个 logs 目录"
else
    find "$BASE_DIR" -path "*/lude_*/lude/logs" -type d -exec rm -rf {} + 2>/dev/null
    echo "  ✅ logs 文件夹清理完成"
fi

# 清理 high_performance_factors.json
echo "🗑️  清理 high_performance_factors.json..."
if [ "$DRY_RUN" = true ]; then
    find "$BASE_DIR" -path "*/lude_*/lude/high_performance_factors.json" -type f | head -10 | while read file; do
        echo "  [预览] 将删除: $file"
    done
    total_json=$(find "$BASE_DIR" -path "*/lude_*/lude/high_performance_factors.json" -type f | wc -l)
    echo "  [预览] 总共找到 $total_json 个 json 文件"
else
    find "$BASE_DIR" -path "*/lude_*/lude/high_performance_factors.json" -type f -delete 2>/dev/null
    echo "  ✅ high_performance_factors.json 清理完成"
fi

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "📋 预览完成！使用 '$0' 执行实际清理"
else
    echo ""
    echo "✅ 清理完成！"
fi