#!/usr/bin/env bash
set -euo pipefail
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/run_optimizer.sh ~/batch_manage_services.sh
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/run_optimizer.sh ~/batch_manage_services.sh ~/batch_run_opt.sh

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

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
    --help)
      usage
      ;;
    *)
      echo -e "${RED}错误: 未知参数 $1${NC}"
      usage
      ;;
  esac
done

# 检查必选参数
if [ -z "$HOLD" ] || [ -z "$FAC" ] || [ -z "$NUM" ]; then
  echo -e "${RED}错误: 缺少必选参数${NC}"
  usage
fi

# 验证模式参数
if [ "$MODE" != "single" ] && [ "$MODE" != "continuous" ]; then
  echo -e "${RED}错误: 模式必须是 'single' 或 'continuous'${NC}"
  exit 1
fi

# 验证数值参数
for param in "$HOLD" "$FAC" "$NUM" "$ITERATIONS" "$TRIALS"; do
  if ! [[ "$param" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}错误: 参数 '$param' 必须是正整数${NC}"
    exit 1
  fi
done

# 根目录，请根据你的实际路径调整
BASE_DIR="/root/autodl-tmp"
TARGET_DIR="${BASE_DIR}/lude_100_150_hold${HOLD}_fac${FAC}_num${NUM}/lude/"

# 检查目录是否存在
if [ ! -d "${TARGET_DIR}" ]; then
  echo -e "${RED}❌ 目标目录不存在：${TARGET_DIR}${NC}"
  exit 1
fi

# 进入工作目录
echo -e "${BLUE}进入工作目录：${TARGET_DIR}${NC}"
cd "${TARGET_DIR}"

echo -e "${GREEN}开始执行优化... (持仓: ${HOLD}, 因子: ${FAC}, 序号: ${NUM}, 模式: ${MODE}, 迭代次数: ${ITERATIONS}, 试验次数: ${TRIALS})${NC}"
# 执行优化脚本
./run_optimizer.sh \
  -m ${MODE} \
  --method tpe \
  --strategy multistage \
  --start 20220729 \
  --end 20250328 \
  --min 100 \
  --max 150 \
  --jobs 5 \
  --trials ${TRIALS} \
  --hold ${HOLD} \
  --seed-start 42 \
  --seed-step 1000 \
  --iterations ${ITERATIONS} \
  --factors ${FAC} \
  -b \
  -l optimization.log

echo -e "${GREEN}✅ 完成：hold=${HOLD} fac=${FAC} num=${NUM}${NC}"