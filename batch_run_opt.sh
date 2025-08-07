#!/bin/bash

# 批量执行优化任务 - 直接调用 run_optimizer.sh（已重构）
# 从num=1执行到num=15
# 作者: Cascade
# 日期: 2025-05-04
# 重构日期: 2025-08-03 (省略 run_opt.sh，直接调用 run_optimizer.sh，降低维护成本)
# chmod +x ~/*.sh
# /root/batch_run_opt.sh

# 使用示例:
# 默认运行
# /root/batch_run_opt.sh
# 明确指定清空结果目录
# /root/batch_run_opt.sh --clear
# 可以与其他参数一起使用
# /root/batch_run_opt.sh --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 5 --jobs 8
# 启用过滤优化
# /root/batch_run_opt.sh --clear --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 5 --enable_filter_opt --jobs 10
# 完整参数示例
# /root/batch_run_opt.sh --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 4 --jobs 15 --enable_filter_opt --clear

# 设置优化参数
MODE="continuous"
TRIALS=5000
ITERATIONS=30
HOLD=5
FACTORS=5
JOBS=5  # 并行任务数，现在可配置
CLEAR_RESULTS=false  # 默认不清空结果目录
ENABLE_FILTER_OPT=false  # 默认不启用过滤因子优化

# 服务器环境路径配置（来自原 run_opt.sh）
BASE_DIR="/root/autodl-tmp"

# 固定参数配置（来自原 run_opt.sh）
METHOD="tpe"
STRATEGY="multistage"
START_DATE="20220801"
END_DATE="20240804"
PRICE_MIN="100"
PRICE_MAX="150"
SEED_START="42"
SEED_STEP="1000"

# 处理命令行参数
while [ $# -gt 0 ]; do
  case "$1" in
    --clear)
      CLEAR_RESULTS=true
      shift
      ;;
    --mode|-m)
      MODE="$2"
      shift 2
      ;;
    --trials|-t)
      TRIALS="$2"
      shift 2
      ;;
    --iterations|-i)
      ITERATIONS="$2"
      shift 2
      ;;
    --hold|-h)
      HOLD="$2"
      shift 2
      ;;
    --factors|-f)
      FACTORS="$2"
      shift 2
      ;;
    --jobs|-j)
      JOBS="$2"
      shift 2
      ;;
    --enable_filter_opt)
      ENABLE_FILTER_OPT=true
      shift
      ;;
    *)
      echo "错误: 未知参数 $1"
      echo "用法: $0 [--clear] [--mode MODE] [--trials NUM] [--iterations NUM] [--hold NUM] [--factors NUM] [--jobs NUM] [--enable_filter_opt]"
      exit 1
      ;;
  esac
done

echo "开始批量执行优化任务...===================================================================================================="
echo "参数设置:"
echo "  运行模式: ${MODE}"
echo "  试验次数: ${TRIALS}"
echo "  迭代次数: ${ITERATIONS}"
echo "  持仓数量: ${HOLD}"
echo "  因子数量: ${FACTORS}"
echo "  并行任务: ${JOBS}"
echo "  清空结果: ${CLEAR_RESULTS}"
echo "  启用过滤优化: ${ENABLE_FILTER_OPT}"
echo "固定参数:"
echo "  优化方法: ${METHOD}"
echo "  优化策略: ${STRATEGY}"
echo "  回测日期: ${START_DATE} - ${END_DATE}"
echo "  价格范围: ${PRICE_MIN} - ${PRICE_MAX}"
echo "  种子配置: 起始=${SEED_START}, 步长=${SEED_STEP}"

# 构建清空参数
CLEAR_OPT=""
if [ "$CLEAR_RESULTS" = true ]; then
  CLEAR_OPT="--clear"
fi

# 构建过滤优化参数
FILTER_OPT=""
if [ "$ENABLE_FILTER_OPT" = true ]; then
  FILTER_OPT="--enable_filter_opt"
fi

# 循环执行优化任务
for num in $(seq 1 15); do
  echo "▶️ 执行序号：${num} (共15个)"
  
  # 构建目标目录（来自原 run_opt.sh 的逻辑）
  TARGET_DIR="${BASE_DIR}/lude_100_150_hold${HOLD}_fac${FACTORS}_num${num}/lude/"
  
  # 检查目录是否存在
  if [ ! -d "${TARGET_DIR}" ]; then
    echo "❌ 目标目录不存在：${TARGET_DIR}"
    echo "   跳过序号 ${num}"
    continue
  fi
  
  echo "📂 工作目录: ${TARGET_DIR}"
  echo "🚀 直接调用 run_optimizer.sh (省略 run_opt.sh 中间层)"
  
  # 进入工作目录并执行 run_optimizer.sh
  (
    cd "${TARGET_DIR}" || exit 1
    ./run_optimizer.sh \
      --mode ${MODE} \
      --method ${METHOD} \
      --strategy ${STRATEGY} \
      --start ${START_DATE} \
      --end ${END_DATE} \
      --min ${PRICE_MIN} \
      --max ${PRICE_MAX} \
      --jobs ${JOBS} \
      --trials ${TRIALS} \
      --hold ${HOLD} \
      --factors ${FACTORS} \
      --iterations ${ITERATIONS} \
      --seed-start ${SEED_START} \
      --seed-step ${SEED_STEP} \
      -b \
      -l optimization.log \
      ${CLEAR_OPT} ${FILTER_OPT}
  )
  
  if [ $? -eq 0 ]; then
    echo "✅ 序号 ${num} 启动成功"
  else
    echo "❌ 序号 ${num} 启动失败"
  fi
  
  # 短暂等待，避免同时启动过多任务
  sleep 1
done

echo "所有任务已启动完成！"
echo "使用 '/root/batch_manage_services.sh --status' 可查看任务状态"
