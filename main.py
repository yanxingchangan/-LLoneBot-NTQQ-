from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import redis
import json
import uuid
import logging
import os
from typing import Optional, Dict, Any

from util.DeepseekChat import Deepseekchat
from util.ImageDatabaseManager import ImageDatabaseManager
from util.MessageSender import Messagesender
from util.MessageUtil import Messageutil

from celeryapp.celery_tasks import process_deepseek_task

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config", "config.json")

app = FastAPI()

# 配置Jinja2模板
templates = Jinja2Templates(directory="templates")

# 连接到Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
QUEUE_NAME = 'deepseek_requests'

def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    default_config = {
        "api": {
            "api_key": "",
            "api_endpoint": "https://api.deepseek.com/user/balance",
            "chat_endpoint": "https://api.deepseek.com/chat/completions"
        },
        "system": {
            "admin_id": "",
            "bot_id": "",
            "target_group_id": "",
            "admin_server": "http://localhost:3000/send_msg",
            "local_server": "http://localhost:3000/send_group_msg",
            "bilibili_cookie": ""
        },
        "files": {
            "history_dir": "./history",
            "max_duplicate_hours": 1
        },
        "user_presets": {
            "2027378574": {
                "content": "You are a helpful assistant.",
                "role": "assistant"
            }
        },
        "default_preset": {
            "content": "You are a helpful assistant.",
            "role": "assistant"
        },
        "media": {
            "schedule_image": "http://i0.hdslb.com/bfs/new_dyn/e86bb1cfd0e9ab20ce928842a0803fff627432065.png",
            "songs_images_1": "file://E:/新建文件夹/粥歌1.jpg",
            "songs_images_2": "file://E:/新建文件夹/粥歌2.jpg"
        }
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for section in default_config:
                    if section not in config:
                        config[section] = default_config[section]
                    else:
                        for key in default_config[section]:
                            if key not in config[section]:
                                config[section][key] = default_config[section][key]
                return config
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return default_config
    return default_config

def save_config(config_data: Dict[str, Any]):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        return False

config = load_config()

ds = Deepseekchat(config)
img_manager = ImageDatabaseManager("image_data.db")
msg_sender = Messagesender(config)
msg_util = Messageutil(msg_sender)

def is_at_bot(raw_message, message_array):
    bot_qq = str(config["system"].get("bot_id", "3435782327"))
    if raw_message.startswith(f"[CQ:at,qq={bot_qq}"):
        return True
    if message_array and len(message_array) > 0:
        first_segment = message_array[0]
        if (first_segment.get('type') == 'at' and first_segment.get('data', {}).get('qq') == bot_qq):
            return True
    return False

@app.post("/reception")
async def handle_reception(request: Request):
    """
    接收上报数据，提取id和message字段，并将任务添加到Celery队列
    """
    try:
        data = await request.json()
        # 提取消息内容
        raw_message = data.get('raw_message', '')
        message_array = data.get('message', [])
        chat_user_id = data.get('user_id')
        group_id = data.get('group_id', "None")
        message_type = data.get('message_type')
        req_id = str(uuid.uuid4())

        import re
        should_create_task = False
        if message_type == "private" and chat_user_id == config["system"].get("admin_id", ""):
            should_create_task = True
        elif message_type == "group":
            if is_at_bot(raw_message, message_array) or ("小羽毛" in raw_message):
                should_create_task = True
            elif re.search(r"来张美图|粥歌|视频推荐|粥表", raw_message):
                should_create_task = True

        if should_create_task:
            task = {
                "id": req_id,
                "message": raw_message,
                "is_private": True if message_type == "private" else False,
                "user_id": chat_user_id,
                "group_id": group_id,
                "message_array": message_array
            }
            process_deepseek_task.delay(task)
            logger.info(f"Task queued: {req_id}")
            return {
                "status": "queued",
                "id": req_id,
                "message": "Request has been queued for processing"
            }
        else:
            return {
                "status": "ignored",
                "message": "Not @bot and no trigger keyword, task not created."
            }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/", response_class=HTMLResponse)
async def config_page(request: Request):
    """显示配置页面"""
    config = load_config()
    return templates.TemplateResponse(
        "config.html", 
        {"request": request, "config": config}
    )

@app.post("/save-config")
async def save_config_api(
    api_key: str = Form(...),
    api_endpoint: str = Form(...),
    chat_endpoint: str = Form(...),
    admin_id: str = Form(...),
    bot_id: str = Form(...),
    target_group_id: str = Form(...),
    admin_server: str = Form(...),
    local_server: str = Form(...),
    bilibili_cookie: str = Form(...),
    history_dir: str = Form(...),
    max_duplicate_hours: int = Form(...)
):
    """保存配置到config.json"""
    config_data = load_config()
    
    # 更新API配置
    config_data["api"]["api_key"] = api_key
    config_data["api"]["api_endpoint"] = api_endpoint
    config_data["api"]["chat_endpoint"] = chat_endpoint
    
    # 更新系统配置
    config_data["system"]["admin_id"] = admin_id
    config_data["system"]["bot_id"] = bot_id
    config_data["system"]["target_group_id"] = target_group_id
    config_data["system"]["admin_server"] = admin_server
    config_data["system"]["local_server"] = local_server
    config_data["system"]["bilibili_cookie"] = bilibili_cookie
    
    # 更新文件配置
    config_data["files"]["history_dir"] = history_dir
    config_data["files"]["max_duplicate_hours"] = max_duplicate_hours
    
    if save_config(config_data):
        return RedirectResponse(url="/?saved=true", status_code=303)
    else:
        raise HTTPException(status_code=500, detail="Failed to save config")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 检查Redis连接
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except redis.ConnectionError:
        raise HTTPException(status_code=500, detail="Redis connection failed")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090)
