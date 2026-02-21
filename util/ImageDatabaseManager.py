import sqlite3
import hashlib
import base64
from PIL import Image
from io import BytesIO
import imagehash
from datetime import datetime

class ImageDatabaseManager:
    """管理 SQLite 数据库中的图片 Base64 数据"""
    
    def __init__(self, db_path: str = "image_data.db"):
        """
        初始化数据库连接并创建表
        :param db_path: 数据库文件路径（默认当前目录的 image_data.db）
        """
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        """创建数据表（如果不存在）"""
        sql = """
        CREATE TABLE IF NOT EXISTS image_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qq_number TEXT NOT NULL,
            base64_data TEXT NOT NULL,
            phash TEXT UNIQUE NOT NULL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_qq_number ON image_store (qq_number);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_phash ON image_store (phash);
        """
        self.conn.executescript(sql)
        self.conn.commit()

    def _calculate_phash(self, base64_data: str) -> tuple[str, str]:
        """
        计算图片的感知哈希值（Perceptual Hash）
        :return: (phash值, 日志信息)
        """
        try:
            image_data = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_data))
            phash = imagehash.phash(image)
            return str(phash), "感知哈希计算成功"
        except Exception as e:
            fallback_hash = hashlib.sha256(base64_data.encode()).hexdigest()
            return fallback_hash, f"感知哈希计算失败，降级为SHA-256: {str(e)}"

    def find_similar_images(self, base64_data: str, threshold: int = 5) -> tuple[list, str]:
        """
        查找相似图片（基于感知哈希）
        :param base64_data: 要比较的图片Base64数据
        :param threshold: 相似度阈值（汉明距离，越小越相似，0表示完全相同）
        :return: (相似图片列表, 日志信息)
        """
        try:
            phash_result, phash_log = self._calculate_phash(base64_data)
            target_phash = imagehash.hex_to_hash(phash_result)
            
            # 获取所有图片的哈希值
            cursor = self.conn.execute("SELECT id, qq_number, phash, upload_time FROM image_store")
            similar_images = []
            
            for row in cursor.fetchall():
                stored_phash = imagehash.hex_to_hash(row[2])
                # 计算汉明距离
                distance = target_phash - stored_phash
                
                if distance <= threshold:
                    similar_images.append({
                        'id': row[0],
                        'qq_number': row[1],
                        'phash': row[2],
                        'upload_time': row[3],
                        'similarity_distance': distance
                    })
            
            # 按相似度排序（距离越小越相似）
            sorted_images = sorted(similar_images, key=lambda x: x['similarity_distance'])
            log_msg = f"相似图片查找完成，找到 {len(sorted_images)} 张相似图片（阈值: {threshold}）"
            return sorted_images, log_msg
            
        except Exception as e:
            return [], f"查找相似图片失败: {str(e)}"

    def insert_image(self, qq_number: str, base64_data: str, check_similarity: bool = True, similarity_threshold: int = 3) -> tuple[bool, str]:
        """
        插入数据（自动校验图片是否重复或相似）
        :param qq_number: 用户QQ号
        :param base64_data: 图片的Base64编码字符串
        :param check_similarity: 是否检查相似图片（默认True）
        :param similarity_threshold: 相似度阈值（默认3，表示很相似）
        :return: (True=插入成功/False=插入失败, 日志信息)
        """
        try:
            # 计算感知哈希值
            data_phash, phash_log = self._calculate_phash(base64_data)
            
            # 先检查完全相同的图片
            cursor = self.conn.execute(
                "SELECT 1 FROM image_store WHERE phash = ?", 
                (data_phash,)
            )
            if cursor.fetchone():
                return False, f"图片已存在（完全相同），phash: {data_phash}"
            
            # 检查相似图片
            if check_similarity:
                similar_images, similar_log = self.find_similar_images(base64_data, similarity_threshold)
                if similar_images:
                    return False, f"发现 {len(similar_images)} 张相似图片，最相似距离: {similar_images[0]['similarity_distance']}"

            # 插入新数据
            sql = """
                INSERT INTO image_store (qq_number, base64_data, phash)
                VALUES (?, ?, ?)
            """
            self.conn.execute(sql, (qq_number, base64_data, data_phash))
            self.conn.commit()
            return True, f"图片插入成功，QQ: {qq_number}, phash: {data_phash}"
        except sqlite3.IntegrityError as e:
            return False, f"唯一性冲突（并发场景）: {str(e)}"
        except sqlite3.Error as e:
            return False, f"数据库操作失败: {str(e)}"

    def get_images_by_qq(self, qq_number: str) -> tuple[list, str]:
        """
        按QQ号查询所有关联的图片数据
        :param qq_number: 要查询的QQ号
        :return: (查询结果列表（按时间倒序）, 日志信息)
        """
        try:
            sql = "SELECT * FROM image_store WHERE qq_number = ? ORDER BY upload_time DESC"
            cursor = self.conn.execute(sql, (qq_number,))
            results = cursor.fetchall()
            return results, f"查询QQ {qq_number} 的图片完成，找到 {len(results)} 张图片"
        except sqlite3.Error as e:
            return [], f"查询数据失败: {str(e)}"

    def delete_old_data(self, days: int = 30) -> tuple[int, str]:
        """
        删除指定天数前的旧数据
        :param days: 保留天数（默认30天）
        :return: (被删除的行数, 日志信息)
        """
        try:
            sql = "DELETE FROM image_store WHERE upload_time < DATE('now', ?)"
            cursor = self.conn.execute(sql, (f'-{days} days',))
            self.conn.commit()
            deleted_count = cursor.rowcount
            return deleted_count, f"数据清理完成，删除了 {deleted_count} 条 {days} 天前的旧数据"
        except sqlite3.Error as e:
            return 0, f"删除旧数据失败: {str(e)}"

    def get_random_image(self) -> tuple[str | None, str]:
        """
        随机获取一条图片的 Base64 数据
        :return: (Base64 字符串（若无数据返回 None）, 日志信息)
        """
        try:
            sql = """
                SELECT base64_data 
                FROM image_store 
                ORDER BY RANDOM() 
                LIMIT 1
            """
            cursor = self.conn.execute(sql)
            result = cursor.fetchone()
            if result:
                return result[0], "随机图片获取成功"
            else:
                return None, "数据库中没有图片数据"
        except sqlite3.Error as e:
            return None, f"随机查询失败: {str(e)}"

    def get_image_info_by_phash(self, phash: str) -> tuple[dict | None, str]:
        """
        根据感知哈希获取图片信息
        :param phash: 感知哈希值
        :return: (图片信息字典或None, 日志信息)
        """
        try:
            sql = "SELECT * FROM image_store WHERE phash = ?"
            cursor = self.conn.execute(sql, (phash,))
            result = cursor.fetchone()
            
            if result:
                image_info = {
                    'id': result[0],
                    'qq_number': result[1],
                    'base64_data': result[2],
                    'phash': result[3],
                    'upload_time': result[4]
                }
                return image_info, f"根据phash查询成功，找到图片ID: {result[0]}"
            return None, f"未找到phash为 {phash} 的图片"
        except sqlite3.Error as e:
            return None, f"查询图片信息失败: {str(e)}"

    def delete_image_by_id(self, image_id: int) -> tuple[bool, str]:
        """
        根据图片ID删除图片
        :param image_id: 图片ID
        :return: (True=删除成功/False=删除失败, 日志信息)
        """
        try:
            # 先检查图片是否存在
            cursor = self.conn.execute("SELECT id, qq_number FROM image_store WHERE id = ?", (image_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, f"图片ID {image_id} 不存在"
            
            # 执行删除
            cursor = self.conn.execute("DELETE FROM image_store WHERE id = ?", (image_id,))
            self.conn.commit()
            
            if cursor.rowcount > 0:
                return True, f"成功删除图片，ID: {image_id}, QQ: {result[1]}"
            else:
                return False, f"删除图片失败，ID: {image_id}"
                
        except sqlite3.Error as e:
            return False, f"删除操作失败: {str(e)}"

    def delete_image_by_phash(self, phash: str) -> tuple[bool, str]:
        """
        根据感知哈希删除图片
        :param phash: 感知哈希值
        :return: (True=删除成功/False=删除失败, 日志信息)
        """
        try:
            # 先检查图片是否存在
            cursor = self.conn.execute("SELECT id, qq_number FROM image_store WHERE phash = ?", (phash,))
            result = cursor.fetchone()
            
            if not result:
                return False, f"phash {phash} 对应的图片不存在"
            
            # 执行删除
            cursor = self.conn.execute("DELETE FROM image_store WHERE phash = ?", (phash,))
            self.conn.commit()
            
            if cursor.rowcount > 0:
                return True, f"成功删除图片，ID: {result[0]}, QQ: {result[1]}, phash: {phash}"
            else:
                return False, f"删除图片失败，phash: {phash}"
                
        except sqlite3.Error as e:
            return False, f"删除操作失败: {str(e)}"

    def delete_exact_match(self, base64_data: str) -> tuple[bool, str]:
        """
        删除与给定图片完全相同的图片
        :param base64_data: 图片的Base64编码字符串
        :return: (True=删除成功/False=删除失败或未找到, 日志信息)
        """
        try:
            # 计算感知哈希
            phash_result, phash_log = self._calculate_phash(base64_data)
            
            # 根据phash删除图片
            success, delete_log = self.delete_image_by_phash(phash_result)
            
            if success:
                return True, f"删除完全相同的图片成功: {delete_log}"
            else:
                return False, f"未找到完全相同的图片或删除失败: {delete_log}"
                
        except Exception as e:
            return False, f"删除完全匹配图片失败: {str(e)}"

    def delete_most_similar(self, base64_data: str, threshold: int = 5) -> tuple[bool, str]:
        """
        删除与给定图片最相似的图片
        :param base64_data: 图片的Base64编码字符串
        :param threshold: 相似度阈值
        :return: (True=删除成功/False=删除失败或未找到, 日志信息)
        """
        try:
            # 查找相似图片
            similar_images, search_log = self.find_similar_images(base64_data, threshold)
            
            if not similar_images:
                return False, f"未找到相似度在阈值 {threshold} 内的图片"
            
            # 获取最相似的图片（第一个，距离最小）
            most_similar = similar_images[0]
            
            # 删除最相似的图片
            success, delete_log = self.delete_image_by_id(most_similar['id'])
            
            if success:
                return True, f"删除最相似图片成功，相似距离: {most_similar['similarity_distance']}, {delete_log}"
            else:
                return False, f"删除最相似图片失败: {delete_log}"
                
        except Exception as e:
            return False, f"删除最相似图片操作失败: {str(e)}"

    def close(self):
        """关闭数据库连接"""
        self.conn.close()