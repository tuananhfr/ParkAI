"""
Application configuration
"""
import os
from dotenv import load_dotenv

# Load .env file nếu có
load_dotenv()


class Config:
    """Application configuration"""

    # Window settings
    WINDOW_TITLE = "ParkAI Desktop"
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900
    WINDOW_MIN_WIDTH = 1200
    WINDOW_MIN_HEIGHT = 700

    # Backend connection
    CENTRAL_URL = os.getenv("CENTRAL_URL", "http://192.168.0.144:8000")

    # WebSocket URLs (auto-generated từ CENTRAL_URL)
    @property
    def WS_CAMERAS_URL(self):
        return self.CENTRAL_URL.replace("http", "ws") + "/ws/cameras"

    @property
    def WS_STATS_URL(self):
        return self.CENTRAL_URL.replace("http", "ws") + "/ws/history"

    # Polling intervals (milliseconds)
    STATUS_CHECK_INTERVAL = 5000  # 5 giây check backend status
    STATS_REFRESH_INTERVAL = 10000  # 10 giây refresh stats (fallback)

    # Styling
    ACCENT_COLOR = "#0d6efd"  # Bootstrap primary blue
    SUCCESS_COLOR = "#198754"
    WARNING_COLOR = "#ffc107"
    DANGER_COLOR = "#dc3545"


# Global config instance
config = Config()
