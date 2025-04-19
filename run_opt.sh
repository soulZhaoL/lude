#!/usr/bin/env bash
set -euo pipefail
# chmod +x ~/batch_init_env.sh ~/run_opt.sh
# /root/run_opt.sh --hold 5 --factors 3 --num 1 --mode continuous --iterations 5
#
#
#

# ----------------------------------
#  usage 函数
usage() {
  echo "用法: $0 [options]"
  echo "示例: $0 --hold 5 --factors 3 --num 1 --mode continuous --iterations 5"
  echo ""
  echo "必选参数:"
  echo "  --hold, -h NUM      - 持仓数量"
  echo "  --factors, -f NUM   - 因子数量"
  echo "  --num, -n NUM       - 序号"
  echo ""
  echo "可选参数:"
  echo "  --mode, -m MODE     - 优化模式: single 或 continuous (默认: continuous)"
  echo "  --iterations, -i NUM - 迭代次数 (默认: 10)"
  echo "  --help              - 显示此帮助信息"
  exit 1
}

# 默认参数值
HOLD=""
FAC=""
NUM=""
MODE="continuous"
ITERATIONS="10"

# 如果没有参数，显示使用方法
if [ $# -eq 0 ]; then
  usage
fi

# 处理所有参数
while [ $# -gt 0 ]; do
  case "$1" in
    --hold|-h)
      HOLD="$2"
      shift 2
      ;;
    --factors|-f)
      FAC="$2"
      shift 2
      ;;
    --num|-n)
      NUM="$2"
      shift 2
      ;;
    --mode|-m)
      MODE="$2"
      shift 2
      ;;
    --iterations|-i)
      ITERATIONS="$2"
      shift 2
      ;;
    --help)
      usage
      ;;
    *)
      echo "错误: 未知参数 $1"
      usage
      ;;
  esac
done

# 检查必选参数
if [ -z "$HOLD" ] || [ -z "$FAC" ] || [ -z "$NUM" ]; then
  echo "错误: 缺少必选参数"
  usage
fi

# 验证模式参数
if [ "$MODE" != "single" ] && [ "$MODE" != "continuous" ]; then
  echo "错误: 模式必须是 'single' 或 'continuous'"
  exit 1
fi

# 验证数值参数
for param in "$HOLD" "$FAC" "$NUM" "$ITERATIONS"; do
  if ! [[ "$param" =~ ^[0-9]+$ ]]; then
    echo "错误: 参数 '$param' 必须是正整数"
    exit 1
  fi
done

# 根目录，请根据你的实际路径调整
BASE_DIR="/root/autodl-tmp"
TARGET_DIR="${BASE_DIR}/lude_100_150_hold${HOLD}_fac${FAC}_num${NUM}/lude/optuna_search/new_test"

# 检查目录是否存在
if [ ! -d "${TARGET_DIR}" ]; then
  echo "❌ 目标目录不存在：${TARGET_DIR}"
  exit 1
fi

# 进入工作目录
echo "进入工作目录：${TARGET_DIR}"
cd "${TARGET_DIR}"

echo "开始执行优化... (持仓: ${HOLD}, 因子: ${FAC}, 序号: ${NUM}, 模式: ${MODE}, 迭代次数: ${ITERATIONS})"
# 执行优化脚本
./run_optimizer.sh \
  -m ${MODE} \
  --method tpe \
  --strategy multistage \
  --start 20220729 \
  --end 20250328 \
  --min 100 \
  --max 150 \
  --jobs 15 \
  --trials 3000 \
  --hold ${HOLD} \
  --seed-start 42 \
  --seed-step 1000 \
  --iterations ${ITERATIONS} \
  --factors ${FAC}

echo "✅ 完成：hold=${HOLD} fac=${FAC} num=${NUM}"