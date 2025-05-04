"""
钉钉消息推送测试用例
"""
import logging
import sys
import os
from datetime import datetime

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# 导入钉钉管理器
from lude.utils.dingtalk.ding_talk_manager import DingTalkManager


def test_send_simple_message():
    """测试发送简单文本消息"""
    try:
        # 获取钉钉管理器实例
        ding_manager = DingTalkManager.get_instance()
        
        # 构造测试消息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_message = f"钉钉消息推送测试 - 这是一条测试消息 - 时间: {current_time}"
        
        # 发送消息
        print(f"正在发送测试消息: {test_message}")
        ding_manager.send_message(
            message=test_message,
            prefix="测试",
            is_at_all=False
        )
        print("消息已发送，请检查钉钉群是否收到")
        
        return True
    except Exception as e:
        print(f"发送消息失败: {e}")
        return False


def test_send_message_with_at_all():
    """测试发送@所有人的消息"""
    try:
        # 获取钉钉管理器实例
        ding_manager = DingTalkManager.get_instance()
        
        # 构造测试消息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_message = f"钉钉消息推送测试 - 这是一条@所有人的测试消息 - 时间: {current_time}"
        
        # 发送消息并@所有人
        print(f"正在发送@所有人的测试消息: {test_message}")
        ding_manager.send_message(
            message=test_message,
            prefix="紧急测试",
            is_at_all=True
        )
        print("消息已发送，请检查钉钉群是否收到并@所有人")
        
        return True
    except Exception as e:
        print(f"发送消息失败: {e}")
        return False


def test_batch_messages():
    """测试批量发送消息"""
    try:
        # 获取钉钉管理器实例
        ding_manager = DingTalkManager.get_instance()
        
        # 批量发送3条消息
        test_messages = [
            "第一条批量测试消息",
            "第二条批量测试消息",
            "第三条批量测试消息"
        ]
        
        # 循环发送消息
        print("开始批量发送测试消息...")
        for index, message in enumerate(test_messages):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_message = f"{message} - [{index+1}/{len(test_messages)}] - 时间: {current_time}"
            
            ding_manager.send_message(
                message=full_message,
                prefix=f"批量测试-{index+1}",
                is_at_all=False
            )
            print(f"已发送第 {index+1} 条消息")
        
        print("所有批量消息已发送，请检查钉钉群是否收到")
        return True
    except Exception as e:
        print(f"批量发送消息失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("钉钉消息推送测试开始")
    print("=" * 50)
    
    # 测试简单消息发送
    print("\n1. 测试发送简单消息:")
    test_send_simple_message()
    
    # 等待用户确认是否继续
    input("\n按回车键继续测试...\n")
    
    # 测试@所有人的消息
    print("\n2. 测试发送@所有人的消息:")
    test_send_message_with_at_all()
    
    # 等待用户确认是否继续
    input("\n按回车键继续测试...\n")
    
    # 测试批量发送消息
    print("\n3. 测试批量发送消息:")
    test_batch_messages()
    
    print("\n" + "=" * 50)
    print("钉钉消息推送测试完成")
    print("=" * 50)
