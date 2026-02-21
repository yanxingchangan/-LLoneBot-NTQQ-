from celery import Celery

import logging
import json
import os
from util.DeepseekChat import Deepseekchat
from util.ImageDatabaseManager import ImageDatabaseManager
from util.MessageSender import Messagesender
from util.MessageUtil import Messageutil, url_to_base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('config/config.json', 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

app = Celery(
    'deepseek_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['celeryapp.celery_tasks']
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_routes={
        'process_deepseek_task': {'queue': 'deepseek_requests'}
    },
    task_default_queue='deepseek_requests',
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


# 计算 images.db 的绝对路径（当前文件上一级目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "image_data.db")

# 初始化组件
chat_manager = Deepseekchat(CONFIG)
image_db = ImageDatabaseManager(DB_PATH)
msg_sender = Messagesender(CONFIG)
msg_util = Messageutil(msg_sender)

if __name__ == '__main__':
    app.start()
