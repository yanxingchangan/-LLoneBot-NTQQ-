import logging
import httpx
import json
from .MessageUtil import Messageutil
from .ImageDatabaseManager import ImageDatabaseManager
from .DeepseekChat import Deepseekchat

# 读取config.json
with open('config/config.json', 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)



async def fetch_video_info(bvid):
    """获取B站视频信息"""
    try:
        videos_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Cookie": CONFIG["system"]["bilibili_cookie"]
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(videos_url, headers=headers, timeout=10.0)
        if response.status_code != 200:
            logging.error(f"获取视频信息失败: 状态码 {response.status_code}")
            return None
        data = response.json()
        items = data.get('data', {})
        return {
            'title': items.get('title', '无标题'),
            'cover_url': items.get('pic', ''),
            'jump_url': f"https://www.bilibili.com/video/{bvid}"
        }
    except Exception as e:
        logging.error(f"获取视频信息出错: {str(e)}")
        return None

async def handle_video_request(target_id, is_private=False, user_id=None, chat_manager=None, msg_util=None):
    """处理视频推荐请求"""
    try:
        bvs = chat_manager.get_random_video() if chat_manager else None
        if not bvs:
            await msg_util.send_text(
                target_id,
                "抱歉，未找到可推荐的视频",
                is_private=is_private
            )
            return {}
        video_data = await fetch_video_info(bvs)
        if not video_data:
            await msg_util.send_text(
                target_id,
                "获取视频信息失败",
                is_private=is_private
            )
            return {}
        await msg_util.send_video_recommendation(target_id, video_data, is_private)
        return {}
    except Exception as e:
        logging.error(f"处理视频请求时发生错误: {str(e)}")
        await msg_util.send_text(
            target_id,
            f"获取视频推荐失败: {str(e)}",
            is_private=is_private
        )
        return {}

async def handle_songs_images(target_id, is_private=False, msg_util=None):
    """发送粥歌图片"""
    try:
        for image_key in ['songs_images_1', 'songs_images_2']:
            await msg_util.send_image(
                target_id,
                image_file=CONFIG["media"][image_key],
                is_private=is_private
            )
        logging.info(f"发送粥歌图片成功: {'私聊' if is_private else '群聊'}")
        return {}
    except Exception as e:
        logging.error(f"发送粥歌图片时发生错误: {str(e)}")
        await msg_util.send_text(
            target_id,
            f"发送图片失败: {str(e)}",
            is_private=is_private
        )
        return {}

async def handle_random_image(target_id, is_private=False, image_db=None, msg_util=None):
    """随机发送一张美图"""
    try:
        base64_data, _ = image_db.get_random_image() if image_db else (None, None)
        if not base64_data:
            await msg_util.send_text(
                target_id,
                "暂无图片可以显示",
                is_private=is_private
            )
            return {}
        await msg_util.send_image(
            target_id,
            image_base=base64_data,
            is_private=is_private
        )
        logging.info(f"成功发送随机图片: {'私聊' if is_private else '群聊'}")
        return {}
    except Exception as e:
        logging.error(f"发送随机图片时发生错误: {str(e)}")
        await msg_util.send_text(
            target_id,
            f"获取图片失败: {str(e)}",
            is_private=is_private
        )
        return {}

async def handle_schedule_image(target_id, is_private=False, msg_util=None):
    """发送粥表图片"""
    try:
        await msg_util.send_image(
            target_id,
            image_url=CONFIG["media"]["schedule_image"],
            is_private=is_private
        )
        logging.info(f"发送粥表图片成功: {'私聊' if is_private else '群聊'}")
        return {}
    except Exception as e:
        logging.error(f"发送粥表图片时发生错误: {str(e)}")
        await msg_util.send_text(
            target_id,
            f"发送粥表失败: {str(e)}",
            is_private=is_private
        )
        return {}
