#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
钉钉通知模块
负责将优化结果发送到钉钉
"""

import os
import json
from datetime import datetime
import sys
import importlib.util

# 尝试导入钉钉管理器
ding_talk_available = False
try:
    from utils.dingtalk.ding_talk_manager import DingTalkManager
    ding_talk_available = True
    print("成功导入钉钉管理器")
except ImportError as e:
    print(f"警告: 尝试标准导入失败，原因: {e}")
    
    # 尝试直接使用绝对导入路径
    try:
        # 假设ding_talk_manager.py在项目根目录的util/dingtalk/下
        manager_path = os.path.join(project_root, "util", "dingtalk", "ding_talk_manager.py")
        if os.path.exists(manager_path):
            print(f"找到钉钉管理器文件: {manager_path}")
            
            # 使用importlib直接从文件导入
            spec = importlib.util.spec_from_file_location("ding_talk_manager", manager_path)
            ding_talk_manager = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ding_talk_manager)
            DingTalkManager = ding_talk_manager.DingTalkManager
            ding_talk_available = True
            print("成功通过文件路径导入钉钉管理器")
        else:
            print(f"钉钉管理器文件不存在: {manager_path}")
    except Exception as e2:
        print(f"尝试直接导入文件失败: {e2}")
        
        # 最后尝试直接从旧的相对路径导入
        try:
            old_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            if old_project_root not in sys.path:
                sys.path.insert(0, old_project_root)
                print(f"尝试添加旧的项目根目录到系统路径: {old_project_root}")
            
            # 再次尝试常规导入
            from utils.dingtalk.ding_talk_manager import DingTalkManager
            ding_talk_available = True
            print("通过旧路径成功导入钉钉管理器")
        except Exception as e3:
            print(f"所有导入尝试均失败: {e3}")
            print("钉钉推送功能将被禁用")


def load_factor_mapping():
    """加载因子中英文映射
    
    Returns:
        factor_mapping: 因子映射字典，键为英文名，值为中文名
    """
    mapping_file = os.path.join(os.path.dirname(__file__), "../../factor_mapping.json")
    
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载因子映射文件时出错: {e}")
            return {}
    else:
        default_mapping = {
            "conv_prem": "转股溢价率",
            "theory_conv_prem": "理论溢价率",
            "mod_conv_prem": "修正溢价率",
            "pure_value": "纯债价值",
            "bond_prem": "纯债溢价率",
            "dblow": "双低",
            "close": "收盘价",
            "ytm": "到期收益率",
            "list_days": "上市天数",
            "left_years": "剩余年限",
            "turnover": "换手率",
            "vol": "成交量",
            "amount": "成交额",
            "pe_ttm": "市盈率",
            "pb": "市净率",
            "ps_ttm": "市销率",
            "bias_5": "5日乖离率",
            "bias_10": "10日乖离率",
            "bias_20": "20日乖离率",
            "pct_chg_5": "5日涨跌幅",
            "pct_chg_10": "10日涨跌幅",
            "pct_chg_20": "20日涨跌幅"
        }
        
        try:
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(default_mapping, f, ensure_ascii=False, indent=4)
            print(f"已创建默认因子映射文件: {mapping_file}")
        except Exception as e:
            print(f"创建因子映射文件时出错: {e}")
        
        return default_mapping


def send_optimization_result_to_dingtalk(
    cagr, 
    rank_factors, 
    seed=None,
    strategy=None,
    n_factors=None,
    start_date=None,
    end_date=None,
    price_range=None,
    hold_num=None
):
    """发送优化结果到钉钉
    
    Args:
        cagr: 年化收益率
        rank_factors: 最佳因子配置
        seed: 随机种子
        strategy: 优化策略名称
        n_factors: 因子数量
        start_date: 回测开始日期
        end_date: 回测结束日期
        price_range: 价格范围元组 (min, max)
        hold_num: 持仓数量
        
    Returns:
        success: 是否发送成功
    """
    # 检查钉钉管理器是否可用
    if not ding_talk_available:
        print("钉钉推送模块不可用，跳过推送")
        return False
    
    # 如果没有rank_factors，返回失败
    if rank_factors is None:
        print("未提供最佳因子配置，无法发送通知")
        return False
    
    try:
        # 加载因子映射
        factor_mapping = load_factor_mapping()
        
        # 获取钉钉管理器实例
        try:
            ding_manager = DingTalkManager.get_instance()
        except Exception as e:
            print(f"获取钉钉管理器实例失败: {e}")
            return False
        
        # 构建消息内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seed_info = f"(种子: {seed})" if seed else ""
        strategy_info = f"策略: {strategy}" if strategy else ""
        
        # 构造优化参数信息
        params_info = ""
        if hold_num is not None or n_factors is not None or start_date is not None or price_range is not None:
            params_info = "\n\n【优化参数】"
            
        if hold_num is not None:
            params_info += f"\n持仓数量: {hold_num}"
        if n_factors is not None:
            params_info += f"\n因子数量: {n_factors}"
        if start_date is not None and end_date is not None:
            params_info += f"\n回测区间: {start_date} 至 {end_date}"
        if price_range is not None:
            params_info += f"\n价格区间: {price_range[0]} 至 {price_range[1]}"
        
        # 如果没有任何参数，则不显示参数部分
        if params_info == "\n\n【优化参数】":
            params_info = ""
        
        # 构造因子信息
        factors_info = ""
        if rank_factors:
            factors_info = "\n\n【最佳因子组合】"
            for i, factor in enumerate(rank_factors):
                direction = "升序" if factor.get('ascending', False) else "降序"
                weight = factor.get('weight', 1)
                factor_name = factor['name']
                
                # 添加中文名称（如果存在）
                chinese_name = factor_mapping.get(factor_name, "")
                if chinese_name:
                    factor_display = f"{factor_name}[{chinese_name}]"
                else:
                    factor_display = factor_name
                
                factors_info += f"\n{i+1}. {factor_display} (权重: {weight}, {direction})"
        
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
            print("钉钉推送成功")
        else:
            print("钉钉推送失败")
        
        return result
    except Exception as e:
        print(f"发送钉钉消息时出错: {e}")
        return False
