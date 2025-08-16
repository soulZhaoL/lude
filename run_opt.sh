#!/usr/bin/env bash
set -euo pipefail
# chmod +x ~/*.sh
# /root/run_opt.sh --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 3 --num 1 
# /root/run_opt.sh --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 3 --num 1 --clear

# ----------------------------------
#  usage 函数
usage() {
  echo "用法: $0 [options]"
  echo "示例: $0 --hold 5 --factors 3 --num 1 --mode continuous --iterations 5 --trials 3000"
  echo ""
  echo "必选参数:"
  echo "  --hold, -h NUM      - 持仓数量"
  echo "  --factors, -f NUM   - 因子数量"
  echo "  --num, -n NUM       - 序号"
  echo ""
  echo "可选参数:"
  echo "  --mode, -m MODE     - 优化模式: single 或 continuous (默认: continuous)"
  echo "  --iterations, -i NUM - 迭代次数 (默认: 10)"
  echo "  --trials, -t NUM    - 每次优化的试验次数 (默认: 3000)"
  echo "  --clear             - 清空优化结果目录"
  echo "  --help              - 显示此帮助信息"
  exit 1
}

# 默认参数值
HOLD=""
FAC=""
NUM=""
MODE="continuous"
ITERATIONS="10"
TRIALS="3000"
CLEAR_RESULTS="false"

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
    --trials|-t)
      TRIALS="$2"
      shift 2
      ;;
    --clear)
      CLEAR_RESULTS="true"
      shift
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
for param in "$HOLD" "$FAC" "$NUM" "$ITERATIONS" "$TRIALS"; do
  if ! [[ "$param" =~ ^[0-9]+$ ]]; then
    echo "错误: 参数 '$param' 必须是正整数"
    exit 1
  fi
done

# 根目录，请根据你的实际路径调整
BASE_DIR="/root/autodl-tmp"
TARGET_DIR="${BASE_DIR}/lude_100_150_hold${HOLD}_fac${FAC}_num${NUM}/lude/"

# 检查目录是否存在
if [ ! -d "${TARGET_DIR}" ]; then
  echo "❌ 目标目录不存在：${TARGET_DIR}"
  exit 1
fi

# 进入工作目录
echo "进入工作目录：${TARGET_DIR}"
cd "${TARGET_DIR}"

# 构建清空参数
CLEAR_OPT=""
if [ "$CLEAR_RESULTS" = "true" ]; then
  CLEAR_OPT="--clear"
fi

echo "开始执行优化... (持仓: ${HOLD}, 因子: ${FAC}, 序号: ${NUM}, 模式: ${MODE}, 迭代次数: ${ITERATIONS}, 试验次数: ${TRIALS}, 清空结果: ${CLEAR_RESULTS})"
# 执行优化脚本
./run_optimizer.sh \
  -m ${MODE} \
  --method tpe \
  --strategy multistage \
  --start 20220729 \
  --end 20240809 \
  --min 100 \
  --max 200 \
  --jobs 5 \
  --trials ${TRIALS} \
  --hold ${HOLD} \
  --seed-start 42 \
  --seed-step 1000 \
  --iterations ${ITERATIONS} \
  --factors ${FAC} \
  -b \
  -l optimization.log \
  ${CLEAR_OPT}

echo "✅ 完成：hold=${HOLD} fac=${FAC} num=${NUM}"