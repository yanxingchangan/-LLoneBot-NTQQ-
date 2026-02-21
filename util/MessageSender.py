import httpx
import requests
import concurrent.futures
import json
import os
from typing import Optional, Dict, Any

class Messagesender:
    def __init__(self, config: dict):
        """
        初始化消息处理器
        :param config_path: 配置文件路径，默认为当前目录下的config.json
        """
        self.config = config
        self.server_url = config.get("system", {}).get("local_server", "http://localhost:3000/send_group_msg")
        self.private_url = config.get("system", {}).get("admin_server", "http://localhost:3000/send_msg")
        
    async def send_message(self, group_id: int, message: Dict[str, Any]) -> tuple[Optional[requests.Response], str]:
        """
        发送群普通消息
        :param group_id: 群ID
        :param message: 消息内容
        :return: (响应对象或None, 日志信息)
        """
        def post_request():
            try:
                response = requests.post(self.server_url, json={
                    'group_id': group_id,
                    'message': message
                })
                response.raise_for_status()
                return response, f"群消息发送成功，群ID: {group_id}"
            except requests.RequestException as e:
                return None, f"群消息发送失败，群ID: {group_id}, 错误: {str(e)}"

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(post_request)
            return future.result()
    
    async def send_group_message(self, group_id: int, user_id: str, message: str) -> tuple[Optional[requests.Response], str]:
        """
        发送群指定消息
        :param group_id: 群ID
        :param user_id: 用户ID
        :param message: 消息内容
        :return: (响应对象或None, 日志信息)
        """
        message_payload = {
            "group_id": group_id,
            "message": [
                {
                    "type": "at",
                    "data": {
                        "qq": f"{user_id}",
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": message
                    }
                }
            ]
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.server_url,
                    json=message_payload,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                return response, f"群指定消息发送成功，群ID: {group_id}, @用户: {user_id}"
        except Exception as e:
            return None, f"群指定消息发送失败，群ID: {group_id}, @用户: {user_id}, 错误: {str(e)}"
    
    async def send_private_message(self, user_id: int, message: Dict[str, Any]) -> tuple[Optional[requests.Response], str]:
        """
        发送私聊消息
        :param user_id: 用户ID
        :param message: 消息内容
        :return: (响应对象或None, 日志信息)
        """
        def post_request():
            try:
                response = requests.post(self.private_url, json={
                    'user_id': user_id,
                    'message': message
                })
                response.raise_for_status()
                return response, f"私聊消息发送成功，用户ID: {user_id}"
            except requests.RequestException as e:
                return None, f"私聊消息发送失败，用户ID: {user_id}, 错误: {str(e)}"

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(post_request)
            return future.result()