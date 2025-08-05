#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import joblib
from datetime import datetime
import time
import subprocess
import json
import glob
import importlib.util
import threading
import sys
import re
from lude.utils.logger import optimization_logger as logger

# 设置环境变量，确保Python输出不被缓存
os.environ['PYTHONUNBUFFERED'] = '1'

from lude.config.paths import RESULTS_DIR  # 导入结果目录常量

# 结果存储目录
BEST_MODELS_DIR = os.path.join(RESULTS_DIR, "best_models")
os.makedirs(BEST_MODELS_DIR, exist_ok=True)

# 全局最佳结果跟踪文件
BEST_RECORD_FILE = os.path.join(RESULTS_DIR, "best_record.json")

# 全局变量，避免频繁文件读写
global_best_record = {"best_cagr": 0, "best_model_path": "", "timestamp": ""}

def load_best_record():
    """加载历史最佳记录"""
    global global_best_record
    if os.path.exists(BEST_RECORD_FILE):
        with open(BEST_RECORD_FILE, 'r', encoding='utf-8') as f:
            try:
                loaded_record = json.load(f)
                
                # 向后兼容：如果是旧格式（使用factors字段），转换为新格式
                if 'factors' in loaded_record and 'rank_factors' not in loaded_record:
                    loaded_record['rank_factors'] = loaded_record.pop('factors')
                    logger.info("已将旧格式的factors字段转换为rank_factors")
                
                # 如果没有filter_conditions字段，添加空数组
                if 'filter_conditions' not in loaded_record:
                    loaded_record['filter_conditions'] = []
                    logger.info("为历史记录添加空的filter_conditions字段")
                
                global_best_record = loaded_record
                return global_best_record
            except:
                return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}
    return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}

def save_best_record(record):
    """保存最佳记录"""
    global global_best_record
    global_best_record = record
    with open(BEST_RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=4, ensure_ascii=False)

def find_latest_model(pattern=None):
    """查找最新的模型文件
    
    Args:
        pattern: 文件名匹配模式，默认查找所有模型文件
        
    Returns:
        最新模型文件的路径，如果没有找到则返回None
    """
    if pattern is None:
        # 默认查找所有joblib文件
        pattern = "*.joblib"
    
    files = glob.glob(os.path.join(RESULTS_DIR, pattern))
    if files:
        return max(files, key=os.path.getctime)
    return None

def extract_cagr_from_output(output):
    """从输出中提取CAGR值"""
    try:
        # 查找多阶段优化的第二阶段结果
        second_stage_cagr = 0.0
        for line in output.split('\n'):
            if "第二阶段结果" in line and ("优于第一阶段" in line or "基本相同" in line):
                try:
                    # 提取格式为"第二阶段结果 (0.2702) 优于第一阶段 (0.2215)"或"第二阶段结果 (0.391601) 与第一阶段 (0.391601) 基本相同"中的第一个括号内数字
                    match = re.search(r"第二阶段结果 \(([0-9.]+)\)", line)
                    if match:
                        second_stage_cagr = float(match.group(1))
                        logger.info(f"成功提取第二阶段CAGR: {second_stage_cagr}")
                except Exception as e:
                    logger.error(f"提取第二阶段CAGR时出错: {e}")
        
        if second_stage_cagr > 0:
            return second_stage_cagr
            
        # 优先查找"最佳年化收益率"（最终结果）
        final_cagr = 0.0
        for line in output.split('\n'):
            if "最佳年化收益率" in line:
                try:
                    cagr_value = float(line.split(":")[1].strip())
                    # 记录找到的最大CAGR值
                    final_cagr = max(final_cagr, cagr_value)
                except:
                    pass
        
        if final_cagr > 0:
            return final_cagr
            
        # 如果没找到标准格式，尝试查找"best_value"
        for line in output.split('\n'):
            if "Best value:" in line:
                try:
                    cagr_str = line.split("Best value:")[1].split(":")[0].strip()
                    return float(cagr_str)
                except:
                    pass
    except Exception as e:
        logger.error(f"提取CAGR时出错: {e}")
        return 0
    
    return 0


def show_progress(seconds=10):
    """显示简单的进度指示器"""
    chars = "|/-\\"
    for i in range(seconds * 2):
        sys.stdout.write('\r' + f"执行中... {chars[i % 4]} ")
        sys.stdout.flush()
        time.sleep(0.5)
    print("\r" + " " * 30, end="\r")

def run_continuous_optimization(iterations=10, strategy="multistage", method="tpe", n_trials=3000, 
                     n_factors=3, start_date="20220729", end_date="20250328", 
                     price_min=100, price_max=150, hold_num=5, n_jobs=15,
                     seed_start=42, seed_step=1000, workspace_id='', enable_filter_opt=False):
    """运行连续优化过程，使用改进的低开销方法
    
    Args:
        iterations: 优化迭代次数
        strategy: 优化策略(multistage, domain, prescreen, filter)
        method: 优化方法(tpe, random, cmaes)
        n_trials: 每次优化的迭代次数
        n_factors: 因子数量
        start_date: 回测开始日期
        end_date: 回测结束日期
        price_min: 价格下限
        price_max: 价格上限
        hold_num: 持仓数量
        n_jobs: 并行任务数
        seed_start: 起始种子值
        seed_step: 种子递增步长
        workspace_id: 工作区ID标识
        enable_filter_opt: 是否启用过滤因子组合优化
    """
    
    # 加载最佳记录
    best_record = load_best_record()
    logger.info(f"历史最佳CAGR: {best_record['best_cagr']:.6f}, 记录时间: {best_record['timestamp']}")
    
    # 准备基础优化参数（不包含种子）
    base_params = {
        "strategy": strategy,
        "method": method,
        "n_trials": n_trials,
        "n_factors": n_factors,
        "start_date": start_date,
        "end_date": end_date,
        "price_min": price_min,
        "price_max": price_max,
        "hold_num": hold_num,
        "n_jobs": n_jobs,
        "workspace_id": workspace_id,
        "enable_filter_opt": enable_filter_opt
    }
    
    # 运行多次优化
    total_start_time = time.time()
    for i in range(iterations):
        # 使用规律变化的种子
        current_seed = seed_start + i * seed_step
        
        logger.info(f"============== 第 {i+1}/{iterations} 次优化 (种子: {current_seed}) ==============")
        
        # 更新参数
        current_params = base_params.copy()
        current_params["seed"] = current_seed
        
        # 开始计时
        start_time = time.time()
        
        # 显示执行信息
        param_str = " ".join([f"--{k} {v}" for k, v in current_params.items()])
        logger.info(f"执行优化，参数: {param_str}")
        logger.info("正在执行...")
        logger.info("-" * 50)
        
        output = ""
        current_cagr = 0
        
        # 定义进度显示线程
        stop_timer = False
        
        def show_elapsed_time():
            """显示已执行的时间"""
            elapsed = 0
            while not stop_timer:
                elapsed += 1
                print(f"\r已执行 {elapsed} 秒...", end="")
                sys.stdout.flush()
                time.sleep(1)
        
        # 启动计时器线程
        timer_thread = threading.Thread(target=show_elapsed_time)
        timer_thread.daemon = True
        timer_thread.start()
        
        try:
            # 使用子进程方式执行，更稳定可靠
            # 注意：使用模块化路径 (-m) 而不是直接调用文件
            cmd = ["python", "-m", "lude.optimization.unified_optimizer", "--mode", "single"]
            for key, value in current_params.items():
                if key == "enable_filter_opt":
                    # 特殊处理：enable_filter_opt 为 store_true 类型，只有为 True 时才添加参数
                    if value:
                        cmd.append("--enable_filter_opt")
                else:
                    # 普通参数：直接添加 key 和 value
                    cmd.extend([f"--{key}", str(value)])
                
            # 打印完整命令用于调试
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 设置合理的超时时间，根据试验次数和并发数动态调整
            # 基础超时时间：2小时，对于大量试验增加时间
            base_timeout = 7200  # 2小时
            trials_factor = min(current_params.get('n_trials', 1000) / 1000, 3)  # 最多3倍
            jobs_factor = min(current_params.get('n_jobs', 15) / 15, 2)  # 并发越高，单个任务可能越慢
            
            timeout_seconds = int(base_timeout * trials_factor * jobs_factor)
            logger.info(f"设置超时时间: {timeout_seconds} 秒 ({timeout_seconds/3600:.1f} 小时)")
            
            result = subprocess.run(cmd, 
                                   capture_output=True, 
                                   text=True, 
                                   timeout=timeout_seconds,
                                   cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            
            output = result.stdout + result.stderr
            
            # 停止计时器
            stop_timer = True
            timer_thread.join(1)
            
            # 计算执行时间
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 检查执行结果
            if result.returncode == 0:
                logger.info(f"命令执行成功, 耗时: {elapsed:.2f} 秒")
                # 提取CAGR
                current_cagr = extract_cagr_from_output(output)
                
                # 如果发现更好的CAGR，更新记录
                if current_cagr > best_record['best_cagr']:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 保存模型文件
                    save_model_path = find_latest_model()
                    
                    # 从最新保存的模型文件中获取正确的因子信息，而不是解析文本输出
                    best_factors = []
                    best_filter_conditions = []
                    
                    if save_model_path and os.path.exists(save_model_path):
                        try:
                            import joblib
                            model_data = joblib.load(save_model_path)
                            
                            # 从模型文件中获取正确的因子信息
                            if 'best_rank_factors' in model_data:
                                best_factors = model_data['best_rank_factors']
                                logger.info(f"从模型文件中获取到 {len(best_factors)} 个打分因子")
                            
                            if 'best_filter_conditions' in model_data:
                                best_filter_conditions = model_data['best_filter_conditions']
                                logger.info(f"从模型文件中获取到 {len(best_filter_conditions)} 个排除因子条件")
                                
                        except Exception as e:
                            logger.error(f"从模型文件读取因子信息失败: {e}")
                    else:
                        logger.warning(f"模型文件不存在，无法获取因子信息: {save_model_path}")
                    
                    if save_model_path:
                        # 复制到最佳模型目录
                        file_ext = os.path.splitext(save_model_path)[1]  # 获取原始文件扩展名
                        new_model_path = os.path.join(
                            BEST_MODELS_DIR, 
                            f"best_model_cagr{current_cagr:.6f}_seed{current_seed}_{timestamp.replace(':', '-').replace(' ', '_')}{file_ext}"
                        )
                        try:
                            import shutil
                            shutil.copy2(save_model_path, new_model_path)
                            logger.info(f"已保存最佳模型: {new_model_path}")
                            
                            # 更新全局记录
                            best_record = {
                                "best_cagr": current_cagr,
                                "best_model_path": new_model_path,
                                "timestamp": timestamp,
                                "rank_factors": best_factors,  # 重命名为更明确的名称
                                "filter_conditions": best_filter_conditions,  # 添加排除因子信息
                                "parameters": current_params
                            }
                            save_best_record(best_record)
                        except Exception as e:
                            logger.error(f"保存最佳模型时出错: {e}")
                    else:
                        logger.warning("未找到模型文件，无法保存最佳模型")
                        
                        # 虽然没有模型文件，但仍然更新CAGR记录
                        best_record = {
                            "best_cagr": current_cagr,
                            "best_model_path": "",
                            "timestamp": timestamp,
                            "rank_factors": best_factors,  # 重命名为更明确的名称
                            "filter_conditions": best_filter_conditions,  # 添加排除因子信息
                            "parameters": current_params
                        }
                        save_best_record(best_record)
                
                # 打印提取到的重要结果
                important_results = extract_important_results(output)
                logger.info("\n==== 优化结果摘要 ====")
                logger.info(important_results)
                    
            else:
                logger.error(f"命令执行失败, 耗时: {elapsed:.2f} 秒")
                logger.error("\n错误输出:")
                logger.error(output.strip())
                
        except subprocess.TimeoutExpired as e:
            # 停止计时器
            stop_timer = True
            if timer_thread.is_alive():
                timer_thread.join(1)
                
            # 计算执行时间
            end_time = time.time()
            elapsed = end_time - start_time
            
            logger.error(f"\n命令执行超时, 耗时: {elapsed:.2f} 秒 (超过 {timeout_seconds} 秒限制)")
            logger.error(f"超时命令: {' '.join(cmd)}")
            logger.error("建议: 1) 减少trials数量 2) 减少jobs并发数 3) 检查数据量是否过大")
            
        except Exception as e:
            # 停止计时器
            stop_timer = True
            if timer_thread.is_alive():
                timer_thread.join(1)
                
            # 计算执行时间
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 打印详细的异常信息
            import traceback
            logger.error(f"\n执行过程中发生错误, 耗时: {elapsed:.2f} 秒")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误信息: {str(e)}")
            logger.error(f"执行命令: {' '.join(cmd)}")
            logger.error("详细错误堆栈:")
            logger.error(traceback.format_exc())
            
            # 如果是特定的内存错误，给出建议
            if "memory" in str(e).lower() or "killed" in str(e).lower():
                logger.error("可能是内存不足导致的错误，建议: 1) 减少jobs并发数 2) 减少数据量 3) 检查系统内存")
            elif "permission" in str(e).lower():
                logger.error("可能是权限问题，建议: 1) 检查文件权限 2) 检查conda环境激活 3) 检查工作目录权限")
            elif "module" in str(e).lower() or "import" in str(e).lower():
                logger.error("可能是模块导入问题，建议: 1) 检查conda环境 2) 检查包安装 3) 检查PYTHONPATH")
            elif "connection" in str(e).lower() or "redis" in str(e).lower():
                logger.error("可能是Redis连接问题，建议: 1) 检查Redis服务状态 2) 检查网络连接 3) 尝试重启Redis服务")

    total_elapsed = time.time() - total_start_time
    logger.info("\n============== 优化完成 ==============")
    logger.info(f"历史最佳CAGR: {best_record['best_cagr']:.6f}")
    logger.info(f"最佳模型路径: {best_record['best_model_path']}")
    logger.info(f"发现时间: {best_record['timestamp']}")
    logger.info(f"总耗时: {total_elapsed/60:.2f} 分钟")

    # 尝试从最佳记录中提取详细信息
    try:
        if 'model_details' in best_record and best_record['model_details']:
            details = best_record['model_details']

            logger.info("\n============== 最佳策略详情 ==============")

            # 打印最佳打分因子组合
            if 'rank_factors' in details:
                logger.info("📊 最佳打分因子组合:")
                for i, factor in enumerate(details['rank_factors']):
                    direction = "升序排列" if factor['ascending'] else "降序排列"
                    logger.info(f"  {i + 1}. {factor['name']} (权重: {factor['weight']}, {direction})")

            # 打印最佳排除因子组合
            if 'filter_conditions' in details and details['filter_conditions']:
                logger.info("\n🚫 最佳排除因子组合:")
                for i, condition in enumerate(details['filter_conditions']):
                    logger.info(f"  {i + 1}. {condition['factor']} {condition['operator']} {condition['value']}")
            else:
                logger.info("\n🚫 排除因子组合: 无")

            # 打印策略参数
            if 'strategy_params' in details:
                params = details['strategy_params']
                logger.info(f"\n⚙️ 策略参数:")
                logger.info(f"  - 回测期间: {params.get('start_date', 'N/A')} ~ {params.get('end_date', 'N/A')}")
                logger.info(f"  - 价格范围: {params.get('price_min', 'N/A')} ~ {params.get('price_max', 'N/A')}")
                logger.info(f"  - 持仓数量: {params.get('hold_num', 'N/A')} 只")

    except Exception as e:
        logger.warning(f"提取最佳策略详情时出错: {e}")
        logger.info("请查看最佳模型文件获取详细信息")

    logger.info("\n" + "=" * 50)

def extract_important_results(output):
    """从优化输出中提取重要结果"""
    important_lines = []
    
    # 定义关键字模式
    key_patterns = [
        "最佳年化收益率", 
        "最佳因子组合", 
        "前5个最佳组合",
        "Best value",
        "Best trial",
    ]
    
    # 跟踪是否在重要区域
    in_important_section = False
    section_lines = []
    
    for line in output.split('\n'):
        # 检查是否是重要行或在重要区域内
        is_important = any(pattern in line for pattern in key_patterns)
        
        if is_important:
            in_important_section = True
            section_lines = [line]  # 开始新区域
        elif in_important_section:
            if line.strip() == "" and len(section_lines) > 0:
                # 空行标志区域结束
                important_lines.extend(section_lines)
                important_lines.append("")  # 添加空行分隔
                in_important_section = False
                section_lines = []
            elif "=" * 20 in line:  # 分隔线
                section_lines.append(line)
                important_lines.extend(section_lines)
                important_lines.append("")
                in_important_section = False
                section_lines = []
            else:
                section_lines.append(line)
    
    # 添加最后一个区域（如果有）
    if section_lines:
        important_lines.extend(section_lines)
    
    return "\n".join(important_lines)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='可转债多因子持续优化程序')
    parser.add_argument('--iterations', type=int, default=10, help='持续优化次数')
    parser.add_argument('--strategy', type=str, default='multistage', 
                        choices=['domain', 'prescreen', 'multistage', 'filter'],
                        help='优化策略')
    parser.add_argument('--method', type=str, default='tpe', 
                        choices=['tpe', 'random', 'cmaes'],
                        help='优化方法')
    parser.add_argument('--n_trials', type=int, default=3000, help='每次优化的迭代次数')
    parser.add_argument('--n_factors', type=int, default=3, choices=[3, 4, 5, 6, 7], help='因子数量')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期')
    parser.add_argument('--price_min', type=int, default=100, help='价格下限')
    parser.add_argument('--price_max', type=int, default=150, help='价格上限')
    parser.add_argument('--hold_num', type=int, default=5, help='持仓数量')
    parser.add_argument('--n_jobs', type=int, default=15, help='并行任务数')
    parser.add_argument('--seed_start', type=int, default=42, help='起始随机种子')
    parser.add_argument('--seed_step', type=int, default=1000, help='种子递增步长')
    parser.add_argument('--workspace_id', type=str, default='', help='工作区ID标识，用于进程管理')
    parser.add_argument('--enable_filter_opt', action='store_true', help='启用过滤因子组合优化')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 设置进程标题，包含工作区ID
    try:
        import setproctitle
        if args.workspace_id:
            process_title = f"lude_optimizer_{args.workspace_id}"
            setproctitle.setproctitle(process_title)
            logger.info(f"进程标题已设置为: {process_title}")
    except ImportError:
        logger.warning("setproctitle模块未安装，无法设置进程标题")
    
    # 运行持续优化
    run_continuous_optimization(
        iterations=args.iterations,
        strategy=args.strategy,
        method=args.method,
        n_trials=args.n_trials,
        n_factors=args.n_factors,
        start_date=args.start_date,
        end_date=args.end_date,
        price_min=args.price_min,
        price_max=args.price_max,
        hold_num=args.hold_num,
        n_jobs=args.n_jobs,
        seed_start=args.seed_start,
        seed_step=args.seed_step,
        workspace_id=args.workspace_id,
        enable_filter_opt=args.enable_filter_opt
    )

if __name__ == "__main__":
    main()
