#!/bin/bash

# 进入脚本所在目录（修改为使用绝对路径）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 定义项目根目录
PROJECT_ROOT=$(cd ../.. && pwd)

# 定义进程ID文件
PID_FILE="$PROJECT_ROOT/optuna_search/new_test/.optimizer_pid"

# 可转债多因子优化脚本
# 作者: Cascade
# 日期: 2025-04-19

# 检测环境并激活conda环境
setup_conda_environment() {
    # 获取当前脚本的完整路径
    SCRIPT_PATH="$SCRIPT_DIR"
    FULL_PATH="$PROJECT_ROOT"
    
    echo "当前工作路径: $FULL_PATH"
    
    # 检查是否为服务器环境（判断是否含有autodl-tmp目录）
    if [[ "$FULL_PATH" == *"autodl-tmp"* ]]; then
        echo "检测到服务器环境"
        
        # 从路径中提取环境名称（例如从/root/autodl-tmp/lude_100_150_hold5_fac3_num1/lude提取lude_100_150_hold5_fac3_num1）
        ENV_NAME=$(echo "$FULL_PATH" | grep -o 'lude_[^/]*')
        
        if [[ -n "$ENV_NAME" ]]; then
            echo "尝试激活服务器conda环境: $ENV_NAME"
            source /root/miniconda3/etc/profile.d/conda.sh
            conda activate "$ENV_NAME" || echo "警告: 无法激活环境 $ENV_NAME"
        else
            echo "警告: 无法从路径解析出conda环境名称，将使用默认环境"
        fi
    else
        echo "检测到本地环境"
        # 本地环境使用固定的conda环境
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate lude || echo "警告: 无法激活本地环境 lude"
    fi
}

# 调用函数激活conda环境
setup_conda_environment

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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
    echo -e "${BLUE}可转债多因子优化脚本${NC}"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -m, --mode <mode>        运行模式: single(单次) 或 continuous(持续), 默认: single"
    echo "  -s, --strategy <strategy> 优化策略: domain, prescreen, multistage, filter, 默认: multistage"
    echo "  --method <method>        优化方法: tpe, random, cmaes, 默认: tpe"
    echo "  --trials <n>             优化迭代次数, 默认: 3000"
    echo "  --factors <n>            因子数量(3-5), 默认: 3"
    echo "  --start <date>           回测开始日期(格式:YYYYMMDD), 默认: 20220729"
    echo "  --end <date>             回测结束日期(格式:YYYYMMDD), 默认: 20250328"
    echo "  --min <price>            价格下限, 默认: 100"
    echo "  --max <price>            价格上限, 默认: 150"
    echo "  --hold <n>               持仓数量, 默认: 5"
    echo "  --jobs <n>               并行任务数, 默认: 15"
    echo "  --seed <n>               随机种子(单次模式), 默认: 42"
    echo "  --seed-start <n>         起始随机种子(持续模式), 默认: 42"
    echo "  --seed-step <n>          种子递增步长(持续模式), 默认: 1000"
    echo "  --iterations <n>         持续模式下的运行次数, 默认: 10"
    echo "  -b, --background         在后台运行脚本"
    echo "  -l, --log <filename>     指定日志文件(用于后台运行)"
    echo "  --clear                  运行前清空结果目录"
    echo "  --stop                   停止后台运行的优化进程"
    echo "  --status                 检查后台运行的优化进程状态"
    echo "  -h, --help               显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -s multistage --factors 4 --jobs 15"
    echo "  $0 -m continuous --iterations 20 --strategy filter"
    echo "  $0 -m continuous -b -l optimization.log"
    echo "  $0 --stop           # 停止后台运行的优化进程"
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
            echo -e "${RED}未知参数: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 验证参数
if [[ "$MODE" != "single" && "$MODE" != "continuous" ]]; then
    echo -e "${RED}错误: 模式必须是 'single' 或 'continuous'${NC}"
    exit 1
fi

if [[ "$BACKGROUND" = true && -z "$LOG_FILE" ]]; then
    # 自动生成日志文件名
    timestamp=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="optimization_${STRATEGY}_${timestamp}.log"
    echo -e "${YELLOW}将使用自动生成的日志文件: $LOG_FILE${NC}"
fi

# 检测和初始化结果目录
check_results_dir() {
    # 检测项目根目录是否存在，不存在则创建
    if [ ! -d "$PROJECT_ROOT" ]; then
        echo -e "${RED}错误：找不到项目根目录: $PROJECT_ROOT${NC}"
        exit 1
    fi

    # 检测 optimization_results 目录
    RESULTS_DIR="$PROJECT_ROOT/optuna_search/new_test/optimization_results"
    if [ ! -d "$RESULTS_DIR" ]; then
        echo "创建 optimization_results 目录..."
        mkdir -p "$RESULTS_DIR/best_models"
    else
        # 统计目录中的文件数量和占用空间
        file_count=$(find "$RESULTS_DIR" -type f | wc -l)
        file_size=$(du -sh "$RESULTS_DIR" | cut -f1)
        echo "发现 optimization_results 目录已存在并包含 $file_count 个文件，占用 $file_size 空间"
        
        # 询问是否清空目录
        if [[ "$CLEAR_RESULTS" = true ]] || [[ "$BACKGROUND" = false ]]; then
            read -p "是否在运行前清空该目录? (y/n) [默认:y]: " clear_dir
            clear_dir=${clear_dir:-y}
            if [[ "$clear_dir" == "y" ]]; then
                echo "正在清空 optimization_results 目录..."
                rm -rf "$RESULTS_DIR"/*
                mkdir -p "$RESULTS_DIR/best_models"
                echo "目录已清空"
            fi
        fi
    fi
}

# 构建命令行
build_command() {
    # 根据运行模式设置命令
    if [[ "$MODE" == "single" ]]; then
        CMD="python domain_knowledge_optimizer.py --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed $SEED"
    else
        CMD="python continuous_optimizer.py --iterations $ITERATIONS --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed_start $SEED_START --seed_step $SEED_STEP"
    fi
    
    echo "将执行以下命令:"
    echo "\"$CMD\""
}

# 停止后台运行的优化进程
stop_optimizer() {
    if [ -f "$PID_FILE" ]; then
        optimizer_pid=$(cat "$PID_FILE")
        if ps -p $optimizer_pid > /dev/null; then
            echo -e "${YELLOW}正在停止优化进程 (PID: $optimizer_pid)...${NC}"
            kill $optimizer_pid
            sleep 1
            
            # 检查进程是否已经停止
            if ps -p $optimizer_pid > /dev/null; then
                echo -e "${RED}进程未能正常停止，尝试强制终止...${NC}"
                kill -9 $optimizer_pid
            fi
            
            # 再次检查进程是否已经停止
            if ! ps -p $optimizer_pid > /dev/null; then
                echo -e "${GREEN}优化进程已停止${NC}"
                rm -f "$PID_FILE"
                return 0
            else
                echo -e "${RED}无法停止优化进程，请手动执行: kill -9 $optimizer_pid${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}优化进程 (PID: $optimizer_pid) 已不存在${NC}"
            rm -f "$PID_FILE"
            return 0
        fi
    else
        echo -e "${YELLOW}未找到正在运行的优化进程${NC}"
        return 0
    fi
}

# 检查优化进程状态
check_status() {
    if [ -f "$PID_FILE" ]; then
        optimizer_pid=$(cat "$PID_FILE")
        if ps -p $optimizer_pid > /dev/null; then
            echo -e "${GREEN}优化进程正在运行 (PID: $optimizer_pid)${NC}"
            
            # 显示进程详情
            echo -e "\n进程详情:"
            ps -p $optimizer_pid -o pid,ppid,user,%cpu,%mem,start,time,command
            
            # 如果有日志文件，显示最新的10行
            if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
                echo -e "\n日志文件最新内容 ($LOG_FILE):"
                tail -n 10 "$LOG_FILE"
                echo -e "\n使用 'tail -f $LOG_FILE' 查看完整日志"
            else
                # 尝试查找默认的日志文件
                default_logs=("optimization.log" "optimizer.log" "optuna.log")
                for log in "${default_logs[@]}"; do
                    if [ -f "$log" ]; then
                        echo -e "\n日志文件最新内容 ($log):"
                        tail -n 10 "$log"
                        echo -e "\n使用 'tail -f $log' 查看完整日志"
                        break
                    fi
                done
            fi
            
            return 0
        else
            echo -e "${YELLOW}优化进程 (PID: $optimizer_pid) 已不存在${NC}"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo -e "${YELLOW}未找到正在运行的优化进程${NC}"
        return 1
    fi
}

# 主执行流程
main() {
    # 检查和初始化结果目录
    check_results_dir
    
    # 构建命令行
    build_command
    
    # 确认执行
    if [[ "$BACKGROUND" = false ]]; then
        read -p "是否继续? (y/n) [默认:y]: " confirm
        confirm=${confirm:-y}
        if [[ "$confirm" != "y" ]]; then
            echo "已取消"
            exit 0
        fi
    fi
    
    # 执行命令
    if [[ "$BACKGROUND" = true ]]; then
        echo -e "${YELLOW}在后台运行，输出将写入: $LOG_FILE${NC}"
        
        # 检查日志文件是否存在，存在则先删除
        if [ -f "$LOG_FILE" ]; then
            echo -e "${YELLOW}发现已存在的日志文件，正在删除...${NC}"
            rm -f "$LOG_FILE"
        fi
        
        nohup $CMD > "$LOG_FILE" 2>&1 &
        PID=$!
        echo -e "${GREEN}进程已启动，PID: $PID${NC}"
        echo -e "可以使用 'tail -f $LOG_FILE' 查看进度"
        echo -e "使用 '$0 --stop' 可以停止运行"
        echo $PID > "$PID_FILE"
    else
        echo -e "${BLUE}开始运行...${NC}"
        $CMD
    fi
    
    echo -e "${GREEN}完成!${NC}"
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
