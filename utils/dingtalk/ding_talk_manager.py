"""
钉钉消息管理器
"""
import logging

from utils.dingtalk.ding_talk import DingTalk

logger = logging.getLogger(__name__)

class DingTalkManager:
    """钉钉消息管理器，单例模式"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'DingTalkManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化"""
        if DingTalkManager._instance is not None:
            raise Exception("DingTalkManager 是单例类，请使用 get_instance() 获取实例")
        self._ding_talk = DingTalk.get_instance()
    
    def send_message(self, message: str, prefix: str = "", msg_type: str = "text", is_at_all: bool = False):
        """发送钉钉消息
        
        Args:
            message: 消息内容
            prefix: 消息前缀，例如交易所名称
            msg_type: 消息类型，默认为 text
            is_at_all: 是否@所有人
        """
        try:
            if prefix:
                message = f"[{prefix}] {message}"
            return self._ding_talk.send_message(message, msg_type, is_at_all)
        except Exception as e:
            logger.error(f"发送钉钉消息失败: {e}")
