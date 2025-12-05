"""
WebSocket Manager cho real-time updates
"""
from PyQt6.QtCore import QThread, pyqtSignal
import websocket
import json
from utils.logger import logger


class WebSocketWorker(QThread):
    """
    WebSocket worker thread

    Signals:
        message_received: Emit khi nhận message từ server
        connected: Emit khi kết nối thành công
        disconnected: Emit khi mất kết nối
    """

    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.ws = None
        self.running = True

    def run(self):
        """Thread main loop"""
        while self.running:
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )

                # Run forever (blocking)
                self.ws.run_forever()

            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            # Nếu connection đóng và vẫn running, reconnect sau 3s
            if self.running:
                logger.info(f"WebSocket reconnecting in 3s... ({self.url})")
                self.msleep(3000)  # Sleep 3 giây

    def _on_open(self, ws):
        """WebSocket opened"""
        logger.info(f"WebSocket connected: {self.url}")
        self.connected.emit()

    def _on_message(self, ws, message):
        """Message received"""
        # Ignore ping/pong messages
        if message.strip().lower() in ["ping", "pong"]:
            return

        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message (ignored): {message}")

    def _on_error(self, ws, error):
        """Error occurred"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Connection closed"""
        logger.info(f"WebSocket closed: {self.url}")
        self.disconnected.emit()

    def stop(self):
        """Stop worker"""
        self.running = False
        if self.ws:
            self.ws.close()
        self.quit()
        self.wait()
