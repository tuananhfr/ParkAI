"""
Cameras Widget - Grid hiển thị cameras
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PyQt6.QtCore import Qt
from .camera_card import CameraCard
from .flow_layout import FlowLayout
from core.models import Camera
from typing import List
from utils.logger import logger


class CamerasWidget(QWidget):
    """
    Cameras grid với scroll

    Usage:
        widget = CamerasWidget(api_client)
        widget.update_cameras(cameras_list)
    """

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.camera_cards = {}  # {camera_id: CameraCard}
        self.setup_ui()
        logger.info("Cameras widget initialized")

    def setup_ui(self):
        """Setup UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("📹 Camera Monitoring")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        main_layout.addWidget(title)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        # Container for camera cards
        self.container = QWidget()
        self.flow_layout = FlowLayout(self.container, margin=20, spacing=20)

        scroll.setWidget(self.container)
        main_layout.addWidget(scroll)

    def update_cameras(self, cameras: List[Camera]):
        """
        Update cameras display

        Args:
            cameras: List of Camera objects
        """
        logger.info(f"Updating cameras widget with {len(cameras)} cameras")

        # Update existing cards hoặc tạo mới
        for camera in cameras:
            logger.debug(f"Camera {camera.id}: {camera.name} - Status: {camera.status} - Plate: {camera.current_plate}")

            if camera.id in self.camera_cards:
                # Update existing card
                self.camera_cards[camera.id].update_camera(camera)
            else:
                # Create new card
                card = CameraCard(camera, self.api_client)
                self.camera_cards[camera.id] = card
                self.flow_layout.addWidget(card)

        # Remove cards của cameras không còn tồn tại
        camera_ids = {cam.id for cam in cameras}
        for cam_id in list(self.camera_cards.keys()):
            if cam_id not in camera_ids:
                card = self.camera_cards.pop(cam_id)
                self.flow_layout.removeWidget(card)
                card.deleteLater()

        logger.info(f"Cameras updated: {len(cameras)} cameras, {len(self.camera_cards)} cards displayed")

    def clear_cameras(self):
        """Clear all camera cards"""
        for card in self.camera_cards.values():
            self.flow_layout.removeWidget(card)
            card.deleteLater()
        self.camera_cards.clear()
