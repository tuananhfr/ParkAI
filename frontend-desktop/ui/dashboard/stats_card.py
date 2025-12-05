"""
Stats Card Widget - Hiển thị 1 stat (Entries, Exits, etc.)
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class StatsCard(QWidget):
    """
    Card hiển thị 1 stat với title, value, và icon

    Example:
        card = StatsCard("Entries Today", 0, "🚗")
        card.update_value(42)
    """

    def __init__(self, title: str, initial_value: int = 0, icon: str = "📊"):
        super().__init__()
        self.title_text = title
        self.current_value = initial_value
        self.icon = icon
        self.setup_ui()

    def setup_ui(self):
        """Setup card UI"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Icon
        icon_label = QLabel(self.icon)
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Value
        self.value_label = QLabel(str(self.current_value))
        value_font = QFont()
        value_font.setPointSize(36)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        # Title
        title_label = QLabel(self.title_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #666;")
        layout.addWidget(title_label)

        # Card styling
        self.setStyleSheet("""
            StatsCard {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            StatsCard:hover {
                border: 1px solid #0d6efd;
            }
        """)

        # Fixed height cho card
        self.setMinimumHeight(200)
        self.setMaximumHeight(250)

    def update_value(self, value):
        """
        Update value displayed

        Args:
            value: New value (int hoặc float)
        """
        self.current_value = value

        # Format: Nếu float, hiển thị 2 chữ số thập phân
        if isinstance(value, float):
            display_text = f"{value:,.2f}"
        else:
            display_text = f"{value:,}"  # Thêm dấu phẩy (1,000)

        self.value_label.setText(display_text)

    def get_value(self):
        """Get current value"""
        return self.current_value
