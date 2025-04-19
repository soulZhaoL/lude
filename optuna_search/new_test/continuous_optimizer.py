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
from tqdm import tqdm
import sys

# 结果存储目录
RESULTS_DIR = "optimization_results"
BEST_MODELS_DIR = os.path.join(RESULTS_DIR, "best_models")
os.makedirs(BEST_MODELS_DIR, exist_ok=True)

# 全局最佳结果跟踪文件
BEST_RECORD_FILE = os.path.join(RESULTS_DIR, "best_record.json")

def load_best_record():
    """加载历史最佳记录"""
    if os.path.exists(BEST_RECORD_FILE):
        with open(BEST_RECORD_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}
    return {"best_cagr": 0, "best_model_path": "", "timestamp": ""}

def save_best_record(record):
    """保存最佳记录"""
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

def run_optimization(iterations=10, strategy="multistage", method="tpe", n_trials=1500, 
                     n_factors=3, start_date="20220729", end_date="20250328", 
                     price_min=100, price_max=150, hold_num=5, n_jobs=5, seed=42):
    """运行连续优化过程"""
    
    # 加载最佳记录
    best_record = load_best_record()
    print(f"历史最佳CAGR: {best_record['best_cagr']:.4f}, 记录时间: {best_record['timestamp']}")
    
    # 准备优化参数
    base_params = [
        "--strategy", strategy,
        "--method", method,
        "--n_trials", str(n_trials),
        "--n_factors", str(n_factors),
        "--start_date", start_date,
        "--end_date", end_date,
        "--price_min", str(price_min),
        "--price_max", str(price_max),
        "--hold_num", str(hold_num),
        "--n_jobs", str(n_jobs),
        "--seed", str(seed)  # 使用固定种子42，与single模式保持一致
    ]
    
    # 运行多次优化
    total_start_time = time.time()
    for i in range(iterations):
        print(f"\n============== 第 {i+1}/{iterations} 次优化 ==============")
        
        # 构建命令 - 不再使用随机种子
        cmd = ["python", "domain_knowledge_optimizer.py"] + base_params
        
        # 运行命令
        start_time = time.time()
        
        # 显示执行信息
        print(f"执行命令: {' '.join(cmd)}")
        print("正在执行...")
        print("-" * 50)
        
        # 创建一个线程用于显示执行时间
        stop_timer = False
        
        def show_elapsed_time():
            """显示已执行的时间"""
            elapsed = 0
            while not stop_timer:
                elapsed += 1
                print(f"\r已执行 {elapsed} 秒，请继续等待...", end="")
                sys.stdout.flush()
                time.sleep(1)
        
        # 启动计时器线程
        import threading
        timer_thread = threading.Thread(target=show_elapsed_time)
        timer_thread.daemon = True
        timer_thread.start()
        
        try:
            # 使用简单的subprocess.run来执行命令
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        finally:
            # 停止计时器线程
            stop_timer = True
            timer_thread.join(timeout=1)
            print()  # 打印一个换行符，避免后续输出在同一行
        
        # 计算执行时间
        elapsed_time = time.time() - start_time
        
        # 清除读秒行
        print("\r" + " " * 50 + "\r", end="")
        
        # 检查是否成功
        if process.returncode == 0:
            print(f"命令执行成功, 耗时: {elapsed_time:.2f} 秒")
            output = process.stdout
        else:
            print(f"命令执行失败, 耗时: {elapsed_time:.2f} 秒, 返回码: {process.returncode}")
            print("\n错误输出:")
            print(process.stderr)
            output = ""
            
        print("-" * 50)
        
        # 提取CAGR值
        current_cagr = extract_cagr_from_output(output)
        
        # 查找最新生成的模型文件
        latest_model = find_latest_model(os.path.join(RESULTS_DIR, f"best_model_{strategy}_{method}_{n_factors}factors_*.pkl"))
        
        if latest_model and current_cagr > 0:
            print(f"当前运行CAGR: {current_cagr:.4f}")
            
            # 如果优于历史最佳，更新记录
            if current_cagr > best_record["best_cagr"]:
                # 复制模型到最佳模型目录
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                best_model_path = os.path.join(BEST_MODELS_DIR, f"best_model_{strategy}_{n_factors}factors_{current_cagr:.4f}_{timestamp}.pkl")
                
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
                    "seed": seed
                }
                save_best_record(best_record)
                print(f"发现新的最佳结果! CAGR: {current_cagr:.4f}")
                print(f"已保存到: {best_model_path}")
            else:
                print(f"未超过历史最佳 ({best_record['best_cagr']:.4f})")
        
        # 计算执行时间
        elapsed = time.time() - start_time
        print(f"本次运行用时: {elapsed/60:.2f} 分钟")
    
    total_elapsed = time.time() - total_start_time
    print("\n============== 优化完成 ==============")
    print(f"历史最佳CAGR: {best_record['best_cagr']:.4f}")
    print(f"最佳模型路径: {best_record['best_model_path']}")
    print(f"发现时间: {best_record['timestamp']}")
    print(f"总耗时: {total_elapsed/60:.2f} 分钟")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='可转债多因子持续优化程序')
    parser.add_argument('--iterations', type=int, default=10, help='连续优化次数')
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
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    
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
        seed=args.seed
    )

if __name__ == "__main__":
    main()
