"""
History Widget - Bảng lịch sử ra/vào
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QAbstractItemView, QLineEdit,
    QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import List, Dict
from utils.logger import logger


class HistoryWidget(QWidget):
    """
    History table với pagination và filters

    Features:
    - Table hiển thị lịch sử ra/vào
    - Pagination (next/prev)
    - Auto-refresh qua WebSocket
    """

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.current_page = 1
        self.items_per_page = 50
        self.all_entries = []
        # Filter & search state (bám logic web frontend)
        self.current_filter = "all"  # all | today | in_parking | in | out | changes
        self.search_text = ""
        self.setup_ui()
        logger.info("History widget initialized")

    def setup_ui(self):
        """Setup UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # === Header (title + refresh) ===
        header_layout = QHBoxLayout()

        title = QLabel("📋 Parking History")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        header_layout.addWidget(refresh_btn)

        main_layout.addLayout(header_layout)

        # === Filters & Search (bám gần giống HistoryPanel của web) ===
        filter_layout = QHBoxLayout()

        # Filter buttons
        self.all_btn = QPushButton("Tất cả")
        self.today_btn = QPushButton("Hôm nay")
        self.in_parking_btn = QPushButton("Trong bãi")
        self.in_btn = QPushButton("VÀO")
        self.out_btn = QPushButton("RA")
        self.changes_btn = QPushButton("Đã thay đổi")

        for btn in [self.all_btn, self.today_btn, self.in_parking_btn, self.in_btn, self.out_btn, self.changes_btn]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 10px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    background-color: #f8f9fa;
                }
                QPushButton:checked {
                    background-color: #0d6efd;
                    color: white;
                }
            """)

        self.all_btn.clicked.connect(lambda: self.set_filter("all"))
        self.today_btn.clicked.connect(lambda: self.set_filter("today"))
        self.in_parking_btn.clicked.connect(lambda: self.set_filter("in_parking"))
        self.in_btn.clicked.connect(lambda: self.set_filter("in"))
        self.out_btn.clicked.connect(lambda: self.set_filter("out"))
        self.changes_btn.clicked.connect(lambda: self.set_filter("changes"))

        filter_layout.addWidget(self.all_btn)
        filter_layout.addWidget(self.today_btn)
        filter_layout.addWidget(self.in_parking_btn)
        filter_layout.addWidget(self.in_btn)
        filter_layout.addWidget(self.out_btn)
        filter_layout.addWidget(self.changes_btn)

        filter_layout.addStretch()

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm biển số...")
        self.search_input.setFixedWidth(200)
        self.search_input.returnPressed.connect(self.on_search)
        filter_layout.addWidget(self.search_input)

        main_layout.addLayout(filter_layout)

        # Set default filter button
        self.all_btn.setChecked(True)

        # === Table ===
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Plate", "Type", "Entry Time", "Exit Time", "Duration", "Fee"
        ])

        # Table properties
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        # Column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Plate
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Entry Time
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Exit Time
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Duration
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Fee

        # Table style
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                gridline-color: #dee2e6;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 10px;
                border: none;
                border-right: 1px solid #dee2e6;
                border-bottom: 2px solid #dee2e6;
                font-weight: bold;
            }
        """)

        main_layout.addWidget(self.table)

        # === Pagination ===
        pagination_layout = QHBoxLayout()

        self.info_label = QLabel("No data")
        pagination_layout.addWidget(self.info_label)

        pagination_layout.addStretch()

        self.prev_btn = QPushButton("⬅ Previous")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover:enabled {
                background-color: #f8f9fa;
            }
            QPushButton:disabled {
                color: #ccc;
            }
        """)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet("margin: 0 10px; font-weight: bold;")
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Next ➡")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover:enabled {
                background-color: #f8f9fa;
            }
            QPushButton:disabled {
                color: #ccc;
            }
        """)
        pagination_layout.addWidget(self.next_btn)

        main_layout.addLayout(pagination_layout)

        # === Row Actions (Edit/Delete) ===
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.edit_btn = QPushButton("✏️ Edit Plate")
        self.edit_btn.clicked.connect(self.edit_selected_entry)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #ffc107;
                color: #212529;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        actions_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self.delete_selected_entry)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                background-color: #dc3545;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #bb2d3b;
            }
        """)
        actions_layout.addWidget(self.delete_btn)

        main_layout.addLayout(actions_layout)

    def update_history(self, entries: List[Dict]):
        """
        Update history table

        Args:
            entries: List of history entry dicts
        """
        logger.info(f"Updating history with {len(entries)} entries")
        self.all_entries = entries
        self.current_page = 1
        self.render_page()

    def render_page(self):
        """Render current page of data"""
        # Calculate pagination
        total = len(self.all_entries)
        total_pages = (total + self.items_per_page - 1) // self.items_per_page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, total)

        page_entries = self.all_entries[start_idx:end_idx]

        # Update table
        self.table.setRowCount(len(page_entries))

        for row, entry in enumerate(page_entries):
            # Phân biệt giữa history entry và history change
            is_change = "change_type" in entry

            if not is_change:
                # ===== History entry (giống web HistoryPanel) =====
                # ID
                self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("id", ""))))

                # Plate (ưu tiên plate_view, fallback plate_id/plate)
                plate_text = (
                    entry.get("plate_view")
                    or entry.get("plate_id")
                    or entry.get("plate", "")
                )
                plate_item = QTableWidgetItem(plate_text)
                plate_item.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
                self.table.setItem(row, 1, plate_item)

                # Type
                vehicle_type = entry.get("customer_type") or entry.get("vehicle_type", "")
                self.table.setItem(row, 2, QTableWidgetItem(vehicle_type))

                # Entry Time
                self.table.setItem(row, 3, QTableWidgetItem(entry.get("entry_time", "")))

                # Exit Time
                exit_time = entry.get("exit_time", "-")
                self.table.setItem(row, 4, QTableWidgetItem(exit_time))

                # Duration
                duration = entry.get("duration", "-")
                self.table.setItem(row, 5, QTableWidgetItem(str(duration)))

                # Fee
                fee = entry.get("fee", 0)
                fee_item = QTableWidgetItem(f"${fee:,.2f}" if fee else "-")
                fee_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 6, fee_item)
            else:
                # ===== History change (tab "Đã thay đổi" trên web) =====
                # ID (change id)
                self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("id", ""))))

                # Plate: Cũ → Mới (nếu có)
                old_plate = entry.get("old_plate_view") or entry.get("old_plate_id") or ""
                new_plate = entry.get("new_plate_view") or entry.get("new_plate_id") or ""
                if entry.get("change_type") == "DELETE":
                    plate_text = f"ĐÃ XOÁ: {old_plate}"
                else:
                    plate_text = f"{old_plate} → {new_plate}" if old_plate or new_plate else ""
                plate_item = QTableWidgetItem(plate_text)
                plate_item.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
                self.table.setItem(row, 1, plate_item)

                # Type: SỬA / XOÁ
                change_type = entry.get("change_type", "").upper()
                self.table.setItem(row, 2, QTableWidgetItem(change_type))

                # Entry Time: changed_at
                changed_at = entry.get("changed_at", "")
                self.table.setItem(row, 3, QTableWidgetItem(changed_at))

                # Các cột còn lại để trống
                for col in range(4, 7):
                    self.table.setItem(row, col, QTableWidgetItem(""))

        # Update pagination controls
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

        # Update info label
        if total > 0:
            self.info_label.setText(f"Showing {start_idx + 1}-{end_idx} of {total} entries")
        else:
            self.info_label.setText("No data")

        logger.debug(f"Rendered page {self.current_page}: {len(page_entries)} entries")

    def prev_page(self):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        """Go to next page"""
        total_pages = (len(self.all_entries) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.render_page()

    def refresh_data(self):
        """Refresh data from API với filter & search hiện tại"""
        logger.info(
            f"Refreshing history data (filter={self.current_filter}, search={self.search_text})"
        )

        # Tab "Đã thay đổi" dùng endpoint riêng /api/parking/history/changes
        if self.current_filter == "changes":
            entries = self.api_client.get_history_changes(limit=100, offset=0)
            self.update_history(entries)
            return

        # Map filter giống web HistoryPanel cho history chính
        today_only = self.current_filter == "today"
        status = None
        in_parking_only = False
        entries_only = False

        if self.current_filter == "in":
            entries_only = True
        elif self.current_filter == "out":
            status = "OUT"
        elif self.current_filter == "in_parking":
            in_parking_only = True

        entries = self.api_client.get_history(
            limit=500,
            offset=0,
            today_only=today_only,
            status=status,
            in_parking_only=in_parking_only,
            entries_only=entries_only,
            search=self.search_text.strip() or None,
        )
        self.update_history(entries)

    def clear_history(self):
        """Clear table"""
        self.table.setRowCount(0)
        self.all_entries = []
        self.info_label.setText("No data")

    # ===== Filters & Search =====

    def set_filter(self, filter_key: str):
        """Set current filter and refresh data"""
        if filter_key == self.current_filter:
            return

        self.current_filter = filter_key

        # Update button checked state
        self.all_btn.setChecked(filter_key == "all")
        self.today_btn.setChecked(filter_key == "today")
        self.in_parking_btn.setChecked(filter_key == "in_parking")
        self.in_btn.setChecked(filter_key == "in")
        self.out_btn.setChecked(filter_key == "out")
        self.changes_btn.setChecked(filter_key == "changes")

        self.refresh_data()

    def on_search(self):
        """Handle search input (Enter pressed)"""
        self.search_text = self.search_input.text()
        self.refresh_data()

    # ===== Edit / Delete actions =====

    def _get_selected_entry(self) -> Dict:
        """Helper: lấy entry tương ứng với row đang chọn"""
        row = self.table.currentRow()
        if row < 0:
            return {}

        global_index = (self.current_page - 1) * self.items_per_page + row
        if 0 <= global_index < len(self.all_entries):
            return self.all_entries[global_index]
        return {}

    def edit_selected_entry(self):
        """Edit plate for selected history entry (PUT /api/parking/history/{id})"""
        entry = self._get_selected_entry()
        if not entry:
            QMessageBox.warning(self, "No selection", "Vui lòng chọn một dòng để sửa.")
            return

        # Không cho sửa trên tab "Đã thay đổi" (chỉ read-only)
        if "change_type" in entry or self.current_filter == "changes":
            QMessageBox.information(self, "Read-only", "Tab 'Đã thay đổi' chỉ để xem lịch sử chỉnh sửa.")
            return

        history_id = entry.get("id")
        if not history_id:
            QMessageBox.warning(self, "Invalid entry", "Không tìm thấy ID của dòng này.")
            return

        current_plate = (
            entry.get("plate_view")
            or entry.get("plate_id")
            or ""
        )

        new_plate, ok = QInputDialog.getText(
            self,
            "Sửa biển số",
            "Nhập biển số mới:",
            text=current_plate
        )

        if not ok or not new_plate.strip():
            return

        normalized = new_plate.strip().upper()
        if len(normalized) < 5:
            QMessageBox.warning(self, "Biển số không hợp lệ", "Biển số phải có ít nhất 5 ký tự.")
            return

        # plate_id: bỏ dấu gạch / space
        plate_id = "".join(ch for ch in normalized if ch.isalnum())
        plate_view = normalized

        logger.info(f"Updating history entry {history_id}: {plate_view} ({plate_id})")
        success = self.api_client.update_history_entry(
            history_id=history_id,
            plate_id=plate_id,
            plate_view=plate_view
        )

        if success:
            QMessageBox.information(self, "Thành công", "Đã cập nhật biển số.")
            self.refresh_data()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể cập nhật biển số. Vui lòng kiểm tra backend.")

    def delete_selected_entry(self):
        """Delete selected history entry (DELETE /api/parking/history/{id})"""
        entry = self._get_selected_entry()
        if not entry:
            QMessageBox.warning(self, "No selection", "Vui lòng chọn một dòng để xóa.")
            return

        # Không cho xóa trên tab "Đã thay đổi"
        if "change_type" in entry or self.current_filter == "changes":
            QMessageBox.information(self, "Read-only", "Tab 'Đã thay đổi' chỉ để xem lịch sử chỉnh sửa.")
            return

        history_id = entry.get("id")
        plate_text = (
            entry.get("plate_view")
            or entry.get("plate_id")
            or ""
        )

        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa lịch sử của xe {plate_text} (ID: {history_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        logger.info(f"Deleting history entry {history_id}")
        success = self.api_client.delete_history_entry(history_id)

        if success:
            QMessageBox.information(self, "Thành công", "Đã xóa entry.")
            self.refresh_data()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể xóa entry. Vui lòng kiểm tra backend.")
