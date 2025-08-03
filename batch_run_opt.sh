#!/bin/bash

# 批量执行优化任务
# 从num=1执行到num=15
# 作者: Cascade
# 日期: 2025-05-04
# chmod +x ~/*.sh
# /root/batch_run_opt.sh

# 默认不清空结果目录
# /root/batch_run_opt.sh
# 明确指定清空结果目录
# /root/batch_run_opt.sh --clear
# 可以与其他参数一起使用
# /root/batch_run_opt.sh --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 5
# 启用过滤优化
# /root/batch_run_opt.sh --clear --mode continuous --trials 5000 --iterations 30 --hold 5 --factors 5 --enable_filter_opt

# TODO 
# 我有一个问题.  我发现 @batch_run_opt.sh  -> @run_opt.sh  -> @run_optimizer.sh
  #  ,  似乎可以省略掉 @run_opt.sh , 直接调用 @run_optimizer.sh , 请你评估是否合理. 如果可以合并,请帮我合并.
  # 我发现 job数量是写死的,请你帮我调整成可配置的.


# 设置优化参数
MODE="continuous"
TRIALS=5000
ITERATIONS=30
HOLD=5
FACTORS=5
CLEAR_RESULTS=false  # 默认不清空结果目录

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
    --enable_filter_opt)
      ENABLE_FILTER_OPT=true
      shift
      ;;
    *)
      echo "错误: 未知参数 $1"
      echo "用法: $0 [--clear] [--mode MODE] [--trials NUM] [--iterations NUM] [--hold NUM] [--factors NUM]"
      exit 1
      ;;
  esac
done

echo "开始批量执行优化任务...===================================================================================================="
echo "参数设置: 模式=${MODE}, 试验次数=${TRIALS}, 迭代=${ITERATIONS}, 持仓=${HOLD}, 因子=${FACTORS}, 清空结果=${CLEAR_RESULTS}"

# 构建清空参数
CLEAR_OPT=""
if [ "$CLEAR_RESULTS" = true ]; then
  CLEAR_OPT="--clear"
fi

# 循环执行优化任务
for num in $(seq 1 15); do
  echo "▶️ 执行序号：${num} (共15个)"
  echo "运行: /root/run_opt.sh --mode ${MODE} --trials ${TRIALS} --iterations ${ITERATIONS} --hold ${HOLD} --factors ${FACTORS} --num ${num} ${CLEAR_OPT}"
  
  # 执行命令
  /root/run_opt.sh --mode ${MODE} --trials ${TRIALS} --iterations ${ITERATIONS} --hold ${HOLD} --factors ${FACTORS} --num ${num} ${CLEAR_OPT}
  
  # 短暂等待，避免同时启动过多任务
  sleep 1
done

echo "所有任务已启动完成！"
echo "使用 '/root/batch_manage_services.sh --status' 可查看任务状态"
