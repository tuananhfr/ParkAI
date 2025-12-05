"""
Camera Card - Hiển thị 1 camera với video, info, controls
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPixmap
from core.models import Camera
from utils.logger import logger
from .mjpeg_worker import MJPEGWorker


class CameraCard(QWidget):
    """
    Card cho 1 camera:
    - Video stream preview
    - Camera info (name, location, status)
    - Vehicle info (plate, type, entry time)
    - Barrier controls (Open/Close)
    """

    def __init__(self, camera: Camera, api_client):
        super().__init__()
        self.camera = camera
        self.api_client = api_client
        self.video_worker = None
        self.setup_ui()
        self.start_video_stream()

    def setup_ui(self):
        """Setup UI"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # === Header: Camera name + status ===
        header_layout = QHBoxLayout()

        name_label = QLabel(f"📹 {self.camera.name}")
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        self.status_label = QLabel(self.camera.status.upper())
        self.update_status_style()
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # === Video preview ===
        self.video_label = QLabel()
        self.video_label.setFixedSize(QSize(320, 240))
        self.video_label.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Placeholder text (will be replaced by video stream)
        self.video_label.setText("📹 Loading...")
        self.video_label.setStyleSheet("""
            background-color: #222;
            border: 1px solid #444;
            color: #888;
            font-size: 14px;
        """)

        layout.addWidget(self.video_label)

        # === Location ===
        location_label = QLabel(f"📍 {self.camera.location}")
        location_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(location_label)

        # === Vehicle info ===
        self.vehicle_frame = QFrame()
        self.vehicle_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        vehicle_layout = QVBoxLayout(self.vehicle_frame)
        vehicle_layout.setContentsMargins(10, 10, 10, 10)
        vehicle_layout.setSpacing(5)

        self.plate_label = QLabel("Plate: -")
        self.type_label = QLabel("Type: -")
        self.entry_time_label = QLabel("Entry: -")

        for label in [self.plate_label, self.type_label, self.entry_time_label]:
            label.setStyleSheet("font-size: 11px;")
            vehicle_layout.addWidget(label)

        layout.addWidget(self.vehicle_frame)

        # === Barrier controls ===
        controls_layout = QHBoxLayout()

        self.open_btn = QPushButton("🚧 Open")
        self.open_btn.clicked.connect(self.on_open_barrier)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #157347;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)

        self.close_btn = QPushButton("⛔ Close")
        self.close_btn.clicked.connect(self.on_close_barrier)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #bb2d3b;
            }
        """)

        controls_layout.addWidget(self.open_btn)
        controls_layout.addWidget(self.close_btn)

        layout.addLayout(controls_layout)

        # Update vehicle info (after buttons are created)
        self.update_vehicle_info()

        # Card border
        self.setStyleSheet("""
            CameraCard {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        self.setFixedWidth(350)

    def update_status_style(self):
        """Update status label style"""
        if self.camera.status == "online":
            self.status_label.setStyleSheet("""
                background-color: #198754;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:
            self.status_label.setStyleSheet("""
                background-color: #6c757d;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)

    def update_vehicle_info(self):
        """Update vehicle info display"""
        if self.camera.current_plate:
            self.plate_label.setText(f"Plate: {self.camera.current_plate}")
            self.type_label.setText(f"Type: {self.camera.vehicle_type or '-'}")
            self.entry_time_label.setText(f"Entry: {self.camera.entry_time or '-'}")
            self.vehicle_frame.setVisible(True)
            self.open_btn.setEnabled(True)
        else:
            self.plate_label.setText("Plate: -")
            self.type_label.setText("Type: -")
            self.entry_time_label.setText("Entry: -")
            self.vehicle_frame.setVisible(False)
            self.open_btn.setEnabled(False)

    def update_camera(self, camera: Camera):
        """Update camera data"""
        logger.debug(f"Updating camera card {camera.id}: status={camera.status}, plate={camera.current_plate}")
        self.camera = camera
        self.status_label.setText(camera.status.upper())
        self.update_status_style()
        self.update_vehicle_info()

    def on_open_barrier(self):
        """Handle open barrier"""
        if not self.camera.current_plate:
            logger.warning("No vehicle detected")
            return

        logger.info(f"Opening barrier for camera {self.camera.id}, plate: {self.camera.current_plate}")

        # Call API
        success = self.api_client.open_barrier(
            self.camera.id,
            self.camera.current_plate
        )

        if success:
            self.status_label.setText("OPENING...")
            logger.info("Barrier opened successfully")
        else:
            logger.error("Failed to open barrier")

    def on_close_barrier(self):
        """Handle close barrier"""
        logger.info(f"Closing barrier for camera {self.camera.id}")

        success = self.api_client.close_barrier(self.camera.id)

        if success:
            logger.info("Barrier closed successfully")
        else:
            logger.error("Failed to close barrier")

    # ===== Video Stream =====

    def start_video_stream(self):
        """Start MJPEG video stream"""
        logger.info(f"Starting MJPEG stream for camera {self.camera.id}")

        # Stop existing worker if any
        self.stop_video_stream()

        # Build MJPEG stream URL
        # Sử dụng base_url từ api_client
        base_url = self.api_client.base_url.rstrip('/')
        stream_url = f"{base_url}/api/stream/annotated?camera_id={self.camera.id}"

        # Create and start MJPEG worker
        self.video_worker = MJPEGWorker(
            stream_url=stream_url,
            camera_id=self.camera.id
        )
        self.video_worker.frame_ready.connect(self.on_frame_ready)
        self.video_worker.error.connect(self.on_stream_error)
        self.video_worker.connected.connect(self.on_stream_connected)
        self.video_worker.disconnected.connect(self.on_stream_disconnected)
        self.video_worker.start()

    def stop_video_stream(self):
        """Stop video stream worker"""
        if self.video_worker:
            self.video_worker.stop()
            self.video_worker = None

    def on_frame_ready(self, pixmap: QPixmap):
        """Handle new video frame"""
        self.video_label.setPixmap(pixmap)

    def on_stream_error(self, error_msg: str):
        """Handle stream error"""
        logger.error(f"Stream error for camera {self.camera.id}: {error_msg}")
        self.video_label.setText(f"📹 Error\n{error_msg}")

    def on_stream_connected(self):
        """Handle MJPEG stream connected"""
        logger.info(f"MJPEG stream connected for camera {self.camera.id}")

    def on_stream_disconnected(self):
        """Handle MJPEG stream disconnected"""
        logger.warning(f"MJPEG stream disconnected for camera {self.camera.id}")
        self.video_label.setText("📹 Disconnected")

    def closeEvent(self, event):
        """Cleanup when card is closed"""
        self.stop_video_stream()
        event.accept()
