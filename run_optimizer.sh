#!/bin/bash

# 进入脚本所在目录（修改为使用绝对路径）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 定义项目根目录
PROJECT_ROOT=$(cd ./ && pwd)

# 定义进程ID文件
PID_FILE="$PROJECT_ROOT/.optimizer_pid"
PID_GROUP_FILE="$PROJECT_ROOT/.optimizer_pid_group"

# 可转债多因子优化脚本
# 作者: Cascade
# 日期: 2025-04-19

# 检测环境并激活conda环境
setup_conda_environment() {
    # 获取当前脚本的完整路径
    SCRIPT_PATH="$SCRIPT_DIR"
    FULL_PATH="$PROJECT_ROOT"
    
    printf "%s当前工作路径: %s%s\n" "${BLUE}" "$FULL_PATH" "${NC}"
    
    # 检查是否为服务器环境（判断是否含有autodl-tmp目录）
    if [[ "$FULL_PATH" == *"autodl-tmp"* ]]; then
        printf "%s检测到服务器环境%s\n" "${BLUE}" "${NC}"
        
        # 从路径中提取环境名称（例如从/root/autodl-tmp/lude_100_150_hold5_fac3_num1/lude提取lude_100_150_hold5_fac3_num1）
        ENV_NAME=$(echo "$FULL_PATH" | grep -o 'lude_[^/]*')
        
        if [[ -n "$ENV_NAME" ]]; then
            printf "%s尝试激活服务器conda环境: %s%s\n" "${BLUE}" "$ENV_NAME" "${NC}"
            source /root/miniconda3/etc/profile.d/conda.sh
            conda activate "$ENV_NAME" || printf "%s警告: 无法激活环境 %s%s\n" "${RED}" "$ENV_NAME" "${NC}"
        else
            printf "%s警告: 无法从路径解析出conda环境名称，将使用默认环境%s\n" "${RED}" "${NC}"
        fi
    else
        printf "%s检测到本地环境%s\n" "${BLUE}" "${NC}"
        # 本地环境使用固定的conda环境
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate lude || printf "%s警告: 无法激活本地环境 lude%s\n" "${RED}" "${NC}"
    fi
}

# 调用函数激活conda环境
setup_conda_environment

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

# 提取工作区ID（用于标识进程）
WORKSPACE_ID=$(dirname "$PROJECT_ROOT" | xargs basename)

# 默认参数
MODE="single"        # 运行模式: single(单次运行) 或 continuous(持续优化)
STRATEGY="domain" # 优化策略: domain, prescreen, multistage, filter
METHOD="tpe"         # 优化方法: tpe, random, cmaes
N_TRIALS=3000        # 优化迭代次数
N_FACTORS=4          # 因子数量
START_DATE="20220729" # 回测开始日期
END_DATE="20250328"  # 回测结束日期
PRICE_MIN=100        # 价格下限
PRICE_MAX=150        # 价格上限
HOLD_NUM=5           # 持仓数量
N_JOBS=15            # 并行任务数
SEED=42              # 随机种子
SEED_START=42        # 起始随机种子
SEED_STEP=1000       # 种子递增步长
ITERATIONS=10        # 持续优化模式下的运行次数
BACKGROUND=false     # 是否在后台运行
LOG_FILE=""          # 日志文件
CLEAR_RESULTS=false  # 是否清空结果目录
ACTION="run"         # 操作类型: run(运行) 或 stop(停止)

# 显示脚本使用说明
show_help() {
    printf "%s可转债多因子优化脚本%s\n" "${BLUE}" "${NC}"
    printf "用法: %s [选项]\n" "$0"
    printf "\n"
    printf "选项:\n"
    printf "  -m, --mode <mode>        运行模式: single(单次) 或 continuous(持续), 默认: single\n"
    printf "  -s, --strategy <strategy> 优化策略: domain, prescreen, multistage, filter, 默认: multistage\n"
    printf "  --method <method>        优化方法: tpe, random, cmaes, 默认: tpe\n"
    printf "  --trials <n>             优化迭代次数, 默认: 3000\n"
    printf "  --factors <n>            因子数量(3-5), 默认: 3\n"
    printf "  --start <date>           回测开始日期(格式:YYYYMMDD), 默认: 20220729\n"
    printf "  --end <date>             回测结束日期(格式:YYYYMMDD), 默认: 20250328\n"
    printf "  --min <price>            价格下限, 默认: 100\n"
    printf "  --max <price>            价格上限, 默认: 150\n"
    printf "  --hold <n>               持仓数量, 默认: 5\n"
    printf "  --jobs <n>               并行任务数, 默认: 15\n"
    printf "  --seed <n>               随机种子(单次模式), 默认: 42\n"
    printf "  --seed-start <n>         起始随机种子(持续模式), 默认: 42\n"
    printf "  --seed-step <n>          种子递增步长(持续模式), 默认: 1000\n"
    printf "  --iterations <n>         持续模式下的运行次数, 默认: 10\n"
    printf "  -b, --background         在后台运行脚本\n"
    printf "  -l, --log <filename>     指定日志文件(用于后台运行)\n"
    printf "  --clear                  运行前清空结果目录\n"
    printf "  --stop                   停止后台运行的优化进程\n"
    printf "  --status                 检查后台运行的优化进程状态\n"
    printf "  -h, --help               显示帮助信息\n"
    printf "\n"
    printf "示例:\n"
    printf "  %s -s multistage --factors 4 --jobs 15\n" "$0"
    printf "  %s -m continuous --iterations 20 --strategy filter\n" "$0"
    printf "  %s -m continuous -b -l optimization.log\n" "$0"
    printf "  %s --stop           # 停止后台运行的优化进程\n" "$0"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -s|--strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --method)
            METHOD="$2"
            shift 2
            ;;
        --trials)
            N_TRIALS="$2"
            shift 2
            ;;
        --factors)
            N_FACTORS="$2"
            shift 2
            ;;
        --start)
            START_DATE="$2"
            shift 2
            ;;
        --end)
            END_DATE="$2"
            shift 2
            ;;
        --min)
            PRICE_MIN="$2"
            shift 2
            ;;
        --max)
            PRICE_MAX="$2"
            shift 2
            ;;
        --hold)
            HOLD_NUM="$2"
            shift 2
            ;;
        --jobs)
            N_JOBS="$2"
            shift 2
            ;;
        --seed)
            SEED="$2"
            shift 2
            ;;
        --seed-start)
            SEED_START="$2"
            shift 2
            ;;
        --seed-step)
            SEED_STEP="$2"
            shift 2
            ;;
        --iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        -b|--background)
            BACKGROUND=true
            shift
            ;;
        -l|--log)
            LOG_FILE="$2"
            shift 2
            ;;
        --clear)
            CLEAR_RESULTS=true
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            printf "%s未知参数: %s%s\n" "${RED}" "$1" "${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 验证参数
if [[ "$MODE" != "single" && "$MODE" != "continuous" ]]; then
    printf "%s错误: 模式必须是 'single' 或 'continuous'%s\n" "${RED}" "${NC}"
    exit 1
fi

if [[ "$BACKGROUND" = true && -z "$LOG_FILE" ]]; then
    # 自动生成日志文件名
    timestamp=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="optimization_${STRATEGY}_${timestamp}.log"
    printf "%s将使用自动生成的日志文件: %s%s\n" "${YELLOW}" "$LOG_FILE" "${NC}"
fi

# 检测和初始化结果目录
check_results_dir() {
    # 检测项目根目录是否存在，不存在则创建
    if [ ! -d "$PROJECT_ROOT" ]; then
        printf "%s错误：找不到项目根目录: %s%s\n" "${RED}" "$PROJECT_ROOT" "${NC}"
        exit 1
    fi

    # 检测 optimization_results 目录
    RESULTS_DIR="$PROJECT_ROOT/optimization_results"
    if [ ! -d "$RESULTS_DIR" ]; then
        printf "%s创建 optimization_results 目录...\n" "${BLUE}"
        mkdir -p "$RESULTS_DIR/best_models"
    else
        # 统计目录中的文件数量和占用空间
        file_count=$(find "$RESULTS_DIR" -type f | wc -l)
        file_size=$(du -sh "$RESULTS_DIR" | cut -f1)
        printf "%s发现 optimization_results 目录已存在并包含 %d 个文件，占用 %s 空间\n" "${BLUE}" "$file_count" "$file_size"
        
        # 询问是否清空目录
        if [[ "$CLEAR_RESULTS" = true ]] || [[ "$BACKGROUND" = false ]]; then
            read -p "是否在运行前清空该目录? (y/n) [默认:y]: " clear_dir
            clear_dir=${clear_dir:-y}
            if [[ "$clear_dir" == "y" ]]; then
                printf "%s正在清空 optimization_results 目录...\n" "${BLUE}"
                rm -rf "$RESULTS_DIR"/*
                mkdir -p "$RESULTS_DIR/best_models"
                printf "%s目录已清空\n" "${GREEN}"
            fi
        fi
    fi
}

# 构建命令行
build_command() {
    # 根据参数构建命令行
    if [[ "$MODE" = "single" ]]; then
        CMD="python -m lude.optimization.domain_knowledge_optimizer --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed $SEED --workspace_id $WORKSPACE_ID"
    else
        CMD="python -m lude.optimization.continuous_optimizer --iterations $ITERATIONS --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed_start $SEED_START --seed_step $SEED_STEP --workspace_id $WORKSPACE_ID"
    fi
    
    printf "%s将执行以下命令:\n" "${BLUE}"
    printf "\"%s\"\n" "$CMD"
}

# 停止后台运行的优化进程
stop_optimizer() {
    # 获取当前工作区路径和ID
    CURRENT_DIR=$(pwd)
    WORKSPACE_ID=$(basename $(dirname "$CURRENT_DIR"))
    
    printf "%s当前工作区: %s%s\n" "${BLUE}" "$WORKSPACE_ID" "${NC}"
    
    # 如果进程组文件存在，优先使用它
    if [ -f "$PID_GROUP_FILE" ]; then
        printf "%s找到进程组信息文件...\n" "${BLUE}"
        ALL_PIDS=$(cat "$PID_GROUP_FILE")
        
        if [ -n "$ALL_PIDS" ]; then
            printf "%s正在停止进程组: %s%s\n" "${YELLOW}" "$ALL_PIDS" "${NC}"
            
            # 逐个停止进程
            for pid in $ALL_PIDS; do
                if ps -p $pid > /dev/null 2>&1; then
                    printf "%s终止进程 %d...\n" "${YELLOW}" "$pid"
                    kill $pid 2>/dev/null
                fi
            done
            
            # 等待进程退出
            sleep 2
            
            # 检查进程是否已经停止，如果没有则尝试强制终止
            remaining_pids=""
            for pid in $ALL_PIDS; do
                if ps -p $pid > /dev/null 2>&1; then
                    remaining_pids="$remaining_pids $pid"
                fi
            done
            
            if [ -n "$remaining_pids" ]; then
                printf "%s进程未能正常停止，尝试强制终止: %s%s\n" "${RED}" "$remaining_pids" "${NC}"
                for pid in $remaining_pids; do
                    kill -9 $pid 2>/dev/null
                done
            fi
            
            # 等待一下
            sleep 1
            
            # 最终检查是否还有残留进程
            final_remaining=""
            for pid in $ALL_PIDS; do
                if ps -p $pid > /dev/null 2>&1; then
                    final_remaining="$final_remaining $pid"
                fi
            done
            
            if [ -n "$final_remaining" ]; then
                printf "%s仍有进程无法终止: %s%s\n" "${RED}" "$final_remaining" "${NC}"
                printf "%s请手动终止这些进程%s\n" "${RED}" "${NC}"
                return 1
            else
                printf "%s所有优化进程已终止%s\n" "${GREEN}" "${NC}"
                rm -f "$PID_FILE" "$PID_GROUP_FILE"
                return 0
            fi
        else
            printf "%s进程组文件为空，尝试其他方法终止进程...\n" "${YELLOW}" "${NC}"
        fi
    fi
    
    # 如果没有进程组文件或进程组文件为空，退回到旧方法
    if [ -f "$PID_FILE" ]; then
        optimizer_pid=$(cat "$PID_FILE")
        if ps -p $optimizer_pid > /dev/null; then
            printf "%s正在停止优化进程 (PID: %d)...\n" "${YELLOW}" "$optimizer_pid"
            
            # 查找所有相关进程，包括子进程和线程
            printf "%s查找所有相关进程和线程...\n" "${BLUE}"
            
            # 使用pstree查找进程树（如果可用）
            if command -v pstree >/dev/null 2>&1; then
                pstree -p $optimizer_pid | grep -o '([0-9]\+)' | tr -d '()' > /tmp/related_pids_$$.txt
                related_pids=$(cat /tmp/related_pids_$$.txt)
                rm -f /tmp/related_pids_$$.txt
            else
                # 查找子进程树
                child_pids=$(ps --forest -o pid,ppid | awk -v ppid=$optimizer_pid '$2 == ppid {print $1}')
                
                # 递归查找子进程的子进程
                for cpid in $child_pids; do
                    grandchild_pids=$(ps --forest -o pid,ppid | awk -v ppid=$cpid '$2 == ppid {print $1}')
                    child_pids="$child_pids $grandchild_pids"
                done
                related_pids="$child_pids"
            fi
            
            # 查找特定于当前工作区的Python优化进程
            python_pids=$(ps -eo pid,command | grep -E "python.*lude.optimization" | grep "$CURRENT_DIR" | grep -v grep | awk '{print $1}')
            
            # 合并所有需要终止的进程ID并去重
            all_pids="$optimizer_pid $related_pids $python_pids"
            all_pids=$(echo "$all_pids" | tr ' ' '\n' | sort -u | tr '\n' ' ')
            
            printf "%s找到相关进程: %s%s\n" "${YELLOW}" "$all_pids" "${NC}"
            
            # 先尝试正常终止所有相关进程
            for pid in $all_pids; do
                if ps -p $pid > /dev/null 2>&1; then
                    printf "%s终止进程 %d...\n" "${YELLOW}" "$pid"
                    kill $pid 2>/dev/null
                fi
            done
            
            # 等待一段时间，让进程有机会正常终止
            sleep 2
            
            # 检查进程是否已经停止，如果没有则尝试强制终止
            remaining_pids=""
            for pid in $all_pids; do
                if ps -p $pid > /dev/null 2>&1; then
                    remaining_pids="$remaining_pids $pid"
                fi
            done
            
            if [ -n "$remaining_pids" ]; then
                printf "%s进程未能正常停止，尝试强制终止: %s%s\n" "${RED}" "$remaining_pids" "${NC}"
                for pid in $remaining_pids; do
                    kill -9 $pid 2>/dev/null
                done
                
                # 再次检查是否所有进程都已终止
                sleep 1
                for pid in $remaining_pids; do
                    if ps -p $pid > /dev/null 2>&1; then
                        printf "%s无法终止进程 %d，请手动执行: kill -9 %d%s\n" "${RED}" "$pid" "$pid" "${NC}"
                    fi
                done
            fi
            
            # 最后检查主进程是否已经停止
            if ! ps -p $optimizer_pid > /dev/null; then
                printf "%s优化进程及相关线程已全部停止%s\n" "${GREEN}" "${NC}"
                rm -f "$PID_FILE" "$PID_GROUP_FILE" 2>/dev/null
                return 0
            else
                printf "%s无法停止主优化进程，请手动执行: kill -9 %d%s\n" "${RED}" "$optimizer_pid" "${NC}"
                return 1
            fi
        else
            printf "%s优化进程 (PID: %d) 已不存在%s\n" "${YELLOW}" "$optimizer_pid" "${NC}"
            
            # 确保清理所有相关的Python进程
            # 1. 基于目录的精确匹配
            python_pids=$(ps -eo pid,command | grep -E "python.*lude.optimization" | grep "$CURRENT_DIR" | grep -v grep | awk '{print $1}')
            
            # 2. 额外检查domain_knowledge_optimizer进程
            domain_pids=$(ps -eo pid,command | grep -E "python.*domain_knowledge_optimizer" | grep -v grep | awk '{print $1}')
            
            all_remaining_pids="$python_pids $domain_pids"
            all_remaining_pids=$(echo "$all_remaining_pids" | tr ' ' '\n' | sort -u | tr '\n' ' ')
            
            if [ -n "$all_remaining_pids" ]; then
                printf "%s发现相关的优化进程仍在运行: %s%s\n" "${YELLOW}" "$all_remaining_pids" "${NC}"
                printf "%s正在清理残留进程...\n" "${YELLOW}"
                for pid in $all_remaining_pids; do
                    printf "%s终止进程 %d...\n" "${YELLOW}" "$pid"
                    kill $pid 2>/dev/null
                    sleep 1
                    if ps -p $pid > /dev/null 2>&1; then
                        kill -9 $pid 2>/dev/null
                    fi
                done
                printf "%s残留进程清理完成%s\n" "${GREEN}" "${NC}"
            fi
            rm -f "$PID_FILE" "$PID_GROUP_FILE" 2>/dev/null
            return 0
        fi
    else
        printf "%s未找到正在运行的优化进程%s\n" "${YELLOW}" "${NC}"
        
        # 扫描可能的孤立进程
        python_pids=$(ps -eo pid,command | grep -E "python.*lude.optimization" | grep "$CURRENT_DIR" | grep -v grep | awk '{print $1}')
        domain_pids=$(ps -eo pid,command | grep -E "python.*domain_knowledge_optimizer" | grep -v grep | awk '{print $1}')
        
        all_orphan_pids="$python_pids $domain_pids"
        all_orphan_pids=$(echo "$all_orphan_pids" | tr ' ' '\n' | sort -u | tr '\n' ' ')
        
        if [ -n "$all_orphan_pids" ]; then
            printf "%s发现孤立的优化相关进程: %s%s\n" "${YELLOW}" "$all_orphan_pids" "${NC}"
            read -p "是否终止这些进程? [y/N] " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                for pid in $all_orphan_pids; do
                    printf "%s终止进程 %d...\n" "${YELLOW}" "$pid"
                    kill $pid 2>/dev/null
                    sleep 1
                    if ps -p $pid > /dev/null 2>&1; then
                        kill -9 $pid 2>/dev/null
                    fi
                done
                printf "%s孤立进程清理完成%s\n" "${GREEN}" "${NC}"
            fi
        fi
        
        return 0
    fi
}

# 检查优化进程状态
check_status() {
    if [ -f "$PID_FILE" ]; then
        optimizer_pid=$(cat "$PID_FILE")
        if ps -p $optimizer_pid > /dev/null; then
            printf "%s优化进程正在运行 (PID: %d)%s\n" "${GREEN}" "$optimizer_pid" "${NC}"
            
            # 显示进程详情
            printf "\n进程详情:\n"
            ps -p $optimizer_pid -o pid,ppid,user,%cpu,%mem,start,time,command
            
            # 如果有日志文件，显示最新的10行
            if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
                printf "\n日志文件最新内容 (%s):\n" "$LOG_FILE"
                tail -n 10 "$LOG_FILE"
                printf "\n使用 'tail -f %s' 查看完整日志\n" "$LOG_FILE"
            else
                # 尝试查找默认的日志文件
                default_logs=("optimization.log" "optimizer.log" "optuna.log")
                for log in "${default_logs[@]}"; do
                    if [ -f "$log" ]; then
                        printf "\n日志文件最新内容 (%s):\n" "$log"
                        tail -n 10 "$log"
                        printf "\n使用 'tail -f %s' 查看完整日志\n" "$log"
                        break
                    fi
                done
            fi
            
            return 0
        else
            printf "%s优化进程 (PID: %d) 已不存在%s\n" "${YELLOW}" "$optimizer_pid" "${NC}"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        printf "%s未找到正在运行的优化进程%s\n" "${YELLOW}" "${NC}"
        return 1
    fi
}

# 参照batch_manage_services.sh实现的进程查找函数
find_related_processes() {
    # 获取工作区ID和完整路径（用于更精确匹配）
    local exact_workspace_id=$(basename "$1")
    local exact_lude_path="$1/lude"
    
    # 查找方法1: 使用完整路径精确匹配
    local path_pids=$(ps -eo pid,command | grep -E "python.*lude.optimization" | grep "$exact_lude_path" | grep -v grep | awk '{print $1}')
    
    # 查找方法2: 使用工作区ID精确匹配
    local id_pids=$(ps -eo pid,command | grep -E "python.*lude.optimization" | grep -E "\b$exact_workspace_id\b" | grep -v grep | awk '{print $1}')
    
    # 查找方法3: 针对主进程PPID查找子进程
    local child_pids=""
    if [ -n "$2" ] && ps -p $2 > /dev/null 2>&1; then
        child_pids=$(ps -eo pid,ppid | awk -v ppid=$2 '$2 == ppid {print $1}')
        
        # 递归查找子进程的子进程
        for child_pid in $child_pids; do
            local grand_pids=$(ps -eo pid,ppid | awk -v ppid=$child_pid '$2 == ppid {print $1}')
            child_pids="$child_pids $grand_pids"
        done
    fi
    
    # 查找方法4: 查找特定优化器模块进程
    local opt_pids=""
    if [ -n "$2" ]; then
        # 使用主进程PID作为辅助匹配条件
        opt_pids=$(ps -eo pid,ppid,command | grep -E "python.*(domain_knowledge_optimizer|continuous_optimizer)" | grep -E "($exact_workspace_id)|ppid:$2" | grep -v grep | awk '{print $1}')
    else
        # 没有主进程PID时，仅使用工作区ID匹配
        opt_pids=$(ps -eo pid,command | grep -E "python.*(domain_knowledge_optimizer|continuous_optimizer)" | grep -E "$exact_workspace_id" | grep -v grep | awk '{print $1}')
    fi
    
    # 查找方法5: 基于python进程创建时间和当前会话的关联性查找相关python进程
    local session_pids=""
    if [ -n "$2" ]; then
        # 获取主进程的会话ID
        local main_session=$(ps -o sess= -p $2 2>/dev/null)
        if [ -n "$main_session" ]; then
            # 查找同一会话的Python进程
            session_pids=$(ps -eo pid,sess,command | awk -v sess="$main_session" '$2 == sess && $3 ~ /python/' | awk '{print $1}')
        fi
    fi
    
    # 合并所有检测方法的结果并去重
    echo "$2 $path_pids $id_pids $child_pids $opt_pids $session_pids" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' '
}

# 主执行流程
main() {
    # 检测和初始化结果目录
    check_results_dir
    
    # 构建命令行
    build_command
    
    # 确认执行
    if [[ "$BACKGROUND" = false ]]; then
        read -p "是否继续? (y/n) [默认:y]: " confirm
        confirm=${confirm:-y}
        if [[ "$confirm" != "y" ]]; then
            printf "%s已取消\n" "${RED}"
            exit 0
        fi
    fi
    
    # 执行命令
    if [[ "$BACKGROUND" = true ]]; then
        printf "%s在后台运行，输出将写入: %s%s\n" "${YELLOW}" "$LOG_FILE" "${NC}"
        
        # 检查日志文件是否存在，存在则先删除
        if [ -f "$LOG_FILE" ]; then
            printf "%s发现已存在的日志文件，正在删除...\n" "${YELLOW}"
            rm -f "$LOG_FILE"
        fi
        
        # 清理旧的PID文件
        rm -f "$PID_FILE" "$PID_GROUP_FILE" 2>/dev/null
        
        # 运行命令并保存PID
        nohup $CMD > "$LOG_FILE" 2>&1 &
        PID=$!
        printf "%s主进程已启动，PID: %d%s\n" "${GREEN}" "$PID" "${NC}"
        printf "可以使用 'tail -f %s' 查看进度\n" "$LOG_FILE"
        printf "使用 '%s --stop' 可以停止运行\n" "$0"
        
        # 保存主进程PID
        echo $PID > "$PID_FILE"
        
        # 等待子进程启动 - 服务器环境需要等待更长时间
        if [[ "$FULL_PATH" == *"autodl-tmp"* ]]; then
            printf "%s检测到服务器环境，等待3秒让子进程启动...\n" "${YELLOW}"
            sleep 3
        else
            printf "%s等待子进程启动(1秒)...\n" "${YELLOW}"
            sleep 1
        fi
        
        # 获取当前工作区路径和主进程ID
        WORKSPACE_DIR=$(dirname "$FULL_PATH")
        MAIN_PID=$PID
        
        # 获取相关进程
        printf "%s开始查找相关进程...\n" "${YELLOW}"
        ALL_PIDS=$(find_related_processes "$WORKSPACE_DIR" "$MAIN_PID")
        
        # 如果初次查找失败，再多等待并重试一次
        if [ -z "$ALL_PIDS" ] || [ "$ALL_PIDS" = "$MAIN_PID" ]; then
            printf "%s未找到足够的相关进程，等待5秒后重试...\n" "${YELLOW}"
            sleep 5
            ALL_PIDS=$(find_related_processes "$WORKSPACE_DIR" "$MAIN_PID")
        fi
        
        # 如果没有找到任何进程，至少包含主进程
        if [ -z "$ALL_PIDS" ]; then
            ALL_PIDS=$MAIN_PID
            printf "%s警告: 未检测到子进程，仅记录主进程 PID: %d%s\n" "${YELLOW}" "$MAIN_PID" "${NC}"
        else
            PROC_COUNT=$(echo "$ALL_PIDS" | wc -w)
            printf "%s找到相关进程组: %s%s\n" "${GREEN}" "$ALL_PIDS" "${NC}"
            printf "%s共 %d 个进程%s\n" "${GREEN}" "$PROC_COUNT" "${NC}"
        fi
        
        # 记录进程组到文件
        echo "$ALL_PIDS" > "$PID_GROUP_FILE"
        PROC_COUNT=$(echo "$ALL_PIDS" | wc -w)
        printf "%s进程组已记录，总共 %d 个进程%s\n" "${GREEN}" "$PROC_COUNT" "${NC}"
    else
        printf "%s开始运行...\n" "${BLUE}"
        $CMD
    fi
    
    printf "%s完成!\n" "${GREEN}"
}

# 根据ACTION参数执行不同操作
if [[ "$ACTION" = "stop" ]]; then
    stop_optimizer
    exit $?
elif [[ "$ACTION" = "status" ]]; then
    check_status
    exit $?
fi

# 执行主流程
main
