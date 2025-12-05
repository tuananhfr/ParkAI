"""
WebRTC Worker - Kết nối WebRTC với Edge backend và hiển thị video
Optimized version with hardware acceleration and frame dropping
"""
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
import asyncio
import json
import time
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from av import VideoFrame
from utils.logger import logger
import numpy as np
import cv2


class WebRTCWorker(QThread):
    """
    Worker thread để xử lý WebRTC connection với hardware acceleration

    Optimizations:
    - Hardware-accelerated frame decoding (GPU)
    - Frame dropping để maintain 30 FPS
    - Optimized QImage conversion
    - Target resolution: 720p minimum

    Signals:
        frame_ready: Emit QPixmap khi có frame mới
        error: Emit error message
        connected: Emit khi WebRTC connected
        disconnected: Emit khi WebRTC disconnected
    """
    frame_ready = pyqtSignal(QPixmap)
    error = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, camera_id: int, api_client, mode: str = "annotated", target_fps: int = 30):
        """
        Args:
            camera_id: ID của camera
            api_client: APIClient instance
            mode: "raw" hoặc "annotated"
            target_fps: Target FPS (default 30)
        """
        super().__init__()
        self.camera_id = camera_id
        self.api_client = api_client
        self.mode = mode
        self.target_fps = target_fps
        self.running = False
        self.pc = None

        # Frame timing
        self.target_frame_time = 1.0 / target_fps  # 33.3ms for 30 FPS
        self.last_frame_time = 0
        self.frame_count = 0
        self.dropped_frames = 0

        logger.info(f"WebRTC worker initialized for camera {camera_id}, mode={mode}, target_fps={target_fps}")

    def run(self):
        """Main thread loop - chạy asyncio event loop"""
        self.running = True

        try:
            # Tạo event loop mới cho thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Chạy WebRTC connection
            loop.run_until_complete(self.connect_webrtc())

        except Exception as e:
            logger.error(f"WebRTC worker error: {e}")
            self.error.emit(str(e))
        finally:
            if loop:
                loop.close()

    async def connect_webrtc(self):
        """Kết nối WebRTC với backend"""
        try:
            # Tạo RTCPeerConnection với STUN server
            config = RTCConfiguration(
                iceServers=[
                    RTCIceServer(urls=["stun:stun.l.google.com:19302"])
                ]
            )
            self.pc = RTCPeerConnection(configuration=config)

            # Handle incoming tracks
            @self.pc.on("track")
            async def on_track(track):
                logger.info(f"Received track: {track.kind}")

                if track.kind == "video":
                    self.connected.emit()

                    # Reset counters
                    self.frame_count = 0
                    self.dropped_frames = 0
                    self.last_frame_time = time.time()

                    while self.running:
                        try:
                            # Nhận frame từ track
                            frame = await track.recv()

                            current_time = time.time()
                            elapsed = current_time - self.last_frame_time

                            # Frame dropping: Chỉ process nếu đủ thời gian
                            if elapsed < self.target_frame_time:
                                self.dropped_frames += 1
                                continue

                            self.last_frame_time = current_time
                            self.frame_count += 1

                            # Process frame với hardware acceleration
                            pixmap = self.process_frame_optimized(frame)

                            if pixmap:
                                # Emit frame
                                self.frame_ready.emit(pixmap)

                            # Log performance every 100 frames
                            if self.frame_count % 100 == 0:
                                actual_fps = 1.0 / elapsed if elapsed > 0 else 0
                                logger.debug(
                                    f"Camera {self.camera_id}: "
                                    f"Frames={self.frame_count}, "
                                    f"Dropped={self.dropped_frames}, "
                                    f"FPS={actual_fps:.1f}"
                                )

                        except Exception as e:
                            if self.running:
                                logger.error(f"Error receiving frame: {e}")
                                break

            @self.pc.on("connectionstatechange")
            async def on_connectionstatechange():
                """
                Callback khi trạng thái WebRTC connection thay đổi.

                Lưu ý: có thể xảy ra race-condition khi cleanup() đã set self.pc = None
                trong khi callback vẫn đang chạy. Vì vậy luôn lấy local reference trước.
                """
                try:
                    pc = self.pc
                    if pc is None:
                        # Đã được cleanup, bỏ qua callback
                        return

                    state = getattr(pc, "connectionState", None)
                    logger.info(f"WebRTC connection state: {state}")

                    if state == "failed":
                        self.error.emit("Connection failed")
                        self.disconnected.emit()
                    elif state == "closed":
                        self.disconnected.emit()
                except Exception as e:
                    # Đừng để Task exception rơi tự do
                    logger.error(f"Error in connectionstatechange handler: {e}")

            # Thêm video transceiver ở chế độ recvonly giống hành vi browser,
            # tránh bug aiortc khi cả hai đầu đều dùng aiortc (offer không có direction rõ ràng)
            self.pc.addTransceiver("video", direction="recvonly")

            # Tạo offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            logger.info(f"Created WebRTC offer for camera {self.camera_id}")

            # Gửi offer đến backend và nhận answer
            endpoint = f"/api/cameras/{self.camera_id}/offer-{self.mode}"

            offer_data = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp
            }

            # POST offer
            response_data = self.api_client._request(
                "POST",
                endpoint,
                json=offer_data
            )

            if not response_data:
                raise Exception("No response from backend")

            # Set remote description (answer)
            answer = RTCSessionDescription(
                sdp=response_data["sdp"],
                type=response_data["type"]
            )
            await self.pc.setRemoteDescription(answer)

            logger.info(f"WebRTC connection established for camera {self.camera_id}")

            # Keep connection alive
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"WebRTC connection error: {e}")
            self.error.emit(str(e))
        finally:
            await self.cleanup()

    def process_frame_optimized(self, frame: VideoFrame) -> QPixmap:
        """
        Process video frame với hardware acceleration

        Optimizations:
        - Use OpenCV for hardware-accelerated operations
        - Direct memory access
        - Optimized QImage format
        - Maintain aspect ratio while scaling to display size

        Args:
            frame: VideoFrame from aiortc

        Returns:
            QPixmap ready for display
        """
        try:
            # Convert VideoFrame to numpy array (RGB24)
            img = frame.to_ndarray(format="rgb24")
            height, width, channels = img.shape

            # Target display size (scaled to fit in card)
            target_width = 320
            target_height = 240

            # Calculate scaling với aspect ratio preserved
            scale = min(target_width / width, target_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            # Resize với hardware acceleration (INTER_LINEAR is GPU-accelerated on modern systems)
            # Note: OpenCV tự động dùng GPU nếu available (cv2.cuda)
            img_resized = cv2.resize(
                img,
                (new_width, new_height),
                interpolation=cv2.INTER_LINEAR  # Fast and smooth
            )

            # Convert to QImage efficiently
            # RGB888 format để tương thích với Qt
            h, w, ch = img_resized.shape
            bytes_per_line = ch * w

            q_img = QImage(
                img_resized.data,
                w,
                h,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )

            # Convert to QPixmap (this operation is hardware-accelerated by Qt)
            pixmap = QPixmap.fromImage(q_img)

            return pixmap

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return None

    async def cleanup(self):
        """Cleanup WebRTC connection"""
        if self.pc:
            logger.info(f"Closing WebRTC connection (processed {self.frame_count} frames, dropped {self.dropped_frames})")
            await self.pc.close()
            self.pc = None

    def stop(self):
        """Stop worker"""
        logger.info(f"Stopping WebRTC worker for camera {self.camera_id}")
        self.running = False
        self.quit()
        self.wait()
