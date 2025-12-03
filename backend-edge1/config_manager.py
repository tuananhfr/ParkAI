"""
Config Manager - Đọc/ghi config từ config.py cho Edge Backend
"""
import os
import re
import socket
from typing import Dict, Any


class ConfigManager:
    """Quản lý đọc/ghi config từ file config.py cho Edge Backend"""

    def __init__(self, config_file="config.py"):
        self.config_file = config_file
        self._cached_ip = None

    def _get_local_ip(self) -> str:
        """Lấy IP thực tế của máy (không phải localhost)"""
        if self._cached_ip:
            return self._cached_ip
        
        try:
            # Kết nối đến một địa chỉ bên ngoài để biết IP của interface mạng chính
            # Không thực sự gửi dữ liệu, chỉ để biết IP của máy
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # Kết nối đến một địa chỉ không cần phải có (chỉ để lấy IP local)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                # Fallback: lấy IP từ hostname
                ip = socket.gethostbyname(socket.gethostname())
            finally:
                s.close()
            
            # Nếu vẫn là localhost, thử cách khác
            if ip in ['127.0.0.1', 'localhost', '::1']:
                # Lấy IP từ tất cả interfaces
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
            
            self._cached_ip = ip
            return ip
        except Exception as e:
            # Nếu không lấy được, trả về IP mặc định hoặc từ config
            print(f"Warning: Could not detect local IP: {e}")
            return "127.0.0.1"

    def get_config(self) -> Dict[str, Any]:
        """Đọc config hiện tại"""
        import config
        from urllib.parse import urlparse

        # Parse central server URL để lấy IP
        central_ip = ""
        if hasattr(config, "CENTRAL_SERVER_URL") and config.CENTRAL_SERVER_URL:
            try:
                parsed = urlparse(config.CENTRAL_SERVER_URL)
                central_ip = parsed.netloc.split(":")[0] if parsed.netloc else ""
            except:
                pass

        # Lấy IP thực tế của máy edge (không phải localhost)
        edge_ip = self._get_local_ip()
        # Nếu SERVER_HOST là một IP cụ thể (không phải 0.0.0.0), dùng nó
        if hasattr(config, "SERVER_HOST") and config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
            edge_ip = config.SERVER_HOST

        # Edge chỉ có 1 camera với id=1, ip là IP thực tế của máy
        edge_cameras = {
            1: {
                "name": config.CAMERA_NAME,
                "ip": edge_ip,
                "camera_type": config.CAMERA_TYPE
            }
        }

        return {
            "backend_type": "edge",
            "camera": {
                "id": config.CAMERA_ID,
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE,
                "location": config.CAMERA_LOCATION,
                "gate": getattr(config, "GATE", 1),
                "heartbeat_timeout": getattr(config, "CAMERA_HEARTBEAT_TIMEOUT", 30),
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
            # Thêm các section để tương thích với frontend
            "parking": {
                "fee_base": getattr(config, "FEE_BASE", 0.5),
                "fee_per_hour": getattr(config, "FEE_PER_HOUR", 25000),
                "fee_overnight": getattr(config, "FEE_OVERNIGHT", 0),
                "fee_daily_max": getattr(config, "FEE_DAILY_MAX", 0),
                "api_url": getattr(config, "PARKING_API_URL", ""),
            },
            "staff": {
                "api_url": getattr(config, "STAFF_API_URL", ""),
            },
            "subscriptions": {
                "api_url": getattr(config, "SUBSCRIPTION_API_URL", ""),
            },
            "report": {
                "api_url": getattr(config, "REPORT_API_URL", ""),
            },
            "central_server": {
                "ip": central_ip,
            },
            "edge_cameras": edge_cameras,
        }

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Cập nhật config vào file config.py"""
        try:
            # Đọc file hiện tại
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Xử lý edge_cameras nếu có (từ frontend SettingsModal)
            # Edge chỉ có 1 camera với id=1, map edge_cameras[1] về camera section
            if "edge_cameras" in new_config:
                edge_cameras = new_config["edge_cameras"]
                # Edge chỉ có camera id=1
                if "1" in edge_cameras or 1 in edge_cameras:
                    cam_id = "1" if "1" in edge_cameras else 1
                    cam_config = edge_cameras[cam_id]
                    
                    # Map edge_cameras về camera section
                    if "camera" not in new_config:
                        new_config["camera"] = {}
                    
                    # Map name từ edge_cameras
                    if "name" in cam_config:
                        new_config["camera"]["name"] = cam_config["name"]
                    
                    # Map camera_type từ edge_cameras về type
                    if "camera_type" in cam_config:
                        new_config["camera"]["type"] = cam_config["camera_type"]
                    
                    # IP không được thay đổi (edge tự động detect)
                    # Bỏ qua ip trong edge_cameras

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

            # Xử lý các section khác từ frontend
            if "parking" in new_config:
                parking_config = new_config["parking"]
                if "fee_base" in parking_config:
                    content = self._update_value(content, "FEE_BASE", parking_config["fee_base"], is_float=True)
                if "fee_per_hour" in parking_config:
                    content = self._update_value(content, "FEE_PER_HOUR", parking_config["fee_per_hour"])
                if "fee_overnight" in parking_config:
                    content = self._update_value(content, "FEE_OVERNIGHT", parking_config["fee_overnight"])
                if "fee_daily_max" in parking_config:
                    content = self._update_value(content, "FEE_DAILY_MAX", parking_config["fee_daily_max"])
                if "api_url" in parking_config:
                    content = self._update_value(content, "PARKING_API_URL", parking_config["api_url"], is_string=True)

            if "staff" in new_config:
                staff_config = new_config["staff"]
                if "api_url" in staff_config:
                    content = self._update_value(content, "STAFF_API_URL", staff_config["api_url"], is_string=True)

            if "subscriptions" in new_config:
                subscriptions_config = new_config["subscriptions"]
                if "api_url" in subscriptions_config:
                    content = self._update_value(content, "SUBSCRIPTION_API_URL", subscriptions_config["api_url"], is_string=True)

            if "report" in new_config:
                report_config = new_config["report"]
                if "api_url" in report_config:
                    content = self._update_value(content, "REPORT_API_URL", report_config["api_url"], is_string=True)

            if "central_server" in new_config:
                central_server_config = new_config["central_server"]
                if "ip" in central_server_config:
                    # Nếu có IP, cập nhật CENTRAL_SERVER_URL
                    ip = central_server_config["ip"]
                    if ip and ip.strip():
                        # Tạo URL từ IP (giả sử port 8000 cho central)
                        # Nếu IP đã có http:// thì dùng luôn, nếu không thì thêm
                        if ip.startswith("http://") or ip.startswith("https://"):
                            new_url = ip
                        else:
                            new_url = f"http://{ip}:8000"
                        content = self._update_value(content, "CENTRAL_SERVER_URL", new_url, is_string=True)
                    else:
                        # Nếu IP trống, set CENTRAL_SERVER_URL về rỗng
                        content = self._update_value(content, "CENTRAL_SERVER_URL", "", is_string=True)

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

