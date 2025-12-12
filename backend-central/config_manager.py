"""
Config Manager - Đọc/ghi config từ config.py
"""
import os
import re
import json
from typing import Dict, Any, List


class ConfigManager:
    """Quản lý đọc/ghi config từ file config.py"""

    def __init__(self, config_file="config.py"):
        self.config_file = config_file

    def get_config(self) -> Dict[str, Any]:
        """Đọc config hiện tại"""
        import config
        from urllib.parse import urlparse
        import socket

        # Parse edge cameras de trich xuat IP tu base_url
        edge_cameras = {}
        for cam_id, cam_config in config.EDGE_CAMERAS.items():
            base_url = cam_config.get("base_url", "")

            # Parse IP va port tu base_url
            parsed = urlparse(base_url)
            ip = parsed.hostname or ""

            edge_cameras[cam_id] = {
                "name": cam_config.get("name", ""),
                "ip": ip,
                "camera_type": cam_config.get("camera_type", "ENTRY"),  # ENTRY | EXIT | PARKING_LOT
                "parking_lot_capacity": cam_config.get("parking_lot_capacity", 0)  # Capacity for PARKING_LOT cameras
            }

        # Auto-detect Central IP neu khong co trong config hoac la "auto"
        central_ip = config.CENTRAL_SERVER_IP if hasattr(config, "CENTRAL_SERVER_IP") else ""
        if not central_ip or central_ip in ["auto", "", "127.0.0.1", "localhost"]:
            # Auto-detect local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                central_ip = s.getsockname()[0]
                s.close()
            except Exception:
                central_ip = "127.0.0.1"

        return {
            "backend_type": "central",
            "server": {
                "host": config.SERVER_HOST,
                "port": config.SERVER_PORT
            },
            "database": {
                "db_file": config.DB_FILE
            },
            "camera": {
                "heartbeat_timeout": config.CAMERA_HEARTBEAT_TIMEOUT
            },
            "parking": {
                "fee_base": config.FEE_BASE,
                "fee_per_hour": config.FEE_PER_HOUR,
                "api_url": config.PARKING_API_URL if hasattr(config, "PARKING_API_URL") else ""
            },
            "staff": {
                "api_url": config.STAFF_API_URL if hasattr(config, "STAFF_API_URL") else ""
            },
            "subscriptions": {
                "api_url": config.SUBSCRIPTION_API_URL if hasattr(config, "SUBSCRIPTION_API_URL") else ""
            },
            "report": {
                "api_url": config.REPORT_API_URL if hasattr(config, "REPORT_API_URL") else ""
            },
            "central_server": {
                "ip": central_ip  # Auto-detected IP
            },
            "central_sync": {
                "servers": self._parse_sync_servers(config.CENTRAL_SYNC_SERVERS if hasattr(config, "CENTRAL_SYNC_SERVERS") else "[]")
            },
            "edge_cameras": edge_cameras
        }

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Cập nhật config vào file config.py"""
        try:
            # Doc file hien tai
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update tung section
            if "server" in new_config:
                content = self._update_value(content, "SERVER_HOST", new_config["server"]["host"], is_string=True)
                content = self._update_value(content, "SERVER_PORT", new_config["server"]["port"])

            if "camera" in new_config:
                content = self._update_value(content, "CAMERA_HEARTBEAT_TIMEOUT", new_config["camera"]["heartbeat_timeout"])

            if "parking" in new_config:
                parking_config = new_config["parking"]
                if "fee_base" in parking_config:
                    content = self._update_value(content, "FEE_BASE", parking_config["fee_base"])
                if "fee_per_hour" in parking_config:
                    content = self._update_value(content, "FEE_PER_HOUR", parking_config["fee_per_hour"])
                if "api_url" in parking_config:
                    content = self._update_value(content, "PARKING_API_URL", parking_config["api_url"], is_string=True)

            if "staff" in new_config:
                staff_api_url = new_config["staff"].get("api_url", "")
                content = self._update_value(content, "STAFF_API_URL", staff_api_url, is_string=True)

            if "subscriptions" in new_config:
                subscription_api_url = new_config["subscriptions"].get("api_url", "")
                content = self._update_value(content, "SUBSCRIPTION_API_URL", subscription_api_url, is_string=True)

            if "report" in new_config:
                report_api_url = new_config["report"].get("api_url", "")
                content = self._update_value(content, "REPORT_API_URL", report_api_url, is_string=True)

            if "central_server" in new_config:
                central_ip = new_config["central_server"].get("ip", "")
                content = self._update_value(content, "CENTRAL_SERVER_IP", central_ip, is_string=True)

            if "central_sync" in new_config:
                servers = new_config["central_sync"].get("servers", [])
                servers_json = json.dumps(servers, ensure_ascii=False)
                # Escape quotes va backslashes trong JSON string cho Python string
                servers_json_escaped = servers_json.replace('\\', '\\\\').replace('"', '\\"')
                # Update voi JSON string trong os.getenv, match ca dong co the co comment
                pattern = rf'^CENTRAL_SYNC_SERVERS\s*=\s*os\.getenv\([^)]+\)'
                replacement = f'CENTRAL_SYNC_SERVERS = os.getenv("CENTRAL_SYNC_SERVERS", "{servers_json_escaped}")'
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            if "edge_cameras" in new_config:
                content = self._update_edge_cameras(content, new_config["edge_cameras"])

            # Ghi lai file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Reload config module
            import importlib
            import config
            importlib.reload(config)

            return True
        except Exception as e:
            print(f"Error updating config: {e}")
            return False

    def _update_value(self, content: str, key: str, value: Any, is_string: bool = False) -> str:
        """Update giá trị trong content"""
        if is_string:
            pattern = rf'^{key}\s*=\s*"[^"]*"'
            replacement = f'{key} = "{value}"'
        else:
            # Ho tro ca so nguyen lan so thuc (vd: 0.5)
            pattern = rf'^{key}\s*=\s*[-+]?\d*\.?\d+'
            replacement = f'{key} = {value}'

        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        return content

    def _parse_sync_servers(self, servers_str: str) -> List[str]:
        """Parse CENTRAL_SYNC_SERVERS từ JSON string thành list"""
        try:
            if isinstance(servers_str, list):
                return servers_str
            if not servers_str or servers_str.strip() == "":
                return []
            # Parse JSON string
            parsed = json.loads(servers_str)
            if isinstance(parsed, list):
                return parsed
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def _update_edge_cameras(self, content: str, cameras: Dict[int, Dict[str, Any]]) -> str:
        """Update EDGE_CAMERAS dictionary"""
        # Tim vi tri EDGE_CAMERAS
        start_pattern = r'EDGE_CAMERAS\s*=\s*\{'
        end_pattern = r'^\}'

        match_start = re.search(start_pattern, content, re.MULTILINE)
        if not match_start:
            return content

        # Tim dau } dong cua dictionary
        start_pos = match_start.end()
        brace_count = 1
        end_pos = start_pos

        for i, char in enumerate(content[start_pos:], start=start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i
                    break

        # Generate new EDGE_CAMERAS content
        new_cameras_content = self._generate_edge_cameras_dict(cameras)

        # Replace
        new_content = content[:match_start.start()] + new_cameras_content + content[end_pos+1:]
        return new_content

    def _generate_edge_cameras_dict(self, cameras: Dict[int, Dict[str, Any]]) -> str:
        """Generate Python dict string cho EDGE_CAMERAS"""
        lines = ["EDGE_CAMERAS = {"]

        for cam_id, cam_config in cameras.items():
            name = cam_config.get("name", "")
            ip = cam_config.get("ip", "")
            camera_type = cam_config.get("camera_type", "ENTRY")
            port = 5000  # Fixed port

            # Auto-generate URLs from IP
            base_url = f"http://{ip}:{port}" if ip else ""
            ws_url = f"ws://{ip}:{port}/ws/detections" if ip else ""

            lines.append(f"    {cam_id}: {{")
            lines.append(f'        "name": "{name}",')
            lines.append(f'        "camera_type": "{camera_type}",')
            lines.append(f'        "base_url": os.getenv("EDGE{cam_id}_URL", "{base_url}"),')
            lines.append(f'        "ws_url": os.getenv(')
            lines.append(f'            "EDGE{cam_id}_WS_URL", "{ws_url}"')
            lines.append(f'        ),')
            lines.append(f'        "default_mode": os.getenv("EDGE{cam_id}_DEFAULT_MODE", "annotated"),')
            lines.append(f'        "supports_annotated": True,')
            lines.append(f'        "info_path": "/api/camera/info",')
            lines.append(f"    }},")

        lines.append("}")
        return "\n".join(lines)