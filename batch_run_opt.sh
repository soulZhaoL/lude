#!/bin/bash

# 批量执行优化任务
# 从num=1执行到num=15
# 作者: Cascade
# 日期: 2025-05-04
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/batch_manage_services.sh ~/batch_run_opt.sh
# /root/batch_run_opt.sh
# 设置优化参数
MODE="continuous"
TRIALS=5000
ITERATIONS=30
HOLD=5
FACTORS=4

echo "开始批量执行优化任务..."

# 循环执行优化任务
for num in $(seq 1 15); do
  echo "▶️ 执行序号：${num} (共15个)"
  echo "运行: /root/run_opt.sh --mode ${MODE} --trials ${TRIALS} --iterations ${ITERATIONS} --hold ${HOLD} --factors ${FACTORS} --num ${num}"
  
  # 执行命令
  /root/run_opt.sh --mode ${MODE} --trials ${TRIALS} --iterations ${ITERATIONS} --hold ${HOLD} --factors ${FACTORS} --num ${num}
  
  # 短暂等待，避免同时启动过多任务
  sleep 1
done

echo "所有任务已启动完成！"
echo "使用 '/root/batch_manage_services.sh --status' 可查看任务状态"
