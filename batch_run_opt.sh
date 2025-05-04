#!/bin/bash

# 批量执行优化任务
# 从num=1执行到num=15
# 作者: Cascade
# 日期: 2025-05-04
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/run_optimizer.sh ~/batch_manage_services.sh ~/batch_run_opt.sh
# /root/batch_run_opt.sh
# 设置优化参数
MODE="continuous"
TRIALS=5000
ITERATIONS=30
HOLD=5
FACTORS=4

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

printf "%s开始批量执行优化任务...%s\n" "${BLUE}" "${NC}"

# 循环执行优化任务
for num in $(seq 1 15); do
  printf "%s▶️ 执行序号：%d (共15个)%s\n" "${YELLOW}" "$num" "${NC}"
  printf "%s运行: /root/run_opt.sh --mode %s --trials %d --iterations %d --hold %d --factors %d --num %d%s\n" "${GREEN}" "$MODE" "$TRIALS" "$ITERATIONS" "$HOLD" "$FACTORS" "$num" "${NC}"
  
  # 执行命令
  /root/run_opt.sh --mode ${MODE} --trials ${TRIALS} --iterations ${ITERATIONS} --hold ${HOLD} --factors ${FACTORS} --num ${num}
  
  # 短暂等待，避免同时启动过多任务
  sleep 1
done

printf "%s所有任务已启动完成！%s\n" "${BLUE}" "${NC}"
printf "%s使用 '/root/batch_manage_services.sh --status' 可查看任务状态%s\n" "${YELLOW}" "${NC}"
