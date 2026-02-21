from celeryapp.celery_app import app, chat_manager, image_db, msg_util
from util.MessageUtil import url_to_base64
from util.TaskReplyUtil import handle_video_request, handle_schedule_image, handle_songs_images, handle_random_image
import asyncio
import logging
import asyncio
import json
import random
import re

logger = logging.getLogger(__name__)

special_handlers = {
    "来张美图": lambda target_id, is_private: handle_random_image(target_id, is_private, image_db=image_db, msg_util=msg_util),
    "粥歌": lambda target_id, is_private: handle_songs_images(target_id, is_private, msg_util=msg_util),
    "视频推荐": lambda target_id, is_private: handle_video_request(target_id, is_private, chat_manager=chat_manager, msg_util=msg_util),
    "粥表": lambda target_id, is_private: handle_schedule_image(target_id, is_private, msg_util=msg_util)
}      

@app.task(name='process_deepseek_task', bind=True, max_retries=3)
def process_deepseek_task(self, task_data):
    """
    处理DeepSeek任务的Celery任务
    """
    try:
        task = json.loads(task_data) if isinstance(task_data, str) else task_data
        user_id = task.get('user_id')
        group_id = task.get('group_id')
        message_array = task.get('message_array', [])
        raw_message = task.get('message', '')
        is_private = task.get('is_private', False)
        content = raw_message

        # 检查是否包含图片
        has_image = False
        image_urls = []
        if message_array:
            for segment in message_array:
                if segment.get('type') == 'image':
                    url = segment.get('data', {}).get('url')
                    if url:
                        image_urls.append(url)
                        has_image = True

        if has_image and is_private and user_id == "2027378574":
            # 处理图片逻辑
            image_count = 0
            for url in image_urls:
                logging.info(f"处理图片URL: {url}")
                base64_data = asyncio.run(url_to_base64(url))
                if base64_data:
                    success, msg = image_db.insert_image(str(user_id), base64_data)
                    if success:
                        image_count += 1
                        logging.info(f"成功保存用户 {user_id} 的图片到数据库")
                    else:
                        logging.info(f"图片已存在或保存失败，用户: {user_id}，原因: {msg}")
            reply_text = f"已成功保存 {image_count} 张图片" if image_count > 0 else "图片保存失败或已存在"
            asyncio.run(msg_util.send_text(user_id, reply_text, is_private=True))
            return {f"已成功保存 {image_count} 张图片" if image_count > 0 else "图片保存失败或已存在"}

        pattern = r"^(来张美图|粥歌|视频推荐|粥表)$"
        if re.match(pattern, content):
            handler = special_handlers[content]
            target_id = user_id if is_private else group_id
            asyncio.run(handler(target_id, is_private))
            return {"status": "success", "handled_special_request": content}
        
        if is_private and user_id == "2027378574":
            # 处理私聊文本消息
            code, answer = asyncio.run(chat_manager.get_chat_response(user_id, content))
            if code != 200:
                logging.error(f"AI响应错误: {code}, {answer}")
                asyncio.run(msg_util.send_text(user_id, f"用户 {user_id} 请求出错: {answer}", is_private=True))
                return {"status": "error", "code": code, "message": answer}
            asyncio.run(msg_util.send_text(user_id, answer, is_private=True))
            return {"status": "success", "user_id": user_id}
        elif not is_private:
            # 群聊消息，判断是否@机器人或包含“小羽毛”
            bot_qq = '3435782327'
            is_at_bot = False
            actual_content = content
            # 方法1: 检查raw_message
            if content.startswith(f"[CQ:at,qq={bot_qq}"):
                is_at_bot = True
                at_end_index = content.find(']')
                if at_end_index > 0:
                    actual_content = content[at_end_index+1:].strip()
                else:
                    actual_content = ""
            # 方法2: 检查message_array
            elif message_array and len(message_array) > 0:
                first_segment = message_array[0]
                if (first_segment.get('type') == 'at' and first_segment.get('data', {}).get('qq') == bot_qq):
                    is_at_bot = True
                    # 如果有多个消息段，提取文本内容
                    actual_content = ""
                    for segment in message_array[1:]:
                        if segment.get('type') == 'text':
                            actual_content += segment.get('data', {}).get('text', '')
                    actual_content = actual_content.strip()
            # 如果@了机器人且内容为空，设置默认值
            if is_at_bot and not actual_content:
                actual_content = "你好"
            # 只要@机器人，必回复
            if is_at_bot:
                code, answer = asyncio.run(chat_manager.get_chat_response(user_id, actual_content))
                if code != 200:
                    logging.error(f"AI响应错误: {code}, {answer}")
                    asyncio.run(msg_util.send_text(group_id, f"用户 {user_id} 请求出错: {answer}", is_private=False, user_id=str(user_id)))
                    return {"status": "error", "code": code, "message": answer}
                asyncio.run(msg_util.send_text(group_id, answer, is_private=False, user_id=str(user_id)))
                return {"status": "success", "user_id": user_id}
            if "小羽毛" in content:
                if random.random() < 0.3:
                    code, answer = asyncio.run(chat_manager.get_chat_response(user_id, content))
                    if code != 200:
                        logging.error(f"AI响应错误: {code}, {answer}")
                        asyncio.run(msg_util.send_text(group_id, f"用户 {user_id} 请求出错: {answer}", is_private=False, user_id=str(user_id)))
                        return {"status": "error", "code": code, "message": answer}
                    asyncio.run(msg_util.send_text(group_id, answer, is_private=False, user_id=str(user_id)))
                    return {"status": "success", "user_id": user_id, "trigger": "keyword_xiaoyumao"}
            return {"status": "ignored", "reason": "not at bot or keyword not triggered"}
        
    except Exception as e:
        logger.error(f"处理任务时发生错误: {str(e)}")
        # 重试逻辑
        try:
            self.retry(exc=e, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(f"任务重试次数已达上限: {task_data}")
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": str(e)}
