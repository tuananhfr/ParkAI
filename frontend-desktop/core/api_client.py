"""
REST API Client để giao tiếp với backend (Central hoặc Edge)
"""
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from .models import ConnectionStatus, Stats, Camera
from utils.logger import logger
from config import config


class APIClient:
    """
    REST API Client với error handling và timeout

    Usage:
        client = APIClient(base_url="http://192.168.0.144:8000")
        status = client.check_connection()
        stats = client.get_stats()
    """

    def __init__(self, base_url: str = None):
        """
        Initialize API client

        Args:
            base_url: Backend URL (mặc định từ config)
        """
        self.base_url = base_url or config.CENTRAL_URL
        self.timeout = 5  # 5 giây timeout
        self.session = requests.Session()  # Reuse connection
        logger.info(f"API Client initialized: {self.base_url}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generic request method với error handling

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/api/stats")
            params: Query parameters
            json: JSON body

        Returns:
            Response JSON dict hoặc None nếu lỗi
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.timeout
            )

            # Raise exception nếu status code 4xx, 5xx
            response.raise_for_status()

            # Parse JSON
            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {url}")
            return None
        except requests.exceptions.HTTPError as e:
            # Log chi tiết nội dung trả về từ backend để dễ debug (ví dụ WebRTC offer lỗi)
            status = e.response.status_code if e.response is not None else "unknown"
            body_text = None
            try:
                body_text = e.response.text if e.response is not None else None
            except Exception:
                body_text = None

            if body_text:
                logger.error(f"HTTP error {status}: {url} - body: {body_text}")
            else:
                logger.error(f"HTTP error {status}: {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    # ===== Connection =====

    def check_connection(self) -> ConnectionStatus:
        """
        Check backend connection status

        Returns:
            ConnectionStatus object
        """
        data = self._request("GET", "/api/status")

        if data:
            return ConnectionStatus(
                connected=True,
                backend_type=data.get("backend_type"),
                last_check=datetime.now(),
                error=None
            )
        else:
            return ConnectionStatus(
                connected=False,
                backend_type=None,
                last_check=datetime.now(),
                error="Cannot connect to backend"
            )

    # ===== Stats =====

    def get_stats(self) -> Optional[Stats]:
        """
        Get dashboard stats

        Returns:
            Stats object hoặc None nếu lỗi
        """
        data = self._request("GET", "/api/stats")

        if data and data.get("success"):
            return Stats(
                entries_today=data.get("entries_today", 0),
                exits_today=data.get("exits_today", 0),
                vehicles_in_parking=data.get("vehicles_in_parking", 0),
                revenue_today=data.get("revenue_today", 0.0)
            )
        return None

    # ===== Cameras =====

    def get_cameras(self) -> List[Camera]:
        """
        Get list of cameras

        Returns:
            List of Camera objects
        """
        data = self._request("GET", "/api/cameras")

        if data and data.get("success"):
            cameras = []
            logger.info(f"Received {len(data.get('cameras', []))} cameras from API")
            for cam_data in data.get("cameras", []):
                try:
                    camera = Camera(
                        id=cam_data.get("id", 0),
                        name=cam_data.get("name", "Unknown Camera"),
                        location=cam_data.get("location", "Unknown"),
                        stream_url=cam_data.get("stream_url"),
                        status=cam_data.get("status", "offline"),
                        current_plate=cam_data.get("current_plate"),
                        vehicle_type=cam_data.get("vehicle_type"),
                        entry_time=cam_data.get("entry_time")
                    )
                    logger.debug(f"Parsed camera: {camera.name} (ID: {camera.id}) - Status: {camera.status}, Plate: {camera.current_plate}, Stream URL: {camera.stream_url}")
                    cameras.append(camera)
                except Exception as e:
                    logger.error(f"Error parsing camera data: {e}, data: {cam_data}")
                    continue
            logger.info(f"Successfully parsed {len(cameras)} cameras")
            return cameras
        logger.warning("No camera data received from API")
        return []

    # ===== Config =====

    def get_config(self) -> Optional[Dict]:
        """Get backend configuration"""
        data = self._request("GET", "/api/config")
        if data and data.get("success"):
            return data.get("config", {})
        return None

    def update_config(self, config_data: Dict) -> bool:
        """
        Update backend configuration

        Args:
            config_data: Configuration dict

        Returns:
            True nếu thành công
        """
        # Backend central sử dụng POST /api/config (giống web frontend)
        data = self._request("POST", "/api/config", json=config_data)
        return data is not None and data.get("success", False)

    # ===== History =====

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        today_only: bool = False,
        status: Optional[str] = None,
        in_parking_only: bool = False,
        entries_only: bool = False,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get history entries

        Args:
            limit: Number of records
            offset: Offset for pagination
            today_only: Only today's records
            status: Filter by status (IN | OUT)
            in_parking_only: Only vehicles currently IN parking
            entries_only: Only entry events
            search: Search by plate_id / plate_view

        Returns:
            List of history entries
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if today_only:
            params["today_only"] = True
        if status:
            params["status"] = status
        if in_parking_only:
            params["in_parking_only"] = True
        if entries_only:
            params["entries_only"] = True
        if search:
            params["search"] = search

        data = self._request("GET", "/api/parking/history", params=params)
        # API (central và edge-mini-central) trả về:
        # { success: true, history: [...], stats: {...} }
        if data and data.get("success"):
            return data.get("history", []) or []
        return []

    def get_history_changes(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get history changes (UPDATE/DELETE records), giống HistoryPanel web.

        Returns:
            List of change records
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        data = self._request("GET", "/api/parking/history/changes", params=params)
        if data and data.get("success"):
            return data.get("changes", []) or []
        return []

    def update_history_entry(self, history_id: int, plate_id: str, plate_view: str) -> bool:
        """
        Update plate info for a history entry.

        Args:
            history_id: History entry ID
            plate_id: Normalized plate (no dash/space)
            plate_view: Display plate
        """
        payload = {
            "plate_id": plate_id,
            "plate_view": plate_view
        }
        data = self._request(
            "PUT",
            f"/api/parking/history/{history_id}",
            json=payload
        )
        return data is not None and data.get("success", False)

    def delete_history_entry(self, history_id: int) -> bool:
        """Delete a history entry."""
        data = self._request(
            "DELETE",
            f"/api/parking/history/{history_id}"
        )
        return data is not None and data.get("success", False)

    # ===== Staff =====

    def get_staff(self) -> List[Dict]:
        """Get staff list"""
        data = self._request("GET", "/api/staff")
        if data and data.get("success"):
            return data.get("staff", [])
        return []

    def update_staff(self, staff_data: List[Dict]) -> bool:
        """Update staff list"""
        data = self._request("POST", "/api/staff", json={"staff": staff_data})
        return data is not None and data.get("success", False)

    # ===== Subscriptions =====

    def get_subscriptions(self) -> List[Dict]:
        """Get subscriptions list (read-only, giống web SubscriptionList)"""
        data = self._request("GET", "/api/subscriptions")
        if data and data.get("success"):
            return data.get("subscriptions", [])
        return []

    # ===== Barrier Control =====

    def open_barrier(self, camera_id: int, plate: str) -> bool:
        """
        Open barrier for camera

        Args:
            camera_id: Camera ID
            plate: Vehicle plate

        Returns:
            True nếu thành công
        """
        data = self._request(
            "POST",
            f"/api/cameras/{camera_id}/barrier/open",
            json={"plate": plate}
        )
        return data is not None and data.get("success", False)

    def close_barrier(self, camera_id: int) -> bool:
        """Close barrier"""
        data = self._request(
            "POST",
            f"/api/cameras/{camera_id}/barrier/close"
        )
        return data is not None and data.get("success", False)
