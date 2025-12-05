"""
MJPEG Stream Worker - Simple, stable, and smooth video streaming
Perfect for 24/7 operation with PyQt6
"""
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import cv2
import numpy as np
from utils.logger import logger
import time


class MJPEGWorker(QThread):
    """
    Worker thread để stream MJPEG từ backend

    Advantages over WebRTC:
    - ✅ Cực kỳ đơn giản và ổn định
    - ✅ Smooth playback (native OpenCV decode)
    - ✅ Perfect cho 24/7 operation
    - ✅ Auto-reconnect khi mất kết nối
    - ✅ Low latency (~50ms)

    Signals:
        frame_ready: Emit QPixmap khi có frame mới
        error: Emit error message
        connected: Emit khi stream connected
        disconnected: Emit khi stream disconnected
    """
    frame_ready = pyqtSignal(QPixmap)
    error = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, stream_url: str, camera_id: int = None):
        """
        Args:
            stream_url: URL của MJPEG stream (e.g., "http://192.168.0.144:8000/api/stream/annotated")
            camera_id: ID của camera (for logging)
        """
        super().__init__()
        self.stream_url = stream_url
        self.camera_id = camera_id
        self.running = False
        self.cap = None

        # Performance tracking
        self.frame_count = 0
        self.start_time = 0
        self.last_fps_log = 0

        logger.info(f"MJPEG worker initialized for camera {camera_id}, URL={stream_url}")

    def run(self):
        """Main thread loop"""
        self.running = True
        self.start_time = time.time()
        self.last_fps_log = self.start_time

        while self.running:
            try:
                # Connect to stream
                if not self.connect_stream():
                    # Retry sau 3 giây
                    time.sleep(3)
                    continue

                # Read and process frames
                self.process_frames()

            except Exception as e:
                logger.error(f"MJPEG worker error: {e}")
                self.error.emit(str(e))
                self.cleanup_stream()

                # Retry sau 3 giây
                if self.running:
                    time.sleep(3)

        # Cleanup
        self.cleanup_stream()

    def connect_stream(self) -> bool:
        """
        Kết nối tới MJPEG stream

        Returns:
            True nếu connect thành công
        """
        try:
            logger.info(f"Connecting to MJPEG stream: {self.stream_url}")

            # Open stream với OpenCV
            self.cap = cv2.VideoCapture(self.stream_url)

            if not self.cap.isOpened():
                raise Exception("Cannot open stream")

            # Set buffer size = 1 để minimize latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.connected.emit()
            logger.info(f"MJPEG stream connected for camera {self.camera_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to stream: {e}")
            self.error.emit(f"Connection failed: {str(e)}")
            self.cleanup_stream()
            return False

    def process_frames(self):
        """Process frames from stream"""
        consecutive_failures = 0
        max_failures = 30  # 30 frames liên tiếp fail → reconnect

        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()

            if not ret or frame is None:
                consecutive_failures += 1
                logger.warning(f"Failed to read frame (failures: {consecutive_failures})")

                if consecutive_failures >= max_failures:
                    logger.error("Too many consecutive failures, reconnecting...")
                    self.disconnected.emit()
                    raise Exception("Stream connection lost")

                time.sleep(0.1)
                continue

            # Reset failure counter
            consecutive_failures = 0
            self.frame_count += 1

            # Convert frame to QPixmap
            pixmap = self.frame_to_pixmap(frame)

            if pixmap:
                self.frame_ready.emit(pixmap)

            # Log FPS every 5 seconds
            current_time = time.time()
            if current_time - self.last_fps_log >= 5.0:
                elapsed = current_time - self.start_time
                fps = self.frame_count / elapsed if elapsed > 0 else 0
                logger.debug(f"Camera {self.camera_id}: Frames={self.frame_count}, FPS={fps:.1f}")
                self.last_fps_log = current_time

    def frame_to_pixmap(self, frame) -> QPixmap:
        """
        Convert OpenCV frame (BGR) to QPixmap

        Args:
            frame: OpenCV frame (numpy array, BGR format)

        Returns:
            QPixmap ready for display
        """
        try:
            # OpenCV returns BGR, convert to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            height, width, channels = rgb_frame.shape
            bytes_per_line = channels * width

            # Create QImage from numpy array
            q_img = QImage(
                rgb_frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )

            # Scale to display size (320x240)
            # Qt's scaled() is hardware-accelerated
            from PyQt6.QtCore import Qt
            pixmap = QPixmap.fromImage(q_img).scaled(
                320,
                240,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            return pixmap

        except Exception as e:
            logger.error(f"Error converting frame to pixmap: {e}")
            return None

    def cleanup_stream(self):
        """Cleanup stream resources"""
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None

    def stop(self):
        """Stop worker thread"""
        logger.info(f"Stopping MJPEG worker for camera {self.camera_id}")
        self.running = False

        # Wait for thread to finish (max 2 seconds)
        self.wait(2000)

        # Force terminate if still running
        if self.isRunning():
            logger.warning("Force terminating MJPEG worker")
            self.terminate()
            self.wait()

        self.cleanup_stream()
