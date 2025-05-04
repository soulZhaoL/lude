#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import joblib
import pandas as pd
import numpy as np
import glob
import json
import argparse
from datetime import datetime

from lude.config.paths import RESULTS_DIR

# 结果存储目录
BEST_MODELS_DIR = os.path.join(RESULTS_DIR, "best_models")

def load_model(model_path):
    """加载模型文件"""
    try:
        model_data = joblib.load(model_path)
        return model_data
    except Exception as e:
        print(f"加载模型文件时出错: {e}")
        return None

def display_model_info(model_data, detailed=False):
    """显示模型信息"""
    if not model_data:
        print("模型数据为空，无法显示信息")
        return
    
    print("\n" + "="*60)
    print(f"模型文件: {os.path.basename(model_path)}")
    print("="*60)
    
    # 提取基本信息
    cagr = model_data.get("best_value", "未知")
    params = model_data.get("best_params", {})
    factors = model_data.get("factors", [])
    combinations = model_data.get("combinations", [])
    
    print(f"年化收益率 (CAGR): {cagr:.4f}")
    print("-"*60)
    
    # 方法0: 从 best_rank_factors 字段中提取 (优先级最高)
    if "best_rank_factors" in model_data:
        best_factors = model_data["best_rank_factors"]
        print("最佳因子组合:")
        for i, factor_info in enumerate(best_factors):
            if isinstance(factor_info, dict):
                factor = factor_info.get("name", "未知")
                weight = factor_info.get("weight", "未知")
                direction = "升序" if factor_info.get("ascending", False) else "降序"
                print(f"  {i+1}. {factor}")
                print(f"     - 权重: {weight}")
                print(f"     - 排序方向: {direction}")
        
        # 额外信息
        if "price_range" in model_data:
            price_min, price_max = model_data.get("price_range", (None, None))
            print(f"\n价格区间: {price_min}-{price_max}")
        
        if "hold_num" in model_data:
            hold_num = model_data.get("hold_num", "未知")
            print(f"持仓数量: {hold_num}")
        
        if "date_range" in model_data:
            start_date, end_date = model_data.get("date_range", (None, None))
            print(f"回测区间: {start_date} 至 {end_date}")
        
        return
    
    # 方法1: 直接从model_data中提取因子信息
    if "best_factors" in model_data:
        best_factors = model_data["best_factors"]
        print("最佳因子组合:")
        for i, factor_info in enumerate(best_factors):
            if isinstance(factor_info, dict):
                factor = factor_info.get("name", "未知")
                weight = factor_info.get("weight", "未知")
                direction = "升序" if factor_info.get("ascending", False) else "降序"
                print(f"  {i+1}. {factor}")
                print(f"     - 权重: {weight}")
                print(f"     - 排序方向: {direction}")
        return
    
    # 方法2: 从combination_idx和params中提取
    if "combination_idx" in params and factors:
        combo_idx = params["combination_idx"]
        if isinstance(combo_idx, (int, float)):
            combo_idx = int(combo_idx)
            if combinations and combo_idx < len(combinations):
                factor_indices = combinations[combo_idx]
                if isinstance(factor_indices, (list, tuple)) and all(isinstance(i, int) for i in factor_indices):
                    factor_names = [factors[i] for i in factor_indices]
                elif isinstance(factor_indices, int):
                    # 处理单个索引的情况
                    factor_names = [factors[factor_indices]]
            
            # 从params中提取权重和方向
            for i in range(10):  # 尝试最多10个因子
                weight_key = f"factor{i}_weight"
                asc_key = f"factor{i}_ascending"
                
                if weight_key in params:
                    weights.append(params[weight_key])
                    directions.append("升序" if params.get(asc_key, False) else "降序")
                else:
                    break
    
    # 如果上面的尝试成功，显示结果
    if factor_names and len(factor_names) == len(weights) == len(directions):
        print("最佳因子组合:")
        for i, (factor, weight, direction) in enumerate(zip(factor_names, weights, directions)):
            print(f"  {i+1}. {factor}")
            print(f"     - 权重: {weight}")
            print(f"     - 排序方向: {direction}")
    else:
        # 方法3: 尝试直接从best_trial中提取
        if "study" in model_data and hasattr(model_data["study"], "best_trial"):
            best_trial = model_data["study"].best_trial
            best_params = best_trial.params
            
            print("最佳因子组合:")
            # 检查是否有直接的因子信息
            for key, value in best_params.items():
                if key == "combination_idx":
                    continue
                print(f"  {key}: {value}")
            
            # 尝试解析combination_idx
            if "combination_idx" in best_params and factors and combinations:
                combo_idx = int(best_params["combination_idx"])
                if combo_idx < len(combinations):
                    indices = combinations[combo_idx]
                    factor_names = [factors[i] for i in indices]
                    print(f"\n使用的因子: {', '.join(factor_names)}")
        else:
            print("\n无法提取因子组合信息，请检查模型文件格式")
            print("原始参数信息:")
            for key, value in params.items():
                print(f"  {key}: {value}")
    
    # 其他参数
    other_params = {k: v for k, v in params.items() 
                    if not k.startswith("factor") and k != "combination_idx"}
    
    if other_params:
        print("\n其他参数:")
        for key, value in other_params.items():
            print(f"  {key}: {value}")
    
    # 详细信息
    if detailed and "study" in model_data:
        study = model_data["study"]
        if hasattr(study, "trials"):
            trials = study.trials
            
            if trials:
                print(f"\n所有试验数量: {len(trials)}")
                
                # 按值排序试验
                sorted_trials = sorted(
                    [t for t in trials if hasattr(t, "value") and t.value is not None],
                    key=lambda t: t.value if t.value is not None else float('-inf'), 
                    reverse=True
                )
                
                if sorted_trials:
                    print("\n前5个最佳试验:")
                    for i, trial in enumerate(sorted_trials[:5]):
                        if not hasattr(trial, "value") or trial.value is None:
                            continue
                        print(f"\n#{i+1} 试验 {trial.number} (CAGR: {trial.value:.4f})")
                        if hasattr(trial, "params"):
                            for k, v in trial.params.items():
                                if k == "combination_idx" and factors:
                                    combo_idx = int(v)
                                    if combinations and combo_idx < len(combinations):
                                        try:
                                            factor_indices = combinations[combo_idx]
                                            factor_names = [factors[i] for i in factor_indices]
                                            print(f"  因子组合: {', '.join(factor_names)}")
                                        except:
                                            print(f"  {k}: {v}")
                                else:
                                    print(f"  {k}: {v}")
        
    # 尝试从文件名中提取更多信息（如策略类型、因子数等）
    filename = os.path.basename(model_path)
    parts = filename.split('_')
    if len(parts) > 2:
        strategy = parts[2] if len(parts) > 2 else "未知"
        method = parts[3] if len(parts) > 3 else "未知"
        print(f"\n优化策略: {strategy}")
        print(f"优化方法: {method}")
        
        # 尝试提取因子数量
        for part in parts:
            if part.endswith('factors'):
                try:
                    n_factors = int(part[0])
                    print(f"因子数量: {n_factors}")
                except:
                    pass

def inspect_model(model_data, max_depth=2, current_depth=0, prefix=''):
    """递归检查模型的内部结构"""
    if current_depth > max_depth:
        return "..."
    
    if isinstance(model_data, dict):
        result = "{\n"
        for key, value in model_data.items():
            new_prefix = prefix + "  "
            value_str = inspect_model(value, max_depth, current_depth + 1, new_prefix) if current_depth < max_depth else "..."
            result += f"{new_prefix}{key}: {value_str}\n"
        result += prefix + "}"
        return result
    elif isinstance(model_data, list):
        if len(model_data) == 0:
            return "[]"
        if current_depth == max_depth:
            return f"[...] (长度: {len(model_data)})"
        if len(model_data) > 10:
            first_items = model_data[:3]
            result = "[\n"
            for item in first_items:
                new_prefix = prefix + "  "
                item_str = inspect_model(item, max_depth, current_depth + 1, new_prefix)
                result += f"{new_prefix}{item_str},\n"
            result += f"{prefix}  ... (共 {len(model_data)} 项)\n"
            result += prefix + "]"
            return result
        else:
            result = "[\n"
            for item in model_data:
                new_prefix = prefix + "  "
                item_str = inspect_model(item, max_depth, current_depth + 1, new_prefix)
                result += f"{new_prefix}{item_str},\n"
            result += prefix + "]"
            return result
    elif isinstance(model_data, (int, float, str, bool, type(None))):
        return str(model_data)
    elif hasattr(model_data, "__dict__"):
        # 处理自定义对象
        try:
            obj_dict = model_data.__dict__
            result = f"{model_data.__class__.__name__}(\n"
            for key, value in obj_dict.items():
                if not key.startswith("_"):  # 跳过私有属性
                    new_prefix = prefix + "  "
                    value_str = inspect_model(value, max_depth, current_depth + 1, new_prefix) if current_depth < max_depth else "..."
                    result += f"{new_prefix}{key}: {value_str}\n"
            result += prefix + ")"
            return result
        except:
            return str(model_data)
    else:
        return str(model_data)

def examine_study(study):
    """检查optuna study对象的详细信息"""
    if not study:
        return "Study 对象为空"
    
    result = "Study详情:\n"
    result += f"- 方向: {study.direction}\n"
    result += f"- 试验数量: {len(study.trials)}\n"
    
    if study.best_trial:
        result += f"- 最佳试验: #{study.best_trial.number}, 值: {study.best_trial.value}\n"
        result += "  参数:\n"
        for k, v in study.best_trial.params.items():
            result += f"    {k}: {v}\n"
    
    return result

def list_available_models():
    """列出所有可用的模型文件"""
    # 检查主结果目录
    main_models = glob.glob(os.path.join(RESULTS_DIR, "best_model_*.pkl"))
    
    # 检查最佳模型目录（如果存在）
    best_models = []
    if os.path.exists(BEST_MODELS_DIR):
        best_models = glob.glob(os.path.join(BEST_MODELS_DIR, "best_model_*.pkl"))
    
    all_models = main_models + best_models
    
    if not all_models:
        print("未找到任何模型文件")
        return []
    
    print("\n可用模型文件:")
    print("-"*60)
    
    # 创建模型信息列表
    model_info_list = []
    
    for model_path in all_models:
        try:
            filename = os.path.basename(model_path)
            cagr_str = "未知"
            cagr_value = 0.0
            
            # 尝试方法1：从文件名中提取CAGR (格式为 best_model_XXX_0.2345_TIMESTAMP.pkl)
            parts = filename.split('_')
            for part in parts:
                if part.startswith('0.') and len(part) >= 4:
                    cagr_str = part
                    try:
                        cagr_value = float(part)
                    except:
                        pass
                    break
            
            # 尝试方法2：如果文件名中没有CAGR，尝试加载模型获取
            if cagr_str == "未知":
                try:
                    # 尝试快速加载模型头部信息
                    model_data = joblib.load(model_path)
                    if isinstance(model_data, dict) and "best_value" in model_data:
                        cagr_value = model_data["best_value"]
                        cagr_str = f"{cagr_value:.4f}"
                except:
                    pass
            
            # 提取创建时间
            mod_time = datetime.fromtimestamp(os.path.getmtime(model_path))
            mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
            
            model_info_list.append({
                'path': model_path,
                'filename': filename,
                'cagr': cagr_value,
                'cagr_str': cagr_str,
                'mod_time': mod_time,
                'mod_time_str': mod_time_str
            })
            
        except Exception as e:
            print(f"无法读取文件 {os.path.basename(model_path)}: {e}")
            model_info_list.append({
                'path': model_path,
                'filename': os.path.basename(model_path),
                'cagr': 0.0,
                'cagr_str': "错误",
                'mod_time': datetime.fromtimestamp(0),
                'mod_time_str': "未知"
            })
    
    # 按CAGR值排序（降序）
    model_info_list.sort(key=lambda x: x['cagr'], reverse=True)
    
    # 显示排序后的模型列表
    for i, info in enumerate(model_info_list):
        print(f"{i+1}. {info['filename']}")
        print(f"   CAGR: {info['cagr_str']}, 修改时间: {info['mod_time_str']}")
    
    print("-"*60)
    return [info['path'] for info in model_info_list]

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='查看可转债优化模型文件')
    parser.add_argument('--list', action='store_true', help='列出所有可用的模型文件')
    parser.add_argument('--model', type=str, help='要查看的特定模型文件路径')
    parser.add_argument('--index', type=int, help='要查看的模型索引（基于列表）')
    parser.add_argument('--detailed', action='store_true', help='显示详细信息')
    parser.add_argument('--depth', type=int, default=3, help='检查模型结构的深度')
    parser.add_argument('--inspect', action='store_true', help='查看模型的完整内部结构')
    parser.add_argument('--save-factors', type=str, help='将提取的因子信息保存到指定文件')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    if args.list or (not args.model and args.index is None):
        # 列出所有模型
        all_models = list_available_models()
        
        if all_models and args.index is None:
            try:
                choice = input("\n输入模型编号查看详情 (或按Enter退出): ")
                if choice.strip():
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_models):
                        args.model = all_models[idx]
                    else:
                        print("无效的模型编号")
                        sys.exit(1)
                else:
                    sys.exit(0)
            except ValueError:
                print("请输入有效的数字")
                sys.exit(1)
        elif args.index is not None:
            if 0 <= args.index - 1 < len(all_models):
                args.model = all_models[args.index - 1]
            else:
                print(f"无效的模型索引: {args.index}")
                sys.exit(1)
    
    if args.model:
        model_path = args.model
        if not os.path.isabs(model_path):
            # 检查相对路径
            if os.path.exists(model_path):
                model_path = os.path.abspath(model_path)
            elif os.path.exists(os.path.join(RESULTS_DIR, model_path)):
                model_path = os.path.abspath(os.path.join(RESULTS_DIR, model_path))
            elif os.path.exists(os.path.join(BEST_MODELS_DIR, model_path)):
                model_path = os.path.abspath(os.path.join(BEST_MODELS_DIR, model_path))
        
        # 加载并显示模型信息
        model_data = load_model(model_path)
        
        if args.inspect:
            print("\n" + "="*60)
            print(f"模型文件详细结构: {os.path.basename(model_path)}")
            print("="*60)
            print(inspect_model(model_data, max_depth=args.depth))
            
            # 特别检查study对象
            if "study" in model_data:
                print("\n" + "="*60)
                print("Study对象详情:")
                print("="*60)
                print(examine_study(model_data["study"]))
        else:
            display_model_info(model_data, detailed=args.detailed)
            
        # 如果需要，保存因子信息
        if args.save_factors and model_data:
            try:
                # 提取因子信息
                factor_info = {
                    "cagr": model_data.get("best_value", 0),
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "model_file": os.path.basename(model_path),
                    "factors": []
                }
                
                # 尝试提取因子信息，与display_model_info函数中类似的逻辑
                params = model_data.get("best_params", {})
                factors = model_data.get("factors", [])
                combinations = model_data.get("combinations", [])
                
                if "combination_idx" in params and factors and combinations:
                    combo_idx = int(params["combination_idx"])
                    if combo_idx < len(combinations):
                        factor_indices = combinations[combo_idx]
                        factor_names = [factors[i] for i in factor_indices]
                        
                        for i, factor_name in enumerate(factor_names):
                            weight_key = f"factor{i}_weight"
                            asc_key = f"factor{i}_ascending"
                            
                            weight = params.get(weight_key, 1)
                            direction = params.get(asc_key, False)
                            
                            factor_info["factors"].append({
                                "name": factor_name,
                                "weight": weight,
                                "ascending": direction
                            })
                
                # 保存到文件
                with open(args.save_factors, 'w', encoding='utf-8') as f:
                    json.dump(factor_info, f, indent=2, ensure_ascii=False)
                print(f"\n因子信息已保存到: {args.save_factors}")
            except Exception as e:
                print(f"\n保存因子信息时出错: {e}")
