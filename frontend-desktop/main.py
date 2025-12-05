"""
ParkAI Desktop Application
Entry point
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.logger import logger
from config import config


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("Starting ParkAI Desktop")
    logger.info(f"Backend URL: {config.CENTRAL_URL}")
    logger.info("=" * 50)

    # Create QApplication instance
    app = QApplication(sys.argv)

    # Set application info
    app.setApplicationName(config.WINDOW_TITLE)
    app.setOrganizationName("ParkAI")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    exit_code = app.exec()

    logger.info("Application exited")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
