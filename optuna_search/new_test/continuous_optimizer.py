#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import time
import subprocess
import json
import glob
import sys
import importlib.util
import threading
import re
import sys

# 添加项目根目录到路径，确保能导入util目录下的模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# 导入钉钉推送模块
try:
    from util.dingtalk.ding_talk_manager import DingTalkManager
    ding_talk_available = True
except ImportError:
    ding_talk_available = False
    print("未找到钉钉推送模块，将不会发送推送消息")

# 设置环境变量，确保Python输出不被缓存
os.environ['PYTHONUNBUFFERED'] = '1'

# 结果存储目录
RESULTS_DIR = "optimization_results"
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
        with open(BEST_RECORD_FILE, 'r') as f:
            try:
                global_best_record = json.load(f)
                return global_best_record
            except:
                return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}
    return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}

def save_best_record(record):
    """保存最佳记录"""
    global global_best_record
    global_best_record = record
    with open(BEST_RECORD_FILE, 'w') as f:
        json.dump(record, f, indent=4)

def find_latest_model(pattern):
    """查找最新的模型文件"""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def extract_cagr_from_output(output):
    """从输出中提取CAGR值"""
    try:
        # 查找多阶段优化的第二阶段结果
        second_stage_cagr = 0.0
        for line in output.split('\n'):
            if "第二阶段结果" in line and "优于第一阶段" in line:
                try:
                    # 提取格式为"第二阶段结果 (0.2702) 优于第一阶段 (0.2215)"中的第一个括号内数字
                    match = re.search(r"第二阶段结果 \(([0-9.]+)\)", line)
                    if match:
                        second_stage_cagr = float(match.group(1))
                except Exception as e:
                    print(f"提取第二阶段CAGR时出错: {e}")
        
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
        print(f"提取CAGR时出错: {e}")
        return 0
    
    return 0

def extract_best_factors_from_output(output):
    """从输出中提取最佳因子组合"""
    try:
        # 保存所有找到的因子组合
        all_factor_sets = []
        
        # 将输出按行分割
        lines = output.split('\n')
        
        # 遍历所有行寻找最佳因子组合部分
        i = 0
        while i < len(lines):
            line = lines[i]
            # 寻找因子组合的开始标记
            if "最佳因子组合" in line or "第二阶段最佳因子组合" in line:
                current_factors = []
                i += 1  # 移到下一行
                
                # 逐行解析因子数据，直到遇到空行或分隔线
                while i < len(lines) and not (lines[i].strip() == "" or "=" * 10 in lines[i]):
                    line = lines[i]
                    
                    # 尝试匹配因子行，格式类似于 "  1. factor_name"
                    factor_match = re.search(r"\s+\d+\.\s+([^\s]+)", line)
                    if factor_match:
                        factor_name = factor_match.group(1)
                        
                        # 初始化权重和排序方向
                        weight = 1
                        ascending = False
                        
                        # 向后查找权重和排序方向信息
                        if i + 1 < len(lines) and "权重" in lines[i + 1]:
                            weight_line = lines[i + 1]
                            weight_match = re.search(r"权重:\s+(\d+(\.\d+)?)", weight_line)
                            if weight_match:
                                weight = float(weight_match.group(1))
                                i += 1  # 移过权重行
                        
                        # 向后查找排序方向信息
                        if i + 1 < len(lines) and "排序方向" in lines[i + 1]:
                            direction_line = lines[i + 1]
                            direction_match = re.search(r"排序方向:\s+(.+)", direction_line)
                            if direction_match:
                                direction = direction_match.group(1)
                                ascending = "升序" in direction
                                i += 1  # 移过排序方向行
                        
                        # 添加解析出的因子信息
                        current_factors.append({
                            "name": factor_name,
                            "weight": weight,
                            "ascending": ascending
                        })
                    
                    i += 1
                
                # 如果找到了因子，保存这组因子
                if current_factors:
                    all_factor_sets.append(current_factors)
            else:
                i += 1
        
        # 返回最后一组找到的因子（优先返回第二阶段结果）
        if all_factor_sets:
            return all_factor_sets[-1]
        
        return []
    except Exception as e:
        print(f"提取最佳因子组合时出错: {e}")
        return []

def send_optimization_result_to_dingtalk(cagr, factors, seed=None, strategy=None, 
                                        n_factors=None, start_date=None, end_date=None,
                                        price_min=None, price_max=None, hold_num=None):
    """发送优化结果到钉钉
    
    Args:
        cagr: 年化收益率
        factors: 因子列表
        seed: 随机种子
        strategy: 优化策略
        n_factors: 因子数量
        start_date: 回测开始日期
        end_date: 回测结束日期
        price_min: 价格下限
        price_max: 价格上限
        hold_num: 持仓数量
    
    Returns:
        bool: 是否成功发送
    """
    if not ding_talk_available:
        print("钉钉推送模块不可用，跳过推送")
        return False
    
    try:
        # 获取钉钉管理器实例
        ding_manager = DingTalkManager.get_instance()
        
        # 构造消息内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seed_info = f"(种子: {seed})" if seed else ""
        strategy_info = f"策略: {strategy}" if strategy else ""
        
        # 构造优化参数信息
        params_info = "\n\n【优化参数】"
        if n_factors is not None:
            params_info += f"\n因子数量: {n_factors}"
        if start_date is not None and end_date is not None:
            params_info += f"\n回测区间: {start_date} 至 {end_date}"
        if price_min is not None and price_max is not None:
            params_info += f"\n价格区间: {price_min} 至 {price_max}"
        if hold_num is not None:
            params_info += f"\n持仓数量: {hold_num}"
        
        # 如果没有任何参数，则不显示参数部分
        if params_info == "\n\n【优化参数】":
            params_info = ""
        
        # 构造因子信息
        factors_info = ""
        if factors:
            factors_info = "\n\n【最佳因子组合】"
            for i, factor in enumerate(factors):
                direction = "升序" if factor.get('ascending', False) else "降序"
                weight = factor.get('weight', 1)
                factors_info += f"\n{i+1}. {factor['name']} (权重: {weight}, {direction})"
        
        # 完整消息
        message = f"【可转债优化新结果】{current_time}\n\n" \
                  f"年化收益率(CAGR): {cagr:.6f} {seed_info}\n" \
                  f"{strategy_info}" \
                  f"{params_info}" \
                  f"{factors_info}"
        
        # 发送消息
        print("正在发送钉钉推送...")
        result = ding_manager.send_message(
            message=message,
            prefix="优化结果",
            is_at_all=False
        )
        
        if result:
            print("钉钉推送发送成功")
        else:
            print("钉钉推送发送失败")
        
        return result
    except Exception as e:
        print(f"发送钉钉推送时出错: {e}")
        return False

def show_progress(seconds=10):
    """显示简单的进度指示器"""
    chars = "|/-\\"
    for i in range(seconds * 2):
        sys.stdout.write('\r' + f"执行中... {chars[i % 4]} ")
        sys.stdout.flush()
        time.sleep(0.5)
    print("\r" + " " * 30, end="\r")

def import_optimizer_module():
    """动态导入优化器模块"""
    try:
        spec = importlib.util.spec_from_file_location(
            "domain_optimizer", 
            os.path.join(os.path.dirname(__file__), "domain_knowledge_optimizer.py")
        )
        if not spec:
            print("无法加载domain_knowledge_optimizer.py模块，将使用子进程方式")
            return None
            
        domain_optimizer = importlib.util.module_from_spec(spec)
        sys.modules["domain_optimizer"] = domain_optimizer
        spec.loader.exec_module(domain_optimizer)
        return domain_optimizer
    except Exception as e:
        print(f"导入优化器模块失败: {e}，将使用子进程方式")
        return None

def run_optimization(iterations=10, strategy="multistage", method="tpe", n_trials=3000, 
                     n_factors=3, start_date="20220729", end_date="20250328", 
                     price_min=100, price_max=150, hold_num=5, n_jobs=15,
                     seed_start=42, seed_step=1000):
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
    """
    
    # 加载最佳记录
    best_record = load_best_record()
    print(f"历史最佳CAGR: {best_record['best_cagr']:.6f}, 记录时间: {best_record['timestamp']}")
    
    # 尝试导入优化器模块
    optimizer_module = import_optimizer_module()
    
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
        "n_jobs": n_jobs
    }
    
    # 运行多次优化
    total_start_time = time.time()
    for i in range(iterations):
        # 使用规律变化的种子
        current_seed = seed_start + i * seed_step
        
        print(f"\n============== 第 {i+1}/{iterations} 次优化 (种子: {current_seed}) ==============")
        
        # 更新参数
        current_params = base_params.copy()
        current_params["seed"] = current_seed
        
        # 开始计时
        start_time = time.time()
        
        # 显示执行信息
        param_str = " ".join([f"--{k} {v}" for k, v in current_params.items()])
        print(f"执行优化，参数: {param_str}")
        print("正在执行...")
        print("-" * 50)
        
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
            cmd = ["python", "domain_knowledge_optimizer.py"]
            for key, value in current_params.items():
                cmd.extend([f"--{key}", str(value)])
            
            # 在新进程中运行命令，但不实时显示输出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )
            
            # 使用非阻塞方式读取输出，避免死锁
            import select
            collected_output = []
            collected_errors = []
            
            # 设置非阻塞模式
            import fcntl
            import os
            
            # 设置stdout为非阻塞模式
            flags = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
            fcntl.fcntl(process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # 设置stderr为非阻塞模式
            flags = fcntl.fcntl(process.stderr, fcntl.F_GETFL)
            fcntl.fcntl(process.stderr, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # 使用select进行非阻塞读取
            while process.poll() is None:
                # 等待数据可读取，最多等待0.1秒
                reads = [process.stdout, process.stderr]
                ret = select.select(reads, [], [], 0.1)
                
                # 循环处理可读取的文件描述符
                for fd in ret[0]:
                    if fd == process.stdout:
                        line = fd.readline()
                        if line:
                            collected_output.append(line)
                    if fd == process.stderr:
                        line = fd.readline()
                        if line:
                            collected_errors.append(line)
            
            # 读取剩余的输出
            for line in process.stdout:
                collected_output.append(line)
            for line in process.stderr:
                collected_errors.append(line)
            
            # 等待进程结束
            return_code = process.wait()
            
            # 合并所有输出
            output = ''.join(collected_output)
            errors = ''.join(collected_errors)
            success = (return_code == 0)
            
        finally:
            # 停止计时器线程
            stop_timer = True
            timer_thread.join(timeout=1)
            print()  # 打印一个换行符，避免后续输出在同一行
        
        # 计算执行时间
        elapsed_time = time.time() - start_time
        
        # 清除读秒行
        print("\r" + " " * 50 + "\r", end="")
        
        # 检查是否成功并显示结果
        if success:
            print(f"命令执行成功, 耗时: {elapsed_time:.2f} 秒")
            
            # 提取并显示重要结果
            important_results = extract_important_results(output)
            if important_results:
                print("\n关键优化结果:")
                print("-" * 50)
                print(important_results)
        else:
            print(f"命令执行失败, 耗时: {elapsed_time:.2f} 秒")
            print("\n错误输出:")
            print(errors)
            
        print("-" * 50)

        # 提取CAGR值
        current_cagr = extract_cagr_from_output(output)
        
        # 提取最佳因子组合
        best_factors = extract_best_factors_from_output(output)
        
        # 查找最新生成的模型文件
        latest_model = find_latest_model(os.path.join(RESULTS_DIR, f"best_model_{strategy}_{method}_{n_factors}factors_*.pkl"))
        
        if latest_model and current_cagr > 0:
            print(f"当前运行CAGR: {current_cagr:.6f} (种子: {current_seed})")
            
            # 如果优于历史最佳，更新记录
            if current_cagr > best_record["best_cagr"]:
                # 复制模型到最佳模型目录
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                best_model_path = os.path.join(BEST_MODELS_DIR, f"best_model_{strategy}_{n_factors}factors_{current_cagr:.6f}_{timestamp}.pkl")
                
                # 复制最新模型到最佳模型目录
                import shutil
                shutil.copy2(latest_model, best_model_path)
                
                # 更新最佳记录
                best_record = {
                    "best_cagr": current_cagr,
                    "best_model_path": best_model_path,
                    "timestamp": timestamp,
                    "strategy": strategy,
                    "method": method,
                    "n_factors": n_factors,
                    "price_range": f"{price_min}-{price_max}",
                    "hold_num": hold_num,
                    "seed": current_seed
                }
                save_best_record(best_record)
                print(f"发现新的最佳结果! CAGR: {current_cagr:.6f}")
                
                # 打印因子组合信息
                if best_factors:
                    print("\n最佳因子组合:")
                    for i, factor in enumerate(best_factors):
                        direction = "升序" if factor.get('ascending', False) else "降序"
                        weight = factor.get('weight', 1)
                        print(f"  {i+1}. {factor['name']} (权重: {weight}, {direction})")
                    print()  # 添加一个空行
                
                print(f"已保存到: {best_model_path}")
                
                # 发送钉钉推送
                send_optimization_result_to_dingtalk(current_cagr, best_factors, seed=current_seed, strategy=strategy,
                                                    n_factors=n_factors, start_date=start_date, end_date=end_date,
                                                    price_min=price_min, price_max=price_max, hold_num=hold_num)
            else:
                print(f"未超过历史最佳 ({best_record['best_cagr']:.6f})")
        
        # 计算执行时间
        elapsed = time.time() - start_time
        print(f"本次运行用时: {elapsed/60:.2f} 分钟")
    
    total_elapsed = time.time() - total_start_time
    print("\n============== 优化完成 ==============")
    print(f"历史最佳CAGR: {best_record['best_cagr']:.6f}")
    print(f"最佳模型路径: {best_record['best_model_path']}")
    print(f"发现时间: {best_record['timestamp']}")
    print(f"总耗时: {total_elapsed/60:.2f} 分钟")

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
    parser.add_argument('--n_factors', type=int, default=3, choices=[3, 4, 5], help='因子数量')
    parser.add_argument('--start_date', type=str, default='20220729', help='回测开始日期')
    parser.add_argument('--end_date', type=str, default='20250328', help='回测结束日期')
    parser.add_argument('--price_min', type=int, default=100, help='价格下限')
    parser.add_argument('--price_max', type=int, default=150, help='价格上限')
    parser.add_argument('--hold_num', type=int, default=5, help='持仓数量')
    parser.add_argument('--n_jobs', type=int, default=15, help='并行任务数')
    parser.add_argument('--seed_start', type=int, default=42, help='起始随机种子')
    parser.add_argument('--seed_step', type=int, default=1000, help='种子递增步长')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    run_optimization(
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
        seed_step=args.seed_step
    )

if __name__ == "__main__":
    main()
