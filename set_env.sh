#!/bin/bash
# 设置 LUDE 项目环境变量
# 使用方法：source set_env.sh

# 获取脚本所在目录作为项目根目录
export LUDE_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "LUDE 项目环境变量已设置:"
echo "LUDE_PROJECT_ROOT = $LUDE_PROJECT_ROOT"

# 可选：添加到 PATH
# export PATH="$LUDE_PROJECT_ROOT/scripts:$PATH"

# 验证路径配置
if command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "验证路径配置..."
    python3 -c "
import sys
sys.path.append('$LUDE_PROJECT_ROOT/src')
try:
    from lude.config.paths import PROJECT_ROOT, validate_project_paths
    print(f'✅ 项目根目录: {PROJECT_ROOT}')
    issues = validate_project_paths()
    if not issues:
        print('✅ 所有路径配置正确')
    else:
        print('⚠️  发现问题:')
        for issue in issues:
            print(f'   - {issue}')
except Exception as e:
    print(f'❌ 路径配置验证失败: {e}')
"
fi