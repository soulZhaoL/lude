#!/usr/bin/env bash
set -euo pipefail
# chmod +x ~/batch_init_env.sh ~/run_opt.shchmod +x ~/batch_init_env.sh ~/run_opt.sh
# /root/run_opt.sh 5 3 1
#
#
#

# ----------------------------------
#  usage 函数
usage() {
  echo "用法: $0 hold fac num"
  echo "示例: $0 5 3 1"
  exit 1
}

# 参数检查
[ $# -eq 3 ] || usage
HOLD="$1"
FAC="$2"
NUM="$3"

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

echo "开始执行优化..."
# 执行优化脚本
./run_optimizer.sh \
  -m continuous \
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
  --iterations 10 \
  --factors ${FAC}

echo "✅ 完成：hold=${HOLD} fac=${FAC} num=${NUM}"