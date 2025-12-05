"""
Settings Widget - Cấu hình hệ thống (bám /api/config giống web SettingsModal)

Sử dụng QTabWidget để tạo các tab tương đương web:
- Cameras
- Parking
- Staff
- Subscriptions
- Card reader
- Report
- IP máy chủ central
- Frontend → Backend (desktop: chỉ hiển thị thông tin)
- P2P / Central Sync (placeholder)
- Barrier hồng ngoại (placeholder)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Dict, Optional
from utils.logger import logger
from config import config as app_config
from urllib.parse import urlparse


class SettingsWidget(QWidget):
    """
    Settings form bám logic /api/config của backend (central/edge),
    tương đương các tab chính trong SettingsModal của web:
    - Cấu hình Camera (edge_cameras)
    - Phí gửi xe (parking)
    - Staff API
    - Subscriptions API
    - IP Central server hiện tại
    """

    settings_changed = pyqtSignal(dict)  # Emit khi settings thay đổi

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.current_config: Dict = {}
        self.backend_type: Optional[str] = None  # "edge" | "central" | None

        # Widgets sẽ được gán trong setup_ui / per-tab setup
        self.parking_fee_base: QDoubleSpinBox
        self.parking_fee_per_hour: QSpinBox
        self.parking_fee_overnight: QSpinBox
        self.parking_fee_daily_max: QSpinBox
        self.staff_api_url: QLineEdit
        self.subs_api_url: QLineEdit
        self.staff_table: QTableWidget
        self.subs_table: QTableWidget
        self.central_ip: QLineEdit
        self.cameras_table: QTableWidget
        self.report_api_url: QLineEdit
        # Frontend-backend tab (desktop chỉ hiển thị thông tin)
        self.fb_backend_host: QLineEdit
        self.fb_backend_port: QLineEdit

        self.setup_ui()
        logger.info("Settings widget initialized")

    def setup_ui(self):
        """Setup UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # === Header (cố định, phía trên tabs) ===
        header_layout = QHBoxLayout()
        title = QLabel("⚙️ Settings")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # === QTabWidget giống các tab trên web ===
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Cameras tab
        cameras_tab = QWidget()
        cameras_layout = QVBoxLayout(cameras_tab)
        cameras_label = QLabel("Cấu hình Edge Cameras (giống tab Cameras trên web)")
        cameras_label.setStyleSheet("font-weight: bold; margin-bottom: 8px;")
        cameras_layout.addWidget(cameras_label)

        self.cameras_table = QTableWidget()
        self.cameras_table.setColumnCount(4)
        self.cameras_table.setHorizontalHeaderLabels(["ID", "Tên", "IP", "Loại cổng"])
        self.cameras_table.horizontalHeader().setStretchLastSection(True)
        cameras_layout.addWidget(self.cameras_table)
        cameras_layout.addStretch()

        self.tabs.addTab(cameras_tab, "Cameras")

        # Parking tab
        parking_tab = QWidget()
        parking_layout = QFormLayout(parking_tab)
        parking_layout.setSpacing(10)

        self.parking_fee_base = QDoubleSpinBox()
        self.parking_fee_base.setRange(0, 24)
        self.parking_fee_base.setDecimals(1)
        self.parking_fee_base.setSingleStep(0.1)
        self.parking_fee_base.setSuffix(" giờ")
        parking_layout.addRow("Số giờ miễn phí:", self.parking_fee_base)

        self.parking_fee_per_hour = QSpinBox()
        self.parking_fee_per_hour.setRange(0, 1_000_000_000)
        self.parking_fee_per_hour.setSuffix(" đ/giờ")
        parking_layout.addRow("Phí mỗi giờ:", self.parking_fee_per_hour)

        self.parking_fee_overnight = QSpinBox()
        self.parking_fee_overnight.setRange(0, 1_000_000_000)
        self.parking_fee_overnight.setSuffix(" đ")
        parking_layout.addRow("Phí qua đêm:", self.parking_fee_overnight)

        self.parking_fee_daily_max = QSpinBox()
        self.parking_fee_daily_max.setRange(0, 1_000_000_000)
        self.parking_fee_daily_max.setSuffix(" đ/ngày")
        parking_layout.addRow("Phí tối đa 1 ngày:", self.parking_fee_daily_max)

        self.tabs.addTab(parking_tab, "Phí gửi xe")

        # Staff tab
        staff_tab = QWidget()
        staff_vlayout = QVBoxLayout(staff_tab)
        staff_form = QFormLayout()
        staff_form.setSpacing(10)

        self.staff_api_url = QLineEdit()
        self.staff_api_url.setPlaceholderText("https://api.example.com/staff")
        staff_form.addRow("Staff API URL:", self.staff_api_url)
        staff_vlayout.addLayout(staff_form)

        # Bảng danh sách người trực (read-only giống StaffList trên web)
        self.staff_table = QTableWidget()
        self.staff_table.setColumnCount(6)
        self.staff_table.setHorizontalHeaderLabels(
            ["ID", "Tên", "Chức vụ", "SĐT", "Ca trực", "Trạng thái"]
        )
        self.staff_table.horizontalHeader().setStretchLastSection(True)
        self.staff_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        staff_vlayout.addWidget(self.staff_table)

        self.tabs.addTab(staff_tab, "Người trực")

        # Subscriptions tab
        subs_tab = QWidget()
        subs_vlayout = QVBoxLayout(subs_tab)
        subs_form = QFormLayout()
        subs_form.setSpacing(10)

        self.subs_api_url = QLineEdit()
        self.subs_api_url.setPlaceholderText("https://api.example.com/subscriptions")
        subs_form.addRow("Subscriptions API URL:", self.subs_api_url)
        subs_vlayout.addLayout(subs_form)

        # Bảng danh sách thuê bao (read-only giống SubscriptionList)
        self.subs_table = QTableWidget()
        self.subs_table.setColumnCount(5)
        self.subs_table.setHorizontalHeaderLabels(
            ["Biển số", "Chủ xe", "Loại", "SĐT", "Trạng thái"]
        )
        self.subs_table.horizontalHeader().setStretchLastSection(True)
        self.subs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        subs_vlayout.addWidget(self.subs_table)

        self.tabs.addTab(subs_tab, "Thuê bao")

        # Card reader tab (placeholder giống web)
        card_tab = QWidget()
        card_layout = QVBoxLayout(card_tab)
        card_info = QLabel("Cấu hình đọc thẻ từ sẽ được thêm vào sau (giống web).")
        card_info.setWordWrap(True)
        card_layout.addWidget(card_info)
        card_layout.addStretch()
        self.tabs.addTab(card_tab, "Đọc thẻ từ")

        # Report tab
        report_tab = QWidget()
        report_layout = QFormLayout(report_tab)
        report_layout.setSpacing(10)

        self.report_api_url = QLineEdit()
        self.report_api_url.setPlaceholderText("https://api.example.com/reports")
        report_layout.addRow("Report API URL:", self.report_api_url)

        self.tabs.addTab(report_tab, "Gửi báo cáo")

        # Central server tab
        central_tab = QWidget()
        central_layout = QFormLayout(central_tab)
        central_layout.setSpacing(10)

        self.central_ip = QLineEdit()
        self.central_ip.setPlaceholderText("auto hoặc 192.168.x.x")
        central_layout.addRow("Central IP:", self.central_ip)

        self.tabs.addTab(central_tab, "IP Central")

        # Frontend → Backend tab (desktop chỉ xem thông tin)
        fb_tab = QWidget()
        fb_layout = QFormLayout(fb_tab)
        fb_layout.setSpacing(10)

        self.fb_backend_host = QLineEdit()
        self.fb_backend_host.setPlaceholderText("Host backend (read-only)")
        self.fb_backend_host.setReadOnly(True)
        fb_layout.addRow("Backend Host:", self.fb_backend_host)

        self.fb_backend_port = QLineEdit()
        self.fb_backend_port.setPlaceholderText("Port backend (read-only)")
        self.fb_backend_port.setReadOnly(True)
        fb_layout.addRow("Backend Port:", self.fb_backend_port)

        fb_note = QLabel(
            "Tab này trên web dùng để đổi CENTRAL_URL của frontend.\n"
            "Desktop luôn dùng cấu hình từ file config/.env, nên chỉ hiển thị thông tin."
        )
        fb_note.setWordWrap(True)
        fb_layout.addRow(fb_note)

        self.tabs.addTab(fb_tab, "Frontend → Backend")

        # P2P / Central Sync tab (placeholder)
        p2p_tab = QWidget()
        p2p_layout = QVBoxLayout(p2p_tab)
        p2p_label = QLabel(
            "Cấu hình P2P đồng bộ dữ liệu hiện đang được quản lý trên web frontend.\n"
            "Desktop chỉ xem dữ liệu, không thay đổi cấu hình P2P."
        )
        p2p_label.setWordWrap(True)
        p2p_layout.addWidget(p2p_label)
        p2p_layout.addStretch()
        self.tabs.addTab(p2p_tab, "Central Sync (P2P)")

        # Barrier tab (placeholder)
        barrier_tab = QWidget()
        barrier_layout = QVBoxLayout(barrier_tab)
        barrier_label = QLabel(
            "Cấu hình Barrier hồng ngoại sẽ được thêm vào sau (giống web)."
        )
        barrier_label.setWordWrap(True)
        barrier_layout.addWidget(barrier_label)
        barrier_layout.addStretch()
        self.tabs.addTab(barrier_tab, "Barrier hồng ngoại")

        # === Footer buttons (Save / Reload) ===
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        reset_btn = QPushButton("🔄 Reload từ server")
        reset_btn.clicked.connect(self.reset_settings)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
        """)
        footer_layout.addWidget(reset_btn)

        save_btn = QPushButton("💾 Lưu cấu hình")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #157347;
            }
        """)
        footer_layout.addWidget(save_btn)

        main_layout.addLayout(footer_layout)

    def load_config(self, config: Optional[Dict] = None):
        """
        Load config vào form.
        Nếu config=None → fetch từ /api/config (giống web).
        """
        if config is None:
            logger.info("Fetching config from API")
            config = self.api_client.get_config()

        if not config:
            logger.warning("No config received, keeping previous values")
            return

        self.current_config = config or {}
        # Detect backend_type giống hook useBackendType trên web
        self.backend_type = self.current_config.get("backend_type")
        if not self.backend_type:
            edge_cameras = self.current_config.get("edge_cameras", {}) or {}
            if len(edge_cameras) == 1:
                self.backend_type = "edge"
            else:
                self.backend_type = "central"
        logger.info(f"Loaded config: {config}")

        # === Parking ===
        parking = self.current_config.get("parking", {})
        self.parking_fee_base.setValue(float(parking.get("fee_base", 0.5) or 0))
        self.parking_fee_per_hour.setValue(int(parking.get("fee_per_hour", 25000) or 0))
        self.parking_fee_overnight.setValue(int(parking.get("fee_overnight", 0) or 0))
        self.parking_fee_daily_max.setValue(int(parking.get("fee_daily_max", 0) or 0))

        # === Staff / Subscriptions API URLs ===
        staff_cfg = self.current_config.get("staff", {})
        self.staff_api_url.setText(staff_cfg.get("api_url", "") or "")

        subs_cfg = self.current_config.get("subscriptions", {})
        self.subs_api_url.setText(subs_cfg.get("api_url", "") or "")

        # === Report API ===
        report_cfg = self.current_config.get("report", {})
        self.report_api_url.setText(report_cfg.get("api_url", "") or "")

        # === Central server IP ===
        central_cfg = self.current_config.get("central_server", {})
        self.central_ip.setText(central_cfg.get("ip", "") or "")

        # === Edge cameras list ===
        edge_cameras = self.current_config.get("edge_cameras", {}) or {}
        items = sorted(edge_cameras.items(), key=lambda kv: int(kv[0]))

        self.cameras_table.setRowCount(len(items))
        for row, (cam_id, cam_cfg) in enumerate(items):
            id_item = QTableWidgetItem(str(cam_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cameras_table.setItem(row, 0, id_item)

            name_item = QTableWidgetItem(cam_cfg.get("name", ""))
            self.cameras_table.setItem(row, 1, name_item)

            ip_item = QTableWidgetItem(cam_cfg.get("ip", ""))
            # Nếu backend là edge, IP auto → không cho sửa
            if self.backend_type == "edge":
                ip_item.setFlags(ip_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.cameras_table.setItem(row, 2, ip_item)

            # camera_type: chỉ cho phép ENTRY/EXIT (giống select trên web)
            cam_type = cam_cfg.get("camera_type", "ENTRY")
            if cam_type not in ("ENTRY", "EXIT"):
                cam_type = "ENTRY"
            cam_type_item = QTableWidgetItem(cam_type)
            self.cameras_table.setItem(row, 3, cam_type_item)

        # === Frontend → Backend info (read-only, dựa trên CENTRAL_URL của desktop) ===
        try:
            parsed = urlparse(app_config.CENTRAL_URL)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            self.fb_backend_host.setText(host)
            self.fb_backend_port.setText(str(port))
        except Exception as e:
            logger.error(f"Error parsing CENTRAL_URL for frontend-backend tab: {e}")
            self.fb_backend_host.setText("")
            self.fb_backend_port.setText("")

        # === Staff list ===
        staff_list = []
        try:
            staff_list = self.api_client.get_staff()
        except Exception as e:
            logger.error(f"Error fetching staff list: {e}")
        self.staff_table.setRowCount(len(staff_list))
        for row, person in enumerate(staff_list):
            self.staff_table.setItem(row, 0, QTableWidgetItem(str(person.get("id", ""))))
            self.staff_table.setItem(row, 1, QTableWidgetItem(person.get("name", "")))
            self.staff_table.setItem(row, 2, QTableWidgetItem(person.get("position", "") or "-"))
            self.staff_table.setItem(row, 3, QTableWidgetItem(person.get("phone", "") or "-"))
            self.staff_table.setItem(row, 4, QTableWidgetItem(person.get("shift", "") or "-"))
            status_text = "Hoạt động" if person.get("status") == "active" else "Nghỉ"
            self.staff_table.setItem(row, 5, QTableWidgetItem(status_text))

        # === Subscriptions list ===
        subs_list = []
        try:
            subs_list = self.api_client.get_subscriptions()
        except Exception as e:
            logger.error(f"Error fetching subscriptions list: {e}")
        self.subs_table.setRowCount(len(subs_list))
        for row, sub in enumerate(subs_list):
            self.subs_table.setItem(row, 0, QTableWidgetItem(sub.get("plate_number", "")))
            self.subs_table.setItem(row, 1, QTableWidgetItem(sub.get("owner_name", "") or "-"))
            self.subs_table.setItem(row, 2, QTableWidgetItem(sub.get("type", "") or "-"))
            self.subs_table.setItem(row, 3, QTableWidgetItem(sub.get("phone", "") or "-"))
            status_text = "Hoạt động" if sub.get("status") == "active" else "Nghỉ"
            self.subs_table.setItem(row, 4, QTableWidgetItem(status_text))

    def get_config(self) -> Dict:
        """
        Lấy config từ form, merge vào current_config
        (để không làm mất các phần khác như P2P, report...).
        """
        cfg = dict(self.current_config or {})

        # Parking
        parking = dict(cfg.get("parking", {}))
        parking.update({
            "fee_base": float(self.parking_fee_base.value()),
            "fee_per_hour": int(self.parking_fee_per_hour.value()),
            "fee_overnight": int(self.parking_fee_overnight.value()),
            "fee_daily_max": int(self.parking_fee_daily_max.value()),
        })
        cfg["parking"] = parking

        # Staff
        staff_cfg = dict(cfg.get("staff", {}))
        staff_cfg["api_url"] = self.staff_api_url.text().strip()
        cfg["staff"] = staff_cfg

        # Subscriptions
        subs_cfg = dict(cfg.get("subscriptions", {}))
        subs_cfg["api_url"] = self.subs_api_url.text().strip()
        cfg["subscriptions"] = subs_cfg

        # Central server
        central_cfg = dict(cfg.get("central_server", {}))
        central_cfg["ip"] = self.central_ip.text().strip()
        cfg["central_server"] = central_cfg

        # Edge cameras (đọc từ bảng)
        edge_cameras: Dict[str, Dict] = {}
        rows = self.cameras_table.rowCount()
        for row in range(rows):
            id_item = self.cameras_table.item(row, 0)
            name_item = self.cameras_table.item(row, 1)
            ip_item = self.cameras_table.item(row, 2)
            type_item = self.cameras_table.item(row, 3)

            if not id_item:
                continue
            cam_id_str = id_item.text().strip()
            if not cam_id_str:
                continue

            edge_cameras[cam_id_str] = {
                "name": name_item.text().strip() if name_item else "",
                "ip": ip_item.text().strip() if ip_item else "",
                "camera_type": type_item.text().strip() if type_item else "ENTRY",
            }

        if edge_cameras:
            cfg["edge_cameras"] = edge_cameras

        # Report config
        report_cfg = dict(cfg.get("report", {}))
        report_cfg["api_url"] = self.report_api_url.text().strip()
        cfg["report"] = report_cfg

        return cfg

    def save_settings(self):
        """Save settings to backend (POST /api/config giống web)"""
        config = self.get_config()
        logger.info(f"Saving settings: {config}")

        success = self.api_client.update_config(config)

        if success:
            QMessageBox.information(
                self,
                "Thành công",
                "Đã lưu cấu hình thành công."
            )
            self.current_config = config
            self.settings_changed.emit(config)
            logger.info("Settings saved successfully")
        else:
            QMessageBox.critical(
                self,
                "Lỗi",
                "Không thể lưu cấu hình. Vui lòng kiểm tra backend."
            )
            logger.error("Failed to save settings")

    def reset_settings(self):
        """Reload cấu hình mới nhất từ backend"""
        reply = QMessageBox.question(
            self,
            "Reload config",
            "Tải lại cấu hình từ server (mọi thay đổi chưa lưu sẽ mất)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Reloading config from backend")
            self.load_config(None)
