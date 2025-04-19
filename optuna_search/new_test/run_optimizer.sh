#!/bin/bash

# 可转债多因子优化脚本
# 作者: Cascade
# 日期: 2025-04-18

# 激活conda环境（如果需要）
source ~/miniconda3/etc/profile.d/conda.sh
conda activate lude

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 默认参数
MODE="single"        # 运行模式: single(单次运行) 或 continuous(持续优化)
STRATEGY="multistage" # 优化策略: domain, prescreen, multistage, filter
METHOD="tpe"         # 优化方法: tpe, random, cmaes
N_TRIALS=3000        # 优化迭代次数
N_FACTORS=3          # 因子数量
START_DATE="20220729" # 回测开始日期
END_DATE="20250328"  # 回测结束日期
PRICE_MIN=100        # 价格下限
PRICE_MAX=150        # 价格上限
HOLD_NUM=5           # 持仓数量
N_JOBS=15            # 并行任务数
SEED=42              # 随机种子
ITERATIONS=10        # 持续优化模式下的运行次数
BACKGROUND=false     # 是否在后台运行
LOG_FILE=""          # 日志文件
CLEAR_RESULTS=false  # 是否清空结果目录

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
    echo "  --seed <n>               随机种子, 默认: 42"
    echo "  --iterations <n>         持续模式下的运行次数, 默认: 10"
    echo "  -b, --background         在后台运行脚本"
    echo "  -l, --log <filename>     指定日志文件(用于后台运行)"
    echo "  --clear                  运行前清空结果目录"
    echo "  -h, --help               显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -s multistage --factors 4 --jobs 15"
    echo "  $0 -m continuous --iterations 20 --strategy filter"
    echo "  $0 -m continuous -b -l optimization.log"
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

# 询问是否清空结果目录
if [[ "$CLEAR_RESULTS" = false ]]; then
    # 检查结果目录是否存在且非空
    RESULTS_DIR="optimization_results"
    if [[ -d "$RESULTS_DIR" && "$(ls -A $RESULTS_DIR 2>/dev/null)" ]]; then
        # 统计文件数量和占用空间
        FILE_COUNT=$(find "$RESULTS_DIR" -type f | wc -l)
        DIR_SIZE=$(du -sh "$RESULTS_DIR" | cut -f1)
        
        echo -e "${YELLOW}发现 $RESULTS_DIR 目录已存在并包含 $FILE_COUNT 个文件，占用 $DIR_SIZE 空间${NC}"
        read -p "是否在运行前清空该目录? (y/n) [默认:y]: " confirm_clear
        confirm_clear=${confirm_clear:-y}
        if [[ "$confirm_clear" == "y" ]]; then
            CLEAR_RESULTS=true
        fi
    fi
fi

# 清空结果目录（如果需要）
if [[ "$CLEAR_RESULTS" = true ]]; then
    echo -e "${YELLOW}正在清空 optimization_results 目录...${NC}"
    rm -rf optimization_results/*
    # 确保目录存在
    mkdir -p optimization_results/best_models
    echo -e "${GREEN}目录已清空${NC}"
fi

# 构建命令
if [[ "$MODE" = "single" ]]; then
    CMD="python domain_knowledge_optimizer.py --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed $SEED"
else
    CMD="python continuous_optimizer.py --iterations $ITERATIONS --strategy $STRATEGY --method $METHOD --n_trials $N_TRIALS --n_factors $N_FACTORS --start_date $START_DATE --end_date $END_DATE --price_min $PRICE_MIN --price_max $PRICE_MAX --hold_num $HOLD_NUM --n_jobs $N_JOBS --seed $SEED"
fi

# 显示将执行的命令
echo -e "${BLUE}将执行以下命令:${NC}"
echo -e "${GREEN}$CMD${NC}"

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
    nohup $CMD > "$LOG_FILE" 2>&1 &
    echo -e "${GREEN}进程已启动，PID: $!${NC}"
    echo -e "可以使用 'tail -f $LOG_FILE' 查看进度"
else
    echo -e "${BLUE}开始运行...${NC}"
    $CMD
fi

echo -e "${GREEN}完成!${NC}"
