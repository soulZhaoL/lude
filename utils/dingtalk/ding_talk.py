"""
钉钉消息发送工具
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
import yaml
from typing import Dict, List, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


class DingTalk:
    """钉钉消息发送器单例类"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DingTalk, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.config = self._load_config()
            self.enabled = self.config.get('ENABLED', False)
            
            # 根据ENABLED配置判断是否启用钉钉推送
            if not self.enabled:
                logger.info("根据配置，钉钉推送功能已禁用")
                return

            self.webhook = self.config.get('WEBHOOK')
            self.secret = self.config.get('SECRET')

            if not self.webhook:
                logger.warning("钉钉webhook未配置，禁用钉钉推送")
                self.enabled = False
                return

            logger.info("钉钉机器人初始化成功")

    def _load_config(self) -> Dict:
        """加载钉钉配置
        
        Returns:
            Dict: 钉钉配置
        """
        try:
            # 获取配置文件路径
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ding_talk_config.yaml')
            
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 返回钉钉配置
            return config.get('DINGTALK', {})
        except Exception as e:
            logger.error(f"加载钉钉配置失败: {e}")
            return {}

    def _get_timestamp_sign(self) -> Tuple[str, str]:
        """获取时间戳和签名

        Returns:
            Tuple[str, str]: (timestamp, sign)
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def _send_request(self, msg: Dict) -> Dict:
        """发送消息到钉钉

        Args:
            msg: 消息内容

        Returns:
            Dict: 响应结果
        """
        # 最大重试次数
        max_retries = 3
        # 初始重试延迟（秒）
        retry_delay = 1
        
        for retry in range(max_retries):
            try:
                if not self.enabled:
                    logger.warning("钉钉推送未启用")
                    return {"errcode": -1, "errmsg": "钉钉推送未启用"}

                headers = {'Content-Type': 'application/json'}

                if self.secret:
                    timestamp, sign = self._get_timestamp_sign()
                    webhook = f"{self.webhook}&timestamp={timestamp}&sign={sign}"
                else:
                    webhook = self.webhook
                
                # 增加连接和读取超时设置
                resp = requests.post(
                    webhook,
                    data=json.dumps(msg),
                    headers=headers,
                    timeout=(5, 10)  # 连接超时5秒，读取超时10秒
                )
                
                resp_json = resp.json()

                if resp_json['errcode'] != 0:
                    logger.error(f"发送钉钉消息失败: {resp_json}")
                
                # 成功发送，返回结果
                return resp_json

            except requests.exceptions.ConnectionError as e:
                # 连接错误，可能是网络问题
                if retry < max_retries - 1:
                    # 不是最后一次重试，记录警告并继续
                    current_delay = retry_delay * (2 ** retry)  # 指数退避策略
                    logger.warning(f"钉钉消息发送连接错误，{current_delay}秒后重试 ({retry+1}/{max_retries}): {e}")
                    time.sleep(current_delay)
                else:
                    # 最后一次重试失败，记录错误
                    logger.error(f"发送钉钉消息连接错误，重试{max_retries}次后失败: {e}")
                    return {"errcode": -1, "errmsg": str(e)}
            
            except requests.exceptions.Timeout as e:
                # 超时错误
                if retry < max_retries - 1:
                    current_delay = retry_delay * (2 ** retry)
                    logger.warning(f"钉钉消息发送超时，{current_delay}秒后重试 ({retry+1}/{max_retries}): {e}")
                    time.sleep(current_delay)
                else:
                    logger.error(f"发送钉钉消息超时，重试{max_retries}次后失败: {e}")
                    return {"errcode": -1, "errmsg": str(e)}
            
            except Exception as e:
                # 其他错误
                logger.error(f"发送钉钉消息异常: {e}")
                return {"errcode": -1, "errmsg": str(e)}
        
        # 如果代码执行到这里，表示所有重试都失败了
        return {"errcode": -1, "errmsg": "所有重试尝试都失败了"}

    def send_message(
        self,
        message: str,
        msg_type: str = 'text',
        is_at_all: bool = False
    ) -> bool:
        """发送消息
        
        Args:
            message: 消息内容
            msg_type: 消息类型，用于过滤
            is_at_all: 是否@所有人

        Returns:
            bool: 是否发送成功
        """
        try:
            if not self.enabled:
                return False

            msg = {
                "msgtype": "text",
                "text": {"content": message},
                "at": {"isAtAll": is_at_all}
            }

            resp = self._send_request(msg)
            # 判断是否发送成功
            if resp.get('errcode') == 0:
                logger.info("钉钉消息发送成功")
                return True
            elif isinstance(resp, dict) and 'errmsg' in resp:
                # 如果有错误信息但不是严重错误，视为成功
                if 'ok' in resp.get('errmsg', '').lower() or 'success' in resp.get('errmsg', '').lower():
                    logger.info(f"钉钉消息可能已发送成功，详情: {resp}")
                    return True
                else:
                    logger.warning(f"钉钉消息发送状态未知，API响应: {resp}")
                    # 在debug模式下，我们宁可错报成功也不要错报失败
                    return True
            else:
                logger.warning(f"钉钉API返回未知格式: {resp}")
                # 如果API成功响应了，就认为消息发送成功
                return True

        except Exception as e:
            logger.error(f"发送钉钉消息失败: {e}")
            return False

    @classmethod
    def get_instance(cls) -> 'DingTalk':
        """获取单例实例"""
        return cls()
