#!/bin/bash
# Redis快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 显示帮助信息
show_help() {
    echo -e "${BLUE}Redis for Optuna - 快速启动脚本${NC}"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  dev      启动开发环境Redis (1GB内存, 端口6379)"
    echo "  prod     启动生产环境Redis (3GB内存, 端口6380)"
    echo "  monitor  启动Redis + 监控面板"
    echo "  stop     停止所有Redis服务"
    echo "  restart  重启Redis服务"
    echo "  status   查看服务状态"
    echo "  logs     查看服务日志"
    echo "  test     测试Redis连接"
    echo "  clean    清理所有数据和容器"
    echo "  help     显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 dev     # 启动开发环境"
    echo "  $0 prod    # 启动生产环境"
    echo "  $0 test    # 测试连接"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker未安装，请先安装Docker${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}错误: docker-compose未安装，请先安装docker-compose${NC}"
        exit 1
    fi
}

# 启动开发环境
start_dev() {
    echo -e "${BLUE}启动开发环境Redis...${NC}"
    docker-compose up -d redis-dev
    
    echo -e "${YELLOW}等待Redis启动...${NC}"
    sleep 3
    
    if docker exec optuna-redis-dev redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ 开发环境Redis启动成功!${NC}"
        echo -e "连接信息: ${YELLOW}localhost:6379${NC}"
        echo -e "测试连接: ${YELLOW}docker exec optuna-redis-dev redis-cli ping${NC}"
    else
        echo -e "${RED}❌ Redis启动失败，请检查日志${NC}"
        docker logs optuna-redis-dev
        exit 1
    fi
}

# 启动生产环境
start_prod() {
    echo -e "${BLUE}启动生产环境Redis...${NC}"
    docker-compose up -d redis-prod
    
    echo -e "${YELLOW}等待Redis启动...${NC}"
    sleep 5
    
    if docker exec optuna-redis-prod redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ 生产环境Redis启动成功!${NC}"
        echo -e "连接信息: ${YELLOW}localhost:6380${NC}"
        echo -e "内存配置: ${YELLOW}3GB${NC}"
        echo -e "测试连接: ${YELLOW}docker exec optuna-redis-prod redis-cli ping${NC}"
    else
        echo -e "${RED}❌ Redis启动失败，请检查日志${NC}"
        docker logs optuna-redis-prod
        exit 1
    fi
}

# 启动监控
start_monitor() {
    echo -e "${BLUE}启动Redis + 监控面板...${NC}"
    docker-compose up -d redis-prod redis-insight
    
    echo -e "${YELLOW}等待服务启动...${NC}"
    sleep 8
    
    if docker exec optuna-redis-prod redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis + 监控启动成功!${NC}"
        echo -e "Redis连接: ${YELLOW}localhost:6380${NC}"
        echo -e "监控面板: ${YELLOW}http://localhost:8001${NC}"
        echo -e "打开浏览器访问监控面板进行配置"
    else
        echo -e "${RED}❌ 服务启动失败${NC}"
        exit 1
    fi
}

# 停止服务
stop_services() {
    echo -e "${BLUE}停止所有Redis服务...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ 服务已停止${NC}"
}

# 重启服务
restart_services() {
    echo -e "${BLUE}重启Redis服务...${NC}"
    docker-compose restart
    sleep 3
    echo -e "${GREEN}✅ 服务已重启${NC}"
}

# 查看状态
show_status() {
    echo -e "${BLUE}Redis服务状态:${NC}"
    echo ""
    docker-compose ps
    echo ""
    
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(redis|optuna)" | grep -q "Up"; then
        echo -e "${GREEN}✅ 有Redis服务正在运行${NC}"
        
        # 检查开发环境
        if docker ps | grep -q "optuna-redis-dev"; then
            echo -e "开发环境: ${GREEN}运行中${NC} (端口: 6379)"
            if docker exec optuna-redis-dev redis-cli ping &> /dev/null; then
                echo -e "  连接状态: ${GREEN}正常${NC}"
            else
                echo -e "  连接状态: ${RED}异常${NC}"
            fi
        fi
        
        # 检查生产环境
        if docker ps | grep -q "optuna-redis-prod"; then
            echo -e "生产环境: ${GREEN}运行中${NC} (端口: 6380)"
            if docker exec optuna-redis-prod redis-cli ping &> /dev/null; then
                echo -e "  连接状态: ${GREEN}正常${NC}"
                # 显示内存使用
                memory_info=$(docker exec optuna-redis-prod redis-cli info memory | grep used_memory_human)
                echo -e "  内存使用: ${YELLOW}${memory_info#*:}${NC}"
            else
                echo -e "  连接状态: ${RED}异常${NC}"
            fi
        fi
        
        # 检查监控面板
        if docker ps | grep -q "redis-insight"; then
            echo -e "监控面板: ${GREEN}运行中${NC} (http://localhost:8001)"
        fi
    else
        echo -e "${YELLOW}⚠️  没有Redis服务在运行${NC}"
    fi
}

# 查看日志
show_logs() {
    echo -e "${BLUE}选择要查看的日志:${NC}"
    echo "1) 开发环境Redis"
    echo "2) 生产环境Redis"
    echo "3) 监控面板"
    read -p "请选择 (1-3): " choice
    
    case $choice in
        1)
            echo -e "${BLUE}开发环境Redis日志:${NC}"
            docker logs -f optuna-redis-dev
            ;;
        2)
            echo -e "${BLUE}生产环境Redis日志:${NC}"
            docker logs -f optuna-redis-prod
            ;;
        3)
            echo -e "${BLUE}监控面板日志:${NC}"
            docker logs -f redis-insight
            ;;
        *)
            echo -e "${RED}无效选择${NC}"
            ;;
    esac
}

# 测试连接
test_connection() {
    echo -e "${BLUE}测试Redis连接...${NC}"
    
    # 测试开发环境
    if docker ps | grep -q "optuna-redis-dev"; then
        echo -e "\n${YELLOW}测试开发环境 (端口6379):${NC}"
        if docker exec optuna-redis-dev redis-cli ping &> /dev/null; then
            echo -e "  基础连接: ${GREEN}✅ 成功${NC}"
            
            # 测试写入读取
            docker exec optuna-redis-dev redis-cli set test_key "Hello Optuna" > /dev/null
            result=$(docker exec optuna-redis-dev redis-cli get test_key)
            if [ "$result" = "Hello Optuna" ]; then
                echo -e "  读写测试: ${GREEN}✅ 成功${NC}"
            else
                echo -e "  读写测试: ${RED}❌ 失败${NC}"
            fi
            docker exec optuna-redis-dev redis-cli del test_key > /dev/null
        else
            echo -e "  基础连接: ${RED}❌ 失败${NC}"
        fi
    fi
    
    # 测试生产环境
    if docker ps | grep -q "optuna-redis-prod"; then
        echo -e "\n${YELLOW}测试生产环境 (端口6380):${NC}"
        if docker exec optuna-redis-prod redis-cli ping &> /dev/null; then
            echo -e "  基础连接: ${GREEN}✅ 成功${NC}"
            
            # 测试写入读取
            docker exec optuna-redis-prod redis-cli set test_key "Hello Optuna Prod" > /dev/null
            result=$(docker exec optuna-redis-prod redis-cli get test_key)
            if [ "$result" = "Hello Optuna Prod" ]; then
                echo -e "  读写测试: ${GREEN}✅ 成功${NC}"
            else
                echo -e "  读写测试: ${RED}❌ 失败${NC}"
            fi
            docker exec optuna-redis-prod redis-cli del test_key > /dev/null
            
            # 显示性能信息
            echo -e "  性能信息:"
            memory_info=$(docker exec optuna-redis-prod redis-cli info memory | grep used_memory_human)
            echo -e "    内存使用: ${YELLOW}${memory_info#*:}${NC}"
            
            clients_info=$(docker exec optuna-redis-prod redis-cli info clients | grep connected_clients)
            echo -e "    连接数: ${YELLOW}${clients_info#*:}${NC}"
        else
            echo -e "  基础连接: ${RED}❌ 失败${NC}"
        fi
    fi
    
    if ! docker ps | grep -q -E "(optuna-redis-dev|optuna-redis-prod)"; then
        echo -e "\n${YELLOW}⚠️  没有Redis服务在运行${NC}"
        echo -e "请先运行: ${BLUE}$0 dev${NC} 或 ${BLUE}$0 prod${NC}"
    fi
}

# 清理数据和容器
clean_all() {
    echo -e "${RED}⚠️  警告: 这将删除所有Redis数据和容器!${NC}"
    read -p "确定要继续吗? (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}清理所有数据和容器...${NC}"
        docker-compose down -v --remove-orphans
        docker system prune -f
        echo -e "${GREEN}✅ 清理完成${NC}"
    else
        echo -e "${YELLOW}操作已取消${NC}"
    fi
}

# 主逻辑
main() {
    # 检查Docker
    check_docker
    
    case "${1:-help}" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "monitor")
            start_monitor
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "test")
            test_connection
            ;;
        "clean")
            clean_all
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

main "$@"