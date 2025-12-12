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
            # Ket noi den mot dia chi ben ngoai de biet IP cua interface mang chinh
            # Khong thuc su gui du lieu, chi de biet IP cua may
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # Ket noi den mot dia chi khong can phai co (chi de lay IP local)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                # Fallback: lay IP tu hostname
                ip = socket.gethostbyname(socket.gethostname())
            finally:
                s.close()
            
            # Neu van la localhost, thu cach khac
            if ip in ['127.0.0.1', 'localhost', '::1']:
                # Lay IP tu tat ca interfaces
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
            
            self._cached_ip = ip
            return ip
        except Exception as e:
            # Neu khong lay duoc, tra ve IP mac dinh hoac tu config
            print(f"Warning: Could not detect local IP: {e}")
            return "127.0.0.1"

    def get_config(self) -> Dict[str, Any]:
        """Đọc config hiện tại"""
        import config
        from urllib.parse import urlparse

        # Parse central server URL de lay IP
        central_ip = ""
        if hasattr(config, "CENTRAL_SERVER_URL") and config.CENTRAL_SERVER_URL:
            try:
                parsed = urlparse(config.CENTRAL_SERVER_URL)
                central_ip = parsed.netloc.split(":")[0] if parsed.netloc else ""
            except:
                pass

        # Lay IP thuc te cua may edge (khong phai localhost)
        edge_ip = self._get_local_ip()
        # Neu SERVER_HOST la mot IP cu the (khong phai 0.0.0.0), dung no
        if hasattr(config, "SERVER_HOST") and config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
            edge_ip = config.SERVER_HOST

        # Edge chi co 1 camera voi id=1, ip la IP thuc te cua may
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
            "central": {
                "server_url": config.CENTRAL_SERVER_URL,
                "sync_enabled": config.CENTRAL_SYNC_ENABLED,
            },
            # Them cac section de tuong thich voi frontend
            "parking": {
                "fee_base": getattr(config, "FEE_BASE", 0.5),
                "fee_per_hour": getattr(config, "FEE_PER_HOUR", 25000),
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
            "barrier": {
                "enabled": getattr(config, "BARRIER_ENABLED", False),
                "gpio_pin": getattr(config, "BARRIER_GPIO_PIN", 18),
                "auto_close_time": getattr(config, "BARRIER_AUTO_CLOSE_TIME", 5.0),
            },
            "parking_lot": {
                "capacity": getattr(config, "PARKING_LOT_CAPACITY", 0),
            },
            "edge_cameras": edge_cameras,
        }

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Cập nhật config vào file config.py"""
        try:
            # Doc file hien tai - thu nhieu encoding
            content = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(self.config_file, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise Exception("Cannot read config file with any known encoding")

            # Xu ly edge_cameras neu co (tu frontend SettingsModal)
            # Edge chi co 1 camera voi id=1, map edge_cameras[1] ve camera section
            if "edge_cameras" in new_config:
                edge_cameras = new_config["edge_cameras"]
                # Edge chi co camera id=1
                if "1" in edge_cameras or 1 in edge_cameras:
                    cam_id = "1" if "1" in edge_cameras else 1
                    cam_config = edge_cameras[cam_id]
                    
                    # Map edge_cameras ve camera section
                    if "camera" not in new_config:
                        new_config["camera"] = {}
                    
                    # Map name tu edge_cameras
                    if "name" in cam_config:
                        new_config["camera"]["name"] = cam_config["name"]
                    
                    # Map camera_type tu edge_cameras ve type
                    if "camera_type" in cam_config:
                        new_config["camera"]["type"] = cam_config["camera_type"]
                    
                    # IP khong duoc thay doi (edge tu dong detect)
                    # Bo qua ip trong edge_cameras

            # Update tung section
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

            if "central" in new_config:
                central_config = new_config["central"]
                if "server_url" in central_config:
                    content = self._update_value(content, "CENTRAL_SERVER_URL", central_config["server_url"], is_string=True)
                if "sync_enabled" in central_config:
                    content = self._update_value(content, "CENTRAL_SYNC_ENABLED", central_config["sync_enabled"], is_bool=True)

            # Xu ly cac section khac tu frontend
            if "parking" in new_config:
                parking_config = new_config["parking"]
                if "fee_base" in parking_config:
                    content = self._update_value(content, "FEE_BASE", parking_config["fee_base"], is_float=True)
                if "fee_per_hour" in parking_config:
                    content = self._update_value(content, "FEE_PER_HOUR", parking_config["fee_per_hour"])
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
                    # Neu co IP, cap nhat CENTRAL_SERVER_URL
                    ip = central_server_config["ip"]
                    if ip and ip.strip():
                        # Tao URL tu IP (gia su port 8000 cho central)
                        # Neu IP da co http:// thi dung luon, neu khong thi them
                        if ip.startswith("http://") or ip.startswith("https://"):
                            new_url = ip
                        else:
                            new_url = f"http://{ip}:8000"
                        content = self._update_value(content, "CENTRAL_SERVER_URL", new_url, is_string=True)
                    else:
                        # Neu IP trong, set CENTRAL_SERVER_URL ve rong
                        content = self._update_value(content, "CENTRAL_SERVER_URL", "", is_string=True)

            if "barrier" in new_config:
                barrier_config = new_config["barrier"]
                if "enabled" in barrier_config:
                    content = self._update_value(content, "BARRIER_ENABLED", barrier_config["enabled"], is_bool=True)
                if "gpio_pin" in barrier_config:
                    content = self._update_value(content, "BARRIER_GPIO_PIN", barrier_config["gpio_pin"])
                if "auto_close_time" in barrier_config:
                    content = self._update_value(content, "BARRIER_AUTO_CLOSE_TIME", barrier_config["auto_close_time"], is_float=True)

            if "parking_lot" in new_config:
                parking_lot_config = new_config["parking_lot"]
                if "capacity" in parking_lot_config:
                    content = self._update_value(content, "PARKING_LOT_CAPACITY", parking_lot_config["capacity"])

            # Ghi lai file - ensure UTF-8
            with open(self.config_file, 'w', encoding='utf-8', errors='replace') as f:
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
        # Pattern de tim dong co key = value (co the co comment sau do)
        # Vi du: CAMERA_TYPE = "ENTRY" # comment
        # Match: key = value (giu lai comment sau #)
        pattern = rf'^(\s*){key}\s*=\s*[^\n#]*(#.*)?$'
        
        def replace_func(match):
            indent = match.group(1)  # Giu lai indentation
            comment = match.group(2) if match.group(2) else ""  # Giữ lại comment nếu có
            
            if is_string:
                new_line = f'{indent}{key} = "{value}"'
            elif is_bool:
                new_line = f'{indent}{key} = {str(value)}'
            elif is_float:
                new_line = f'{indent}{key} = {float(value)}'
            else:
                new_line = f'{indent}{key} = {value}'
            
            # Them lai comment neu co
            if comment:
                new_line += f"  {comment}"
            
            return new_line
        
        # Tim xem co match khong
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            print(f"Warning: Key {key} not found in config file")
            return content
        
        # Replace gia tri
        new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
        return new_content

