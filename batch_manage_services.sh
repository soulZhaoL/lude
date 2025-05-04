#!/bin/bash

# 可转债多因子批量服务管理脚本
# 功能：批量查看服务状态或批量停止服务
# 作者: Cascade
# 日期: 2025-05-04
# chmod +x ~/batch_init_env.sh ~/run_opt.sh ~/batch_manage_services.sh ~/batch_run_opt.sh
# 查看所有服务状态
# /root/batch_manage_services.sh --status

# 停止所有服务
# /root/batch_manage_services.sh --stop


# 显示帮助信息
# /root/batch_manage_services.sh --help

# 定义工程根目录
PROJECT_ROOT="/root/autodl-tmp"
# 本地测试用
# PROJECT_ROOT="/Users/zhaolei/My/python/lude"

# 显示帮助信息
show_help() {
    echo "批量服务管理工具"
    echo "用法: $0 [选项]"
    echo "选项:"
    echo "  -s, --status    检查所有服务状态"
    echo "  -k, --stop      停止所有服务"
    echo "  -h, --help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --status    # 查看所有服务状态"
    echo "  $0 --stop      # 停止所有服务"
}

# 检查单个服务状态
check_status() {
    local workspace_dir="$1"
    local lude_dir="$workspace_dir/lude"
    local pid_file="$lude_dir/.optimizer_pid"
    
    echo ""
    echo "==================================== 检查服务: $(basename "$workspace_dir") ===================================="
    
    if [ ! -d "$lude_dir" ]; then
        echo "错误: 目录 '$lude_dir' 不存在"
        return 1
    fi
    
    if [ -f "$pid_file" ]; then
        local optimizer_pid=$(cat "$pid_file")
        if ps -p $optimizer_pid > /dev/null 2>&1; then
            echo "服务正在运行 (PID: $optimizer_pid)"
            
            # 显示进程详情
            echo ""
            echo "进程详情:"
            ps -p $optimizer_pid -o pid,ppid,user,%cpu,%mem,start,time,command
            
            # 如果有日志文件，显示最新的5行
            local default_logs=("$lude_dir/optimization.log" "$lude_dir/optimizer.log" "$lude_dir/optuna.log")
            for log in "${default_logs[@]}"; do
                if [ -f "$log" ]; then
                    echo ""
                    echo "日志文件最新内容 ($(basename "$log")):"
                    tail -n 5 "$log"
                    break
                fi
            done
            
            return 0
        else
            echo "服务PID文件存在 ($optimizer_pid)，但进程已不存在"
            return 1
        fi
    else
        echo "服务未运行 (未找到PID文件)"
        return 1
    fi
}

# 定义一个函数来查找与当前工作区相关的所有进程
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
    # 这里使用grep -E "($exact_workspace_id)|($2)"确保只查找与当前工作区或主进程相关的优化器进程
    local opt_pids=""
    if [ -n "$2" ]; then
        # 使用主进程PID作为辅助匹配条件
        opt_pids=$(ps -eo pid,ppid,command | grep -E "python.*(domain_knowledge_optimizer|continuous_optimizer)" | grep -E "($exact_workspace_id)|ppid:$2" | grep -v grep | awk '{print $1}')
    else
        # 没有主进程PID时，仅使用工作区ID匹配
        opt_pids=$(ps -eo pid,command | grep -E "python.*(domain_knowledge_optimizer|continuous_optimizer)" | grep -E "$exact_workspace_id" | grep -v grep | awk '{print $1}')
    fi
    
    # 查找方法5: 基于python进程创建时间和当前会话的关联性查找相关python进程
    # 这种方法假设同一次启动的进程，创建时间相近且运行在同一个会话中
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

# 停止单个服务
stop_service() {
    local workspace_dir="$1"
    local lude_dir="$workspace_dir/lude"
    local pid_file="$lude_dir/.optimizer_pid"
    local pid_group_file="$lude_dir/.optimizer_pid_group"
    
    echo ""
    echo "==================================== 正在停止服务: $(basename "$workspace_dir") ===================================="
    
    if [ ! -d "$lude_dir" ]; then
        echo "错误: 目录 '$lude_dir' 不存在"
        return 1
    fi
    
    # 获取工作区标识符（用于更精确匹配）
    local workspace_id=$(basename "$workspace_dir")
    local MAIN_PID=""  # 初始化主进程PID变量
    
    # 如果进程组文件存在，优先使用它
    if [ -f "$pid_group_file" ]; then
        echo "找到进程组信息文件..."
        ALL_PIDS=$(cat "$pid_group_file")
        
        if [ -n "$ALL_PIDS" ]; then
            echo "使用记录的进程组: $ALL_PIDS"
        else
            echo "进程组文件为空，将使用进程扫描方式"
            ALL_PIDS=$(find_related_processes "$workspace_dir")
        fi
    elif [ -f "$pid_file" ]; then
        # 使用PID文件获取主进程ID
        MAIN_PID=$(cat "$pid_file")
        echo "找到主进程ID: $MAIN_PID"
        
        # 查找所有相关进程
        ALL_PIDS="$MAIN_PID $(find_related_processes "$workspace_dir" "$MAIN_PID")"
        ALL_PIDS=$(echo "$ALL_PIDS" | tr ' ' '\n' | sort -u | tr '\n' ' ')
    else
        echo "未找到PID文件，尝试查找相关进程..."
        ALL_PIDS=$(find_related_processes "$workspace_dir")
    fi
    
    if [ -z "$ALL_PIDS" ]; then
        echo "未找到任何相关进程，服务可能未运行"
        return 0
    fi
    
    echo "找到相关进程: $ALL_PIDS"
    
    # 逐个停止进程
    for pid in $ALL_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "正在终止进程 $pid..."
            kill $pid 2>/dev/null
        fi
    done
    
    # 等待一段时间，让进程有机会正常终止
    sleep 2
    
    # 检查进程是否已经停止，如果没有则尝试强制终止
    remaining_pids=""
    for pid in $ALL_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            remaining_pids="$remaining_pids $pid"
        fi
    done
    
    if [ -n "$remaining_pids" ]; then
        echo "进程未能正常停止，尝试强制终止: $remaining_pids "
        for pid in $remaining_pids; do
            kill -9 $pid 2>/dev/null
        done
        
        # 再次检查是否所有进程都已终止
        sleep 1
        remaining_pids=""
        for pid in $ALL_PIDS; do
            if ps -p $pid > /dev/null 2>&1; then
                remaining_pids="$remaining_pids $pid"
            fi
        done
        
        if [ -n "$remaining_pids" ]; then
            echo "仍有进程无法终止: $remaining_pids"
            echo "请手动终止这些进程"
            return 1
        fi
    fi
    
    # 最后一次检查是否还有漏网之鱼
    FINAL_CHECK=$(find_related_processes "$workspace_dir")
    if [ -n "$FINAL_CHECK" ]; then
        echo "检测到可能遗漏的相关进程: $FINAL_CHECK"
        echo "正在尝试终止这些进程..."
        for pid in $FINAL_CHECK; do
            if ps -p $pid > /dev/null 2>&1; then
                echo "终止额外进程 $pid..."
                kill $pid 2>/dev/null
                sleep 1
                if ps -p $pid > /dev/null 2>&1; then
                    kill -9 $pid 2>/dev/null
                fi
            fi
        done
    fi
    
    # 清理PID文件
    rm -f "$pid_file" "$pid_group_file" 2>/dev/null
    
    echo "服务已成功停止"
    return 0
}

# 批量停止所有服务
stop_all_services() {
    echo "开始批量停止所有服务..."
    
    # 记录成功停止的服务数量
    local stopped_count=0
    local total_count=0
    local failed_workspaces=""
    
    # 寻找所有工作区目录
    local workspaces=$(find "$PROJECT_ROOT" -maxdepth 1 -type d -name "lude_*")
    
    if [ -z "$workspaces" ]; then
        echo "未找到任何工作区目录"
        return 1
    fi
    
    for workspace in $workspaces; do
        ((total_count++))
        stop_service "$workspace"
        if [ $? -eq 0 ]; then
            ((stopped_count++))
        else
            failed_workspaces="$failed_workspaces\n - $(basename "$workspace")"
        fi
    done
    
    # 最后检查是否有任何遗漏的优化相关进程
    echo ""
    echo "进行最终检查，查找任何可能遗漏的优化进程..."
    orphan_pids=$(ps -eo pid,command | grep -E "python.*(domain_knowledge_optimizer|continuous_optimizer|lude.optimization)" | grep -v grep | awk '{print $1}')
    
    if [ -n "$orphan_pids" ]; then
        echo "发现可能遗漏的优化相关进程: $orphan_pids"
        echo "是否终止这些进程? [Y/n] "
        read -r confirm
        if [[ "$confirm" =~ ^[Nn]$ ]]; then
            echo "已跳过终止这些进程"
        else
            for pid in $orphan_pids; do
                echo "终止进程 $pid..."
                kill $pid 2>/dev/null
                sleep 1
                if ps -p $pid > /dev/null 2>&1; then
                    kill -9 $pid 2>/dev/null
                fi
            done
            echo "遗漏进程清理完成"
        fi
    else
        echo "未发现任何遗漏的优化进程"
    fi
    
    echo ""
    echo "===== 停止服务结果汇总 ====="
    echo "总工作区数量: $total_count"
    echo "成功停止服务数量: $stopped_count"
    if [ $((total_count - stopped_count)) -gt 0 ]; then
        echo "停止失败服务数量: $((total_count - stopped_count))"
        echo "失败的工作区:$failed_workspaces"
        echo "请检查失败的服务并手动停止"
    fi
}

# 批量检查所有服务状态
check_all_services() {
    echo "开始批量检查服务状态..."
    
    # 记录运行中的服务数量
    local running_count=0
    local total_count=0
    
    # 寻找所有工作区目录
    local workspaces=$(find "$PROJECT_ROOT" -maxdepth 1 -type d -name "lude_*")
    
    if [ -z "$workspaces" ]; then
        echo "未找到任何工作区目录"
        return 1
    fi
    
    for workspace in $workspaces; do
        ((total_count++))
        check_status "$workspace"
        if [ $? -eq 0 ]; then
            ((running_count++))
        fi
    done
    
    echo ""
    echo "===== 服务状态汇总 ====="
    echo "总工作区数量: $total_count"
    echo "运行中服务数量: $running_count"
    echo "未运行服务数量: $((total_count - running_count))"
}

# 主函数
main() {
    # 检查参数数量
    if [ $# -eq 0 ]; then
        show_help
        exit 1
    fi
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            -s|--status)
                check_all_services
                exit $?
                ;;
            -k|--stop)
                check_all_services  # 先显示当前状态
                echo ""
                echo "确认要停止所有运行中的服务吗? [Y/n] "
                read -r confirm
                if [[ "$confirm" =~ ^[Nn]$ ]]; then
                    echo "操作已取消"
                else
                    stop_all_services
                fi
                exit $?
                ;;
            -h|--help|*)
                show_help
                exit 0
                ;;
        esac
        shift
    done
}

# 执行主函数
main "$@"
