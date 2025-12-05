from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel,
    QTabWidget, QStatusBar, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from config import config
from utils.logger import logger
from core.api_client import APIClient
from core.connection_service import ConnectionService
from core.models import ConnectionStatus, Camera
from core.websocket_manager import WebSocketWorker
from ui.dashboard.dashboard_widget import DashboardWidget
from ui.cameras.cameras_widget import CamerasWidget
from ui.history.history_widget import HistoryWidget
from ui.settings.settings_widget import SettingsWidget


class MainWindow(QMainWindow):
    """
    Main application window

    Layout:
    - Menu bar (File, View, Help)
    - Tab widget (Dashboard, Cameras, History, Settings)
    - Status bar (Connection status, info)
    """

    def __init__(self):
        super().__init__()

        # API Client
        self.api_client = APIClient()

        # Connection Service
        self.connection_service = ConnectionService(self.api_client)
        self.connection_service.connection_changed.connect(self.on_connection_changed)
        self.connection_service.status_updated.connect(self.on_status_updated)

        self.setup_ui()

        # Start connection service
        self.connection_service.start()

        # Stats WebSocket
        self.setup_stats_websocket()

        # Cameras WebSocket
        self.setup_cameras_websocket()

        # History WebSocket
        self.setup_history_websocket()

        # Fetch data lần đầu
        self.fetch_stats()
        self.fetch_cameras()
        self.fetch_history()

        logger.info("Main window initialized")

    def setup_ui(self):
        """Setup UI components"""
        # Window properties
        self.setWindowTitle(config.WINDOW_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)

        # Create menu bar
        self.create_menu_bar()

        # Create central widget with tabs
        self.create_tabs()

        # Create status bar
        self.create_status_bar()

        logger.info(f"UI setup complete - {config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")

    def create_menu_bar(self):
        """Create menu bar với File, View, Help menus"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # File > Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        # View > Refresh
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.setStatusTip("Refresh all data")
        refresh_action.triggered.connect(self.refresh_all)
        view_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # Help > About
        about_action = QAction("&About", self)
        about_action.setStatusTip("About ParkAI Desktop")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tabs(self):
        """Create tab widget với 4 tabs"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs)

        # Create tabs
        self.create_dashboard_tab()
        self.create_cameras_tab()
        self.create_history_tab()
        self.create_settings_tab()

    def create_dashboard_tab(self):
        """Dashboard tab"""
        self.dashboard_widget = DashboardWidget()
        self.tabs.addTab(self.dashboard_widget, "Dashboard")

    def create_cameras_tab(self):
        """Cameras tab"""
        self.cameras_widget = CamerasWidget(self.api_client)
        self.tabs.addTab(self.cameras_widget, "Cameras")

    def create_history_tab(self):
        """History tab"""
        self.history_widget = HistoryWidget(self.api_client)
        self.tabs.addTab(self.history_widget, "History")

    def create_settings_tab(self):
        """Settings tab"""
        self.settings_widget = SettingsWidget(self.api_client)
        self.settings_widget.settings_changed.connect(self.on_settings_changed)
        self.tabs.addTab(self.settings_widget, "Settings")
        # Load config từ backend khi tạo tab Settings (giống web mở modal)
        self.settings_widget.load_config()

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Left: Connection status
        self.connection_label = QLabel("⚫ Disconnected")
        self.connection_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.status_bar.addWidget(self.connection_label)

        # Right: Info message
        self.status_bar.showMessage("Ready")

    def update_connection_status(self, connected: bool):
        """Update connection status indicator"""
        if connected:
            self.connection_label.setText("🟢 Connected")
            self.connection_label.setStyleSheet("color: #198754; font-weight: bold;")
            self.status_bar.showMessage("Connected to backend")
        else:
            self.connection_label.setText("⚫ Disconnected")
            self.connection_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.status_bar.showMessage("Backend disconnected")

    # ===== WebSocket Setup =====

    def setup_stats_websocket(self):
        """Setup WebSocket cho stats updates"""
        ws_url = config.CENTRAL_URL.replace("http", "ws") + "/ws/history"

        self.stats_ws = WebSocketWorker(ws_url)
        self.stats_ws.message_received.connect(self.on_stats_message)
        self.stats_ws.connected.connect(lambda: logger.info("Stats WebSocket connected"))
        self.stats_ws.disconnected.connect(lambda: logger.warning("Stats WebSocket disconnected"))
        self.stats_ws.start()

    def on_stats_message(self, data: dict):
        """Handle stats WebSocket message"""
        if data.get("type") == "history_update":
            # Khi có history update, fetch stats và history mới
            self.fetch_stats()
            self.fetch_history()

    def fetch_stats(self):
        """Fetch stats từ API và update dashboard"""
        stats = self.api_client.get_stats()
        if stats:
            self.dashboard_widget.update_stats(stats)

    def setup_cameras_websocket(self):
        """Setup WebSocket cho cameras updates"""
        ws_url = config.CENTRAL_URL.replace("http", "ws") + "/ws/cameras"

        self.cameras_ws = WebSocketWorker(ws_url)
        self.cameras_ws.message_received.connect(self.on_cameras_message)
        self.cameras_ws.connected.connect(lambda: logger.info("Cameras WebSocket connected"))
        self.cameras_ws.disconnected.connect(lambda: logger.warning("Cameras WebSocket disconnected"))
        self.cameras_ws.start()

    def on_cameras_message(self, data: dict):
        """Handle cameras WebSocket message"""
        if data.get("type") == "cameras_update":
            cameras_data = data.get("data", {}).get("cameras", [])
            cameras = []
            for cam_data in cameras_data:
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
                    cameras.append(camera)
                except Exception as e:
                    logger.error(f"Error parsing camera data from WebSocket: {e}")
                    continue
            self.cameras_widget.update_cameras(cameras)

    def fetch_cameras(self):
        """Fetch cameras từ API"""
        cameras = self.api_client.get_cameras()
        self.cameras_widget.update_cameras(cameras)

    def setup_history_websocket(self):
        """Setup WebSocket cho history updates (reuse stats WebSocket)"""
        # Stats WebSocket already handles history_update events
        pass

    def fetch_history(self):
        """Fetch history từ API"""
        logger.info("Fetching history data")
        self.history_widget.refresh_data()

    # ===== Connection handlers =====

    def on_connection_changed(self, connected: bool):
        """Handle connection status change"""
        logger.info(f"Connection changed: {connected}")
        self.update_connection_status(connected)

        if connected:
            # Khi kết nối lại, refresh data
            self.refresh_all()

    def on_status_updated(self, status: ConnectionStatus):
        """Handle full status update"""
        # Update status bar message
        if status.connected:
            backend_type = status.backend_type or "unknown"
            self.status_bar.showMessage(f"Connected to {backend_type} backend")
        else:
            error_msg = status.error or "Disconnected"
            self.status_bar.showMessage(error_msg)

    # ===== Menu actions =====

    def refresh_all(self):
        """Refresh all data (F5)"""
        logger.info("Refresh all triggered")
        self.status_bar.showMessage("Refreshing...", 2000)
        self.fetch_stats()
        self.fetch_cameras()
        self.fetch_history()

    def on_settings_changed(self, config: dict):
        """Handle settings change"""
        logger.info(f"Settings changed: {config}")
        # Khi config thay đổi (đặc biệt danh sách cameras / parking),
        # refresh lại cameras & stats giống web gọi onSaveSuccess
        try:
            self.fetch_cameras()
            self.fetch_stats()
        except Exception as e:
            logger.error(f"Error applying new settings: {e}")

    def show_about(self):
        """Show about dialog"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About ParkAI Desktop",
            "<h3>ParkAI Desktop v1.0</h3>"
            "<p>Parking Management System</p>"
            "<p>Built with PyQt6</p>"
            "<p>© 2024 ParkAI</p>"
        )

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Application closing...")

        # Stop services
        self.connection_service.stop()
        self.stats_ws.stop()
        self.cameras_ws.stop()

        logger.info("Application closed")
        event.accept()
