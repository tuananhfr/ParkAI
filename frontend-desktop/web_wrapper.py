"""
Web App Wrapper - Electron-style desktop app
Embeds the React web app for smooth 60 FPS performance
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import QUrl, Qt


class WebAppWrapper(QMainWindow):
    """
    Desktop wrapper cho web app
    Performance = native browser (60 FPS)
    """

    def __init__(self, web_url="http://localhost:5173"):
        super().__init__()
        self.web_url = web_url
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        self.setWindowTitle("ParkAI - Monitoring Dashboard")
        self.setGeometry(100, 100, 1400, 900)

        # Create web view
        self.web_view = QWebEngineView()

        # Enable all optimizations
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

        # Enable modern web features (WebSocket, WebRTC, etc.)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        # Load web app
        print(f"Loading web app from: {self.web_url}")
        self.web_view.setUrl(QUrl(self.web_url))

        # Set as central widget
        self.setCentralWidget(self.web_view)

        # Window flags
        self.setWindowFlags(Qt.WindowType.Window)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # F11: Fullscreen toggle
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        # Esc: Exit fullscreen
        elif event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
        # F5: Reload
        elif event.key() == Qt.Key.Key_F5:
            self.web_view.reload()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="ParkAI Web App Wrapper")
    parser.add_argument(
        "--url",
        default="http://localhost:5173",
        help="Web app URL (default: http://localhost:5173)"
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start in fullscreen mode"
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("ParkAI Desktop")

    window = WebAppWrapper(web_url=args.url)

    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
