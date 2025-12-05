"""
Dashboard Widget với 4 stats cards
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel
from PyQt6.QtCore import Qt
from .stats_card import StatsCard
from core.models import Stats
from utils.logger import logger


class DashboardWidget(QWidget):
    """
    Dashboard với 4 stats cards:
    - Entries Today
    - Exits Today
    - Vehicles in Parking
    - Revenue Today
    """

    def __init__(self):
        super().__init__()
        self.setup_ui()
        logger.info("Dashboard widget initialized")

    def setup_ui(self):
        """Setup UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("📊 Dashboard Overview")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        main_layout.addWidget(title)

        # Grid layout cho 4 cards (2x2)
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)

        # Create 4 cards
        self.entries_card = StatsCard("Entries Today", 0, "🚗")
        self.exits_card = StatsCard("Exits Today", 0, "🚙")
        self.in_parking_card = StatsCard("Vehicles in Parking", 0, "🅿️")
        self.revenue_card = StatsCard("Revenue Today", 0.0, "💰")

        # Add cards to grid (2 columns)
        cards_layout.addWidget(self.entries_card, 0, 0)
        cards_layout.addWidget(self.exits_card, 0, 1)
        cards_layout.addWidget(self.in_parking_card, 1, 0)
        cards_layout.addWidget(self.revenue_card, 1, 1)

        main_layout.addLayout(cards_layout)

        # Stretch để cards không bị kéo dãn
        main_layout.addStretch()

    def update_stats(self, stats: Stats):
        """
        Update all stats cards

        Args:
            stats: Stats object từ API
        """
        self.entries_card.update_value(stats.entries_today)
        self.exits_card.update_value(stats.exits_today)
        self.in_parking_card.update_value(stats.vehicles_in_parking)
        self.revenue_card.update_value(stats.revenue_today)

        logger.debug(f"Dashboard updated: {stats}")
