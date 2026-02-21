
---

# 群聊 util 模块接口说明

## MessageUtil.py

- `Messageutil.send_text(target_id, text, is_private=False, user_id=None)`
  - 发送文本消息（群聊/私聊/群@）。
- `Messageutil.send_image(target_id, image_url=None, image_file=None, image_base=None, is_private=False)`
  - 发送图片消息（支持URL、文件、本地base64）。
- `Messageutil.send_video_recommendation(target_id, video_data, is_private=False)`
  - 发送视频推荐消息（文本+图片+链接）。
- `Messageutil.send_message(target_id, message, is_private=False)`
  - 通用消息发送（群聊/私聊）。
- `extract_image_urls(message_array)`
  - 提取消息中的图片URL。
- `url_to_base64(url)`
  - 将图片URL转为base64字符串。
- `extract_at_content(raw_message, message_array, bot_qq='3435782327')`
  - 提取@机器人的消息内容。

---

## ImageDatabaseManager.py

- `ImageDatabaseManager.insert_image(qq_number, base64_data, check_similarity=True, similarity_threshold=3)`
  - 插入图片（自动查重/查相似）。
- `ImageDatabaseManager.find_similar_images(base64_data, threshold=5)`
  - 查找相似图片（感知哈希）。
- `ImageDatabaseManager.get_images_by_qq(qq_number)`
  - 按QQ号查询图片。
- `ImageDatabaseManager.delete_old_data(days=30)`
  - 删除指定天数前的旧图片数据。
- `ImageDatabaseManager.get_random_image()`
  - 随机获取一张图片base64数据。
- `ImageDatabaseManager.get_image_info_by_phash(phash)`
  - 根据感知哈希查询图片信息。
- `ImageDatabaseManager.delete_image_by_id(image_id)`
  - 根据图片ID删除图片。
- `ImageDatabaseManager.delete_image_by_phash(phash)`
  - 根据感知哈希删除图片。
- `ImageDatabaseManager.delete_exact_match(base64_data)`
  - 删除完全相同的图片。
- `ImageDatabaseManager.delete_most_similar(base64_data, threshold=5)`
  - 删除最相似的图片。
- `ImageDatabaseManager.close()`
  - 关闭数据库连接。

---

## MessageSender.py

- `Messagesender.send_message(group_id, message)`
  - 发送群普通消息（异步）。
- `Messagesender.send_group_message(group_id, user_id, message)`
  - 发送群@指定用户消息（异步）。
- `Messagesender.send_private_message(user_id, message)`
  - 发送私聊消息（异步）。

---

## DeepseekChat.py

- `Deepseekchat.get_fresh_session(user_id)`
  - 获取新会话（带预设）。
- `Deepseekchat.add_message(user_id, message, role)`
  - 添加消息到会话。
- `Deepseekchat.get_chat_response(user_id, message)`
  - 获取AI聊天回复（异步）。
- `Deepseekchat.clean_expired_sessions()`
  - 清理过期会话。
- `Deepseekchat.get_balance()`
  - 获取API账户余额（异步）。
- `Deepseekchat.get_random_video()`
  - 随机获取一个视频（从Excel）。
- `Deepseekchat.end_chat(user_id)`
  - 结束并清除用户会话。

---
