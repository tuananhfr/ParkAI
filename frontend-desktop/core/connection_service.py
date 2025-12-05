"""
Connection service để check backend status periodically
"""
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from .api_client import APIClient
from .models import ConnectionStatus
from utils.logger import logger


class ConnectionWorker(QThread):
    """
    Worker thread để check connection status
    (Chạy ở background thread, không block UI)
    """

    # Signals
    status_changed = pyqtSignal(ConnectionStatus)  # Emit khi status thay đổi

    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
        self.running = True

    def run(self):
        """Thread main loop - check status"""
        status = self.api_client.check_connection()
        self.status_changed.emit(status)

    def stop(self):
        """Stop worker"""
        self.running = False
        self.quit()
        self.wait()


class ConnectionService(QObject):
    """
    Service quản lý connection status với periodic check

    Signals:
        connection_changed: Emit khi connection status thay đổi (True/False)

    Usage:
        service = ConnectionService(api_client)
        service.connection_changed.connect(self.on_connection_changed)
        service.start()
    """

    # Signals
    connection_changed = pyqtSignal(bool)  # True = connected, False = disconnected
    status_updated = pyqtSignal(ConnectionStatus)  # Full status object

    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
        self.worker = None
        self.current_status = ConnectionStatus(connected=False)
        self.check_interval = 5000  # 5 giây (milliseconds)

    def check_now(self):
        """Check connection status ngay lập tức"""
        if self.worker and self.worker.isRunning():
            # Worker đang chạy, đợi nó xong
            return

        # Create new worker
        self.worker = ConnectionWorker(self.api_client)
        self.worker.status_changed.connect(self._handle_status)
        self.worker.start()

    def _handle_status(self, status: ConnectionStatus):
        """Handle status từ worker thread"""
        # Check nếu status thay đổi
        if status.connected != self.current_status.connected:
            logger.info(f"Connection status changed: {status.connected}")
            self.connection_changed.emit(status.connected)

        self.current_status = status
        self.status_updated.emit(status)

    def start(self):
        """Start periodic status check"""
        from PyQt6.QtCore import QTimer

        # Check ngay lập tức
        self.check_now()

        # Setup timer cho periodic check
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_now)
        self.timer.start(self.check_interval)

        logger.info(f"Connection service started (interval: {self.check_interval}ms)")

    def stop(self):
        """Stop service"""
        if hasattr(self, 'timer'):
            self.timer.stop()

        if self.worker:
            self.worker.stop()

        logger.info("Connection service stopped")
