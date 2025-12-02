"""
Config Manager - Đọc/ghi config từ config.py cho Edge Backend
"""
import os
import re
from typing import Dict, Any


class ConfigManager:
    """Quản lý đọc/ghi config từ file config.py cho Edge Backend"""

    def __init__(self, config_file="config.py"):
        self.config_file = config_file

    def get_config(self) -> Dict[str, Any]:
        """Đọc config hiện tại"""
        import config

        return {
            "camera": {
                "id": config.CAMERA_ID,
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE,
                "location": config.CAMERA_LOCATION,
                "gate": getattr(config, "GATE", 1),
            },
            "server": {
                "host": config.SERVER_HOST,
                "port": config.SERVER_PORT,
            },
            "database": {
                "db_file": config.DB_FILE,
            },
            "barrier": {
                "enabled": config.BARRIER_ENABLED,
                "gpio_pin": config.BARRIER_GPIO_PIN,
                "auto_close_time": config.BARRIER_AUTO_CLOSE_TIME,
            },
            "central": {
                "server_url": config.CENTRAL_SERVER_URL,
                "ws_url": getattr(config, "CENTRAL_WS_URL", ""),
                "sync_enabled": config.CENTRAL_SYNC_ENABLED,
            },
            "offline": {
                "exit_strategy": getattr(config, "OFFLINE_EXIT_STRATEGY", "ALLOW_DEFAULT_FEE"),
                "default_exit_fee": getattr(config, "DEFAULT_EXIT_FEE", 50000),
            },
        }

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Cập nhật config vào file config.py"""
        try:
            # Đọc file hiện tại
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update từng section
            if "camera" in new_config:
                cam_config = new_config["camera"]
                if "type" in cam_config:
                    content = self._update_value(content, "CAMERA_TYPE", cam_config["type"], is_string=True)
                if "name" in cam_config:
                    content = self._update_value(content, "CAMERA_NAME", cam_config["name"], is_string=True)
                if "location" in cam_config:
                    content = self._update_value(content, "CAMERA_LOCATION", cam_config["location"], is_string=True)
                if "id" in cam_config:
                    content = self._update_value(content, "CAMERA_ID", cam_config["id"])
                if "gate" in cam_config:
                    content = self._update_value(content, "GATE", cam_config["gate"])

            if "server" in new_config:
                server_config = new_config["server"]
                if "host" in server_config:
                    content = self._update_value(content, "SERVER_HOST", server_config["host"], is_string=True)
                if "port" in server_config:
                    content = self._update_value(content, "SERVER_PORT", server_config["port"])

            if "database" in new_config:
                db_config = new_config["database"]
                if "db_file" in db_config:
                    content = self._update_value(content, "DB_FILE", db_config["db_file"], is_string=True)

            if "barrier" in new_config:
                barrier_config = new_config["barrier"]
                if "enabled" in barrier_config:
                    content = self._update_value(content, "BARRIER_ENABLED", barrier_config["enabled"], is_bool=True)
                if "gpio_pin" in barrier_config:
                    content = self._update_value(content, "BARRIER_GPIO_PIN", barrier_config["gpio_pin"])
                if "auto_close_time" in barrier_config:
                    content = self._update_value(content, "BARRIER_AUTO_CLOSE_TIME", barrier_config["auto_close_time"], is_float=True)

            if "central" in new_config:
                central_config = new_config["central"]
                if "server_url" in central_config:
                    content = self._update_value(content, "CENTRAL_SERVER_URL", central_config["server_url"], is_string=True)
                if "ws_url" in central_config:
                    content = self._update_value(content, "CENTRAL_WS_URL", central_config["ws_url"], is_string=True)
                if "sync_enabled" in central_config:
                    content = self._update_value(content, "CENTRAL_SYNC_ENABLED", central_config["sync_enabled"], is_bool=True)

            if "offline" in new_config:
                offline_config = new_config["offline"]
                if "exit_strategy" in offline_config:
                    content = self._update_value(content, "OFFLINE_EXIT_STRATEGY", offline_config["exit_strategy"], is_string=True)
                if "default_exit_fee" in offline_config:
                    content = self._update_value(content, "DEFAULT_EXIT_FEE", offline_config["default_exit_fee"])

            # Ghi lại file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Reload config module
            import importlib
            import config
            importlib.reload(config)

            return True
        except Exception as e:
            print(f"Error updating config: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_camera_type(self, camera_type: str) -> bool:
        """Cập nhật chỉ camera type"""
        return self.update_config({
            "camera": {
                "type": camera_type
            }
        })

    def _update_value(self, content: str, key: str, value: Any, is_string: bool = False, is_bool: bool = False, is_float: bool = False) -> str:
        """Update giá trị trong content - giữ lại comment nếu có"""
        # Pattern để tìm dòng có key = value (có thể có comment sau đó)
        # Ví dụ: CAMERA_TYPE = "ENTRY"  # comment
        # Match: key = value (giữ lại comment sau #)
        pattern = rf'^(\s*){key}\s*=\s*[^\n#]*(#.*)?$'
        
        def replace_func(match):
            indent = match.group(1)  # Giữ lại indentation
            comment = match.group(2) if match.group(2) else ""  # Giữ lại comment nếu có
            
            if is_string:
                new_line = f'{indent}{key} = "{value}"'
            elif is_bool:
                new_line = f'{indent}{key} = {str(value)}'
            elif is_float:
                new_line = f'{indent}{key} = {float(value)}'
            else:
                new_line = f'{indent}{key} = {value}'
            
            # Thêm lại comment nếu có
            if comment:
                new_line += f"  {comment}"
            
            return new_line
        
        # Tìm xem có match không
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            print(f"Warning: Key {key} not found in config file")
            return content
        
        # Replace giá trị
        new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
        return new_content

