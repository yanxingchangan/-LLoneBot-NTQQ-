import time
import secrets
from typing import Dict, Set, Tuple, Optional, ClassVar
from dataclasses import dataclass, field

# 权限组定义
class Role:
    SUPER_ADMIN = 'super_admin'
    DB_ADMIN = 'db_admin'
    GROUP_ADMIN = 'group_admin'

@dataclass
class AuthManager:
    """授权管理器类，支持多权限组"""
    super_admin_id: int
    db_admins: Set[int] = field(default_factory=set)
    group_admins: Set[int] = field(default_factory=set)
    authorized_users: Set[int] = field(default_factory=set)

    ADMIN_COMMANDS: ClassVar[Dict[str, str]] = {
        "/auth add <role> <user_id>": "添加指定角色的管理员",
        "/auth remove <role> <user_id>": "移除指定角色的管理员", 
        "/auth list": "查看所有授权用户列表",
        "/auth clear": "移除所有用户授权（超级管理员除外）",
        "/auth command": "显示管理员命令"
    }

    def __post_init__(self):
        self.authorized_users.add(self.super_admin_id)
        self.db_admins.add(self.super_admin_id)
        self.group_admins.add(self.super_admin_id)

    def is_authorized(self, user_id: int) -> bool:
        return (
            user_id in self.authorized_users or
            user_id in self.db_admins or
            user_id in self.group_admins or
            user_id == self.super_admin_id
        )

    def is_super_admin(self, user_id: int) -> bool:
        return user_id == self.super_admin_id

    def is_db_admin(self, user_id: int) -> bool:
        return user_id in self.db_admins

    def is_group_admin(self, user_id: int) -> bool:
        return user_id in self.group_admins



    async def handle_auth_command(self, user_id: int, message: str) -> Dict[str, str]:
        """处理授权命令，支持多权限组"""
        parts = message.strip().split()

        if not parts or parts[0] != "/auth":
            return {"message": "无效的命令格式"}

        # 非管理员无权操作
        if not self.is_super_admin(user_id) and not self.is_db_admin(user_id) and not self.is_group_admin(user_id):
            return {"message": "权限不足"}

        # 管理员命令处理
        if len(parts) == 2:
            command = parts[1]
            if command == "list":
                return {"message": self.get_user_list()}
            elif command == "command":
                return {"message": self.get_command_list()}
            elif command == "clear":
                return self.clear_all_authorizations()

        if len(parts) == 3:
            action, target = parts[1:]
            try:
                target_id = int(target)
                # 默认添加/移除普通授权用户
                if action == "add":
                    return {"message": self.add_user(target_id)}
                elif action == "remove":
                    return {"message": self.remove_user(target_id)}
            except ValueError:
                return {"message": "用户ID必须为数字"}

        # 新增：支持角色管理员的添加/移除
        if len(parts) == 4:
            action, role, target = parts[1:]
            try:
                target_id = int(target)
                if action == "add":
                    return {"message": self.add_role_admin(role, target_id)}
                elif action == "remove":
                    return {"message": self.remove_role_admin(role, target_id)}
            except ValueError:
                return {"message": "用户ID必须为数字"}

        return {"message": "无效的命令格式"}



    def add_user(self, target_id: int) -> str:
        if target_id in self.authorized_users:
            return f"用户 {target_id} 已在授权列表中"
        self.authorized_users.add(target_id)
        return f"已添加用户 {target_id} 到授权列表"

    def remove_user(self, target_id: int) -> str:
        if target_id == self.super_admin_id:
            return "不能移除超级管理员权限"
        if target_id not in self.authorized_users:
            return f"用户 {target_id} 不在授权列表中"
        self.authorized_users.remove(target_id)
        return f"已从授权列表中移除用户 {target_id}"

    def add_role_admin(self, role: str, target_id: int) -> str:
        if role == Role.DB_ADMIN:
            if target_id in self.db_admins:
                return f"用户 {target_id} 已是数据库管理员"
            self.db_admins.add(target_id)
            return f"已添加用户 {target_id} 为数据库管理员"
        elif role == Role.GROUP_ADMIN:
            if target_id in self.group_admins:
                return f"用户 {target_id} 已是用户组成员管理员"
            self.group_admins.add(target_id)
            return f"已添加用户 {target_id} 为用户组成员管理员"
        elif role == Role.SUPER_ADMIN:
            return "超级管理员不可更改"
        else:
            return "无效的角色类型"

    def remove_role_admin(self, role: str, target_id: int) -> str:
        if role == Role.DB_ADMIN:
            if target_id == self.super_admin_id:
                return "不能移除超级管理员权限"
            if target_id not in self.db_admins:
                return f"用户 {target_id} 不是数据库管理员"
            self.db_admins.remove(target_id)
            return f"已移除用户 {target_id} 的数据库管理员权限"
        elif role == Role.GROUP_ADMIN:
            if target_id == self.super_admin_id:
                return "不能移除超级管理员权限"
            if target_id not in self.group_admins:
                return f"用户 {target_id} 不是用户组成员管理员"
            self.group_admins.remove(target_id)
            return f"已移除用户 {target_id} 的用户组成员管理员权限"
        elif role == Role.SUPER_ADMIN:
            return "超级管理员不可更改"
        else:
            return "无效的角色类型"

    def get_user_list(self) -> str:
        result = []
        result.append(f"超级管理员: {self.super_admin_id}")
        result.append(f"数据库管理员: {sorted(self.db_admins)}")
        result.append(f"用户组成员管理员: {sorted(self.group_admins)}")
        result.append(f"普通授权用户: {sorted(self.authorized_users - {self.super_admin_id, *self.db_admins, *self.group_admins})}")
        return "\n".join(result)

    def get_command_list(self) -> str:
        return "\n".join([f"{cmd}: {desc}" for cmd, desc in self.ADMIN_COMMANDS.items()])

    def clear_all_authorizations(self):
        """移除所有非超级管理员的授权"""
        try:
            before_count = len(self.authorized_users - {self.super_admin_id})
            self.authorized_users = {self.super_admin_id}
            self.db_admins = {self.super_admin_id}
            self.group_admins = {self.super_admin_id}
            return {"message": f"已清除所有用户授权（超级管理员除外），共移除 {before_count} 个用户"}
        except Exception as e:
            return {"message": f"清除授权失败: {str(e)}"}

