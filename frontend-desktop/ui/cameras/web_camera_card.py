"""
Web-based Camera Card - Embed web view for best performance
Uses QWebEngineView to display React camera component
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QFont
from core.models import Camera
from utils.logger import logger


class WebCameraCard(QWidget):
    """
    Camera card sử dụng web view để hiển thị camera

    Performance: GIỐNG HỆT WEB BROWSER!
    - Native WebRTC (hardware decode)
    - Canvas rendering (GPU accelerated)
    - 60 FPS smooth

    Tradeoff: Tốn RAM hơn (~100MB/camera) nhưng MƯỢT!
    """

    def __init__(self, camera: Camera, web_url: str):
        """
        Args:
            camera: Camera object
            web_url: URL của web app (e.g., "http://192.168.0.144:3000")
        """
        super().__init__()
        self.camera = camera
        self.web_url = web_url
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === Header: Camera name ===
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                padding: 10px;
            }
        """)
        header_layout = QHBoxLayout(header)

        name_label = QLabel(f"📹 {self.camera.name}")
        name_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        status_label = QLabel(self.camera.status.upper())
        status_label.setStyleSheet("""
            background-color: #27ae60;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_layout.addWidget(status_label)

        layout.addWidget(header)

        # === Web View (camera stream) ===
        self.web_view = QWebEngineView()

        # Enable hardware acceleration và các optimizations
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Build URL để load single camera view
        # Giả sử web app có route: /camera/:id
        camera_url = f"{self.web_url}/camera/{self.camera.id}"

        logger.info(f"Loading web camera view: {camera_url}")
        self.web_view.setUrl(QUrl(camera_url))

        # Set size
        self.web_view.setMinimumSize(QSize(400, 350))

        layout.addWidget(self.web_view)

        # Card styling
        self.setStyleSheet("""
            WebCameraCard {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        self.setFixedWidth(400)

    def update_camera(self, camera: Camera):
        """Update camera data"""
        self.camera = camera
        # Web app tự update qua WebSocket, không cần làm gì

    def closeEvent(self, event):
        """Cleanup when card is closed"""
        # Stop web view
        self.web_view.setUrl(QUrl("about:blank"))
        event.accept()
