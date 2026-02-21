import logging
import base64
import os
import random
import subprocess
import tempfile
import pandas as pd

class Messageutil:
    """消息处理工具类，封装各种消息发送模式"""
    def __init__(self, Message_chat):
        self.Message_chat = Message_chat
    
    async def send_text(self, target_id, text, is_private=False, user_id=None):
        try:
            if is_private:
                await self.Message_chat.send_private_message(target_id, text)
            elif user_id:
                await self.Message_chat.send_group_message(target_id, user_id, text)
            else:
                await self.Message_chat.send_message(
                    target_id,
                    {'type': 'text', 'data': {'text': text}}
                )
        except Exception as e:
            logging.error(f"发送文本消息失败: {e}")
    
    async def send_image(self, target_id, image_url=None, image_file=None, image_base=None, is_private=False):
        try:
            image_data = {}
            if image_url:
                image_data['url'] = image_url
            elif image_file:
                image_data['file'] = image_file
            elif image_base:
                image_data['file'] = "base64://" + image_base
            message = {'type': 'image', 'data': image_data}
            if is_private:
                await self.Message_chat.send_private_message(target_id, message)
            else:
                await self.Message_chat.send_message(target_id, message)
        except Exception as e:
            logging.error(f"发送图片消息失败: {e}")
    
    async def send_video_recommendation(self, target_id, video_data, is_private=False):
        try:
            title = video_data.get('title', '无标题')
            cover_url = video_data.get('cover_url', '')
            jump_url = video_data.get('jump_url', '')
            videos = [
                {'type': 'text', 'data': {'text': f"要睡觉了吗？那就让小粥哄哥哥吧\n-------------------------------------\n视频标题：{title}\n"}},
                {'type': 'image', 'data': {'url': cover_url}},
                {'type': 'text', 'data': {'text': f"视频链接：{jump_url}"}}
            ]
            if is_private:
                await self.Message_chat.send_private_message(target_id, videos)
            else:
                await self.Message_chat.send_message(target_id, videos)
        except Exception as e:
            logging.error(f"发送视频推荐失败: {e}")
            if is_private:
                await self.Message_chat.send_private_message(target_id, f"发送视频失败: {str(e)}")
            else:
                await self.Message_chat.send_message(target_id, {'type': 'text', 'data': {'text': f"发送视频失败: {str(e)}"}})
    
    async def send_message(self, target_id, message, is_private=False):
        try:
            if is_private:
                await self.Message_chat.send_private_message(target_id, message)
            else:
                await self.Message_chat.send_message(target_id, message)
        except Exception as e:
            logging.error(f"发送消息失败: {e}")

def extract_image_urls(message_array):
    image_urls = []
    if not message_array:
        return image_urls
    for segment in message_array:
        if segment.get('type') == 'image':
            url = segment.get('data', {}).get('url')
            if url:
                image_urls.append(url)
    return image_urls

async def url_to_base64(url):
    try:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                temp_path = tmp.name
            curl_cmd = f'curl -k -A "Mozilla/5.0" -o "{temp_path}" "{url}"'
            subprocess.run(curl_cmd, shell=True, timeout=30)
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                with open(temp_path, "rb") as f:
                    image_data = f.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                os.unlink(temp_path)
                return base64_data
        except Exception as e:
            logging.error(f"使用curl下载图片失败: {str(e)}")
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
        logging.error("所有获取图片方法均失败")
        return None
    except Exception as e:
        logging.error(f"URL转Base64全局异常: {str(e)}")
        return None

def extract_at_content(raw_message, message_array, bot_qq='3435782327'):
    is_at_bot = False
    actual_content = raw_message
    if raw_message.startswith(f"[CQ:at,qq={bot_qq}"):
        is_at_bot = True
        at_end_index = raw_message.find(']')
        if (at_end_index > 0):
            actual_content = raw_message[at_end_index+1:].strip()
        else:
            actual_content = ""
    elif message_array and len(message_array) > 0:
        first_segment = message_array[0]
        if (first_segment.get('type') == 'at' and first_segment.get('data', {}).get('qq') == bot_qq):
            is_at_bot = True
            actual_content = ""
            for segment in message_array[1:]:
                if segment.get('type') == 'text':
                    actual_content += segment.get('data', {}).get('text', '')
            actual_content = actual_content.strip()
    if is_at_bot and not actual_content:
        actual_content = "你好"
    return is_at_bot, actual_content

