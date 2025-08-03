#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
钉钉通知模块
负责将优化结果发送到钉钉
"""

from datetime import datetime

from lude.utils.dingtalk.ding_talk_manager import DingTalkManager
from lude.utils.logger import dingtalk_logger as logger


def send_optimization_result_to_dingtalk(
        cagr,
        rank_factors,
        filter_conditions=None,
        seed=None,
        strategy="default",
        n_trials=None,
        start_date=None,
        end_date=None,
        hold_num=None,
        price_range=None,
        model_path=None,
        current_iteration=None,
        total_iterations=None
):
    """发送优化结果到钉钉
    
    Args:
        cagr: 年化收益率
        rank_factors: 因子数据列表，每个元素为字典，包含 name、description、weight、ascending 等字段
        filter_conditions: 排除因子条件列表
        seed: 随机种子
        strategy: 策略名称
        n_trials: 试验次数
        start_date: 开始日期
        end_date: 结束日期
        hold_num: 持仓数
        price_range: 价格范围 (min, max)
        model_path: 模型保存路径
        current_iteration: 当前迭代次数
        total_iterations: 总迭代次数
    """

    # 时间信息
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 创建钉钉管理器实例
        manager = DingTalkManager()

        # 种子信息
        seed_info = f"(种子: {seed})" if seed is not None else ""

        # 迭代信息
        iteration_info = ""
        if current_iteration is not None and total_iterations is not None:
            iteration_info = f"[迭代进度: {current_iteration}/{total_iterations}]\n"

        # 策略信息
        strategy_info = f"策略: {strategy}\n" if strategy else ""

        # 参数信息
        params_info = ""
        if n_trials:
            params_info += f"试验次数: {n_trials}\n"
        if hold_num:
            params_info += f"持仓数: {hold_num}\n"
        if start_date and end_date:
            params_info += f"时间范围: {start_date} - {end_date}\n"
        if price_range:
            params_info += f"价格范围: {price_range[0]} - {price_range[1]}\n"

        # 模型路径信息
        model_info = f"模型保存路径: {model_path}\n" if model_path else ""

        # 因子组合
        factors_info = ""
        if rank_factors:
            factors_info = "最佳因子组合:"
            for i, factor_data in enumerate(rank_factors):
                # 从因子数据字典中获取各个字段
                name = factor_data['name']
                weight = factor_data['weight']
                ascending = factor_data['ascending']
                description = factor_data.get('description', '')
                
                direction = "升序" if ascending else "降序"

                # 使用因子描述(中文名)
                factor_display = f"{name} ({description})" if description else name

                factors_info += f"\n{i + 1}. {factor_display} (权重: {weight}, {direction})"

        # 排除因子信息
        filter_info = ""
        if filter_conditions:
            filter_info = "\n\n排除因子条件:"
            for i, condition in enumerate(filter_conditions):
                factor_name = condition.get('factor', 'unknown')
                operator = condition.get('operator', '>=')
                value = condition.get('value', 0)
                desc = condition.get('desc', '')
                
                desc_part = f" ({desc})" if desc else ""
                filter_info += f"\n{i + 1}. {factor_name} {operator} {value}{desc_part}"

        # 完整消息
        message = f"【可转债优化新结果】{current_time}\n" \
                  f"年化收益率(CAGR): {cagr:.6f} {seed_info}\n" \
                  f"{strategy_info}" \
                  f"{params_info}" \
                  f"{model_info}" \
                  f"{iteration_info}" \
                  f"{factors_info}" \
                  f"{filter_info}"

        # 发送消息
        manager.send_message(message)
        logger.debug("钉钉推送成功")

    except Exception as e:
        logger.error(f"发送钉钉通知时出错: {e}")
        return False

    return True
