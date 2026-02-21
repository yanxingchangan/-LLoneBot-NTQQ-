import json
import httpx
import logging
import random
import pandas as pd
import requests
import time
import os
import redis
from typing import Dict, Tuple, Any, Optional

# 设置日志
logger = logging.getLogger(__name__)

class Deepseekchat:
    def __init__(self, config: dict):
        """
        初始化聊天管理器
        """
        self.config = config
        
        # db=1 用于存储聊天记录，与 Celery 的 db=0 区分开
        try:
            self.redis = redis.Redis(
                host='localhost', 
                port=6379, 
                db=1, 
                decode_responses=True,
                socket_timeout=5
            )
            self.redis.ping()
        except Exception as e:
            logger.error(f"Redis 连接失败，请检查 Redis 服务是否启动: {e}")
            raise e
        
        self.max_history_len = 20  # 限制保留最近 20 条消息 (10轮对话)
        self.session_timeout = 1800  # 30分钟后忘记上下文

    def _get_redis_key(self, user_id: int) -> str:
        """生成 Redis 存储的 Key"""
        return f"chat_context:{user_id}"

    def get_context(self, user_id: int) -> list:
        """从 Redis 获取当前对话上下文"""
        key = self._get_redis_key(user_id)
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"读取 Redis 上下文失败: {e}")
        
        # 如果没有历史或读取失败，初始化并加载人设
        return self._init_new_session(user_id)

    def _init_new_session(self, user_id: int) -> list:
        """初始化新会话（带人设）"""
        user_presets = self.config.get("user_presets", {})
        # 默认人设
        default_preset = self.config.get("default_preset", {
            "content": "你是一个有用的AI助手。", 
            "role": "system"
        })
        # 获取特定用户/群组人设
        preset = user_presets.get(str(user_id), default_preset)
        
        # 确保 preset 是个列表
        if isinstance(preset, dict):
            return [preset]
        return list(preset)

    def update_context(self, user_id: int, message: str, role: str):
        """更新上下文到 Redis"""
        try:
            key = self._get_redis_key(user_id)
            history = self.get_context(user_id)
            
            # 添加新消息
            history.append({"content": message, "role": role})
            
            # === 滑动窗口内存保护 ===
            if len(history) > self.max_history_len:
                # 始终保留 index 0 (System Prompt/人设)
                # 切片保留最后 (max_history_len - 1) 条
                system_prompt = history[0]
                recent_chats = history[-(self.max_history_len - 1):]
                history = [system_prompt] + recent_chats
                
            # 存回 Redis 并重置过期时间 (30分钟)
            self.redis.setex(key, self.session_timeout, json.dumps(history))
        except Exception as e:
            logger.error(f"更新 Redis 上下文失败: {e}")

    async def get_chat_response(self, user_id: int, message: str) -> Tuple[int, str]:
        """获取AI响应（带上下文记忆）"""
        try:
            self.update_context(user_id, message, "user")
            
            context = self.get_context(user_id)
            
            payload = {
                "messages": context,
                "model": "deepseek-chat",
                "max_tokens": 2048,
                "temperature": 1.3,
                "top_p": 1
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.config.get("api", {}).get("api_key", "")}'
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.config.get("api", {}).get("chat_endpoint", ""), 
                    headers=headers, 
                    json=payload
                )
                response.raise_for_status()
                
                response_json = response.json()
                if "choices" not in response_json or not response_json["choices"]:
                    return response.status_code, "响应缺少有效的 'choices' 字段"
                
                bot_reply = response_json["choices"][0]["message"]["content"]
                
                self.update_context(user_id, bot_reply, "assistant")
                
                return response.status_code, bot_reply
            
        except Exception as e:
            logger.error(f"Chat请求错误: {str(e)}")
            return 500, f"请求错误: {str(e)}"

    async def get_balance(self) -> str:
        """获取API账户余额 """
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.config.get("api", {}).get("api_key", "")}'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.config.get("api", {}).get("api_endpoint", ""), headers=headers)
                response.raise_for_status()
                data = response.json()

                if not data.get("is_available"):
                    return "API服务不可用"

                balance_info = data.get("balance_infos", [])
                if not balance_info:
                    return "无可用余额信息"
                    
                balance = balance_info[0].get("total_balance")
                if balance is None:
                    return "余额信息无效"
                    
                return f"{balance:.2f}"

        except Exception as e:
            logging.error(f"获取余额错误: {str(e)}")
            return f"查询失败: {str(e)}"
            
    def get_random_video(self) -> Any:
        """随机视频获取逻辑 """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filename = os.path.join(base_dir, "resource", "up_videos.xlsx")
        try:
            if not os.path.exists(filename):
                logging.warning(f"视频资源文件不存在: {filename}")
                return None

            df = pd.read_excel(filename)
            non_empty_cells = [(i, j) for i in range(df.shape[0]) for j in range(df.shape[1]) if pd.notnull(df.iat[i, j])]
            if not non_empty_cells:
                logging.warning("文件中没有非空单元格。")
                return None
            random_cell = random.choice(non_empty_cells)
            row, col = random_cell
            cell_value = df.iat[row, col]
            return cell_value
        except Exception as e:
            logging.error(f"获取随机视频失败: {str(e)}")
            return None

    def end_chat(self, user_id: int):
        """
        手动结束会话
        """
        try:
            key = self._get_redis_key(user_id)
            self.redis.delete(key)
            logging.info(f"已清除用户 {user_id} 的 Redis 会话记录")
        except Exception as e:
            logging.error(f"清除会话失败: {e}")
