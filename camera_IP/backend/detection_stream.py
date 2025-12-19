"""
Detection Stream Service - Real-time license plate detection với WebSocket broadcast
"""
import cv2
import threading
import time
from typing import Optional
from license_plate_detector import get_detector
from websocket_manager import WebSocketManager


class DetectionStreamService:
    """Service để chạy detection loop và broadcast qua WebSocket"""

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.detector = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.active_cameras = {}  # {camera_id: VideoCapture}
        self.lock = threading.Lock()

    def start_detection(self, camera_id: str, rtsp_url: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        """
        Start detection cho 1 camera

        Args:
            camera_id: ID của camera
            rtsp_url: RTSP URL hoặc camera index (0, 1, 2)
            conf_threshold: Confidence threshold
            iou_threshold: IOU threshold
        """
        with self.lock:
            # Kiểm tra camera đã active chưa
            if camera_id in self.active_cameras:
                print(f"[DETECTION] Camera {camera_id} already running")
                return False

            # Mở camera
            try:
                # Nếu là số thì dùng camera index, không thì dùng RTSP URL
                print(f"[DEBUG] Attempting to open camera: {rtsp_url}")

                # Strip go2rtc params (#video=copy#audio=copy) - OpenCV không hiểu cú pháp này
                clean_rtsp_url = rtsp_url.split('#')[0] if '#' in rtsp_url else rtsp_url
                if clean_rtsp_url != rtsp_url:
                    print(f"[DEBUG] Cleaned RTSP URL: {clean_rtsp_url}")

                if clean_rtsp_url.isdigit():
                    cap = cv2.VideoCapture(int(clean_rtsp_url))
                else:
                    # Set RTSP options for better compatibility
                    cap = cv2.VideoCapture(clean_rtsp_url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    print(f"[ERROR] Failed to open camera {camera_id}")
                    print(f"[ERROR] RTSP URL: {rtsp_url}")
                    print(f"[ERROR] Check if camera is accessible and credentials are correct")
                    return False

                # Test read a frame
                ret, frame = cap.read()
                if not ret or frame is None:
                    print(f"[ERROR] Failed to read frame from camera {camera_id}")
                    cap.release()
                    return False

                print(f"[SUCCESS] Camera {camera_id} opened successfully, frame size: {frame.shape}")

                # Load detector nếu chưa có
                if self.detector is None:
                    print("[DETECTION] Loading detector...")
                    self.detector = get_detector()
                    print("[DETECTION] Detector loaded!")

                # Lưu camera
                self.active_cameras[camera_id] = {
                    'cap': cap,
                    'url': rtsp_url,
                    'conf_threshold': conf_threshold,
                    'iou_threshold': iou_threshold,
                    'frame_count': 0,
                    'detection_count': 0
                }

                # Start detection thread nếu chưa chạy
                if not self.running:
                    self.running = True
                    self.thread = threading.Thread(target=self._detection_loop, daemon=True)
                    self.thread.start()
                    print("[DETECTION] Detection loop started")

                print(f"[DETECTION] Camera {camera_id} started: {rtsp_url}")
                return True

            except Exception as e:
                print(f"[ERROR] Failed to start camera {camera_id}: {e}")
                return False

    def stop_detection(self, camera_id: str):
        """Stop detection cho 1 camera"""
        with self.lock:
            if camera_id not in self.active_cameras:
                return False

            # Release camera
            camera_info = self.active_cameras[camera_id]
            camera_info['cap'].release()
            del self.active_cameras[camera_id]

            print(f"[DETECTION] Camera {camera_id} stopped")

            # Stop thread nếu không còn camera nào
            if len(self.active_cameras) == 0:
                self.running = False
                print("[DETECTION] Detection loop stopped")

            return True

    def stop_all(self):
        """Stop tất cả cameras"""
        with self.lock:
            camera_ids = list(self.active_cameras.keys())
            for camera_id in camera_ids:
                self.stop_detection(camera_id)

            self.running = False

    def _detection_loop(self):
        """Main detection loop - chạy trong thread riêng"""
        print("[DETECTION] Detection loop running...")

        while self.running:
            # Process từng camera
            camera_ids = list(self.active_cameras.keys())

            for camera_id in camera_ids:
                try:
                    with self.lock:
                        if camera_id not in self.active_cameras:
                            continue

                        camera_info = self.active_cameras[camera_id]
                        cap = camera_info['cap']

                    # Read frame - lấy frame hiện tại
                    ret, frame = cap.read()

                    if not ret:
                        print(f"[WARNING] Failed to read frame from {camera_id}")
                        continue

                    # Update frame count
                    with self.lock:
                        camera_info['frame_count'] += 1

                    # Resize frame nhỏ hơn để tăng tốc inference (giữ nguyên aspect ratio)
                    # Detection vẫn chính xác nhưng nhanh hơn 3-4 lần
                    original_h, original_w = frame.shape[:2]
                    target_size = 640  # YOLO standard size

                    if max(original_h, original_w) > target_size:
                        scale = target_size / max(original_h, original_w)
                        new_w = int(original_w * scale)
                        new_h = int(original_h * scale)
                        resized_frame = cv2.resize(frame, (new_w, new_h))
                    else:
                        resized_frame = frame
                        scale = 1.0

                    # CHỈ DETECT - không vẽ box, không encode frame
                    # Frontend sẽ tự vẽ box lên canvas (nhanh hơn nhiều!)
                    detections = self.detector.detect_from_frame(
                        resized_frame,
                        conf_threshold=camera_info['conf_threshold'],
                        iou_threshold=camera_info['iou_threshold']
                    )

                    # Scale bbox coordinates back to original size
                    for det in detections:
                        det['bbox'] = [int(coord / scale) for coord in det['bbox']]

                    # Convert bbox format: [x1, y1, x2, y2] -> [x, y, w, h]
                    formatted_detections = []
                    for det in detections:
                        x1, y1, x2, y2 = det['bbox']
                        w = x2 - x1
                        h = y2 - y1

                        formatted_detections.append({
                            'class': det['class_name'],
                            'confidence': det['confidence'],
                            'bbox': [int(x1), int(y1), int(w), int(h)],  # [x, y, width, height]
                            'camera_id': camera_id,
                            'frame_id': camera_info['frame_count'],
                            'timestamp': time.time()
                        })

                    # Update detection count
                    if len(formatted_detections) > 0:
                        with self.lock:
                            camera_info['detection_count'] += len(formatted_detections)

                    # CHỈ GỬI DETECTIONS - không gửi frame
                    # Giảm bandwidth từ ~5MB/s xuống ~5KB/s !!!
                    message = {
                        'detections': formatted_detections,
                        'camera_id': camera_id,
                        'frame_id': camera_info['frame_count']
                    }

                    self.websocket_manager.broadcast_detections(message)

                    if len(formatted_detections) > 0:
                        print(f"[DETECTION] Camera {camera_id} - Frame {camera_info['frame_count']}: {len(formatted_detections)} detection(s)")

                except Exception as e:
                    print(f"[ERROR] Detection error for camera {camera_id}: {e}")

            # Sleep ngắn để giảm CPU load nhưng vẫn giữ FPS cao
            time.sleep(0.05)  # ~20 FPS (tốt cho real-time detection)

        print("[DETECTION] Detection loop stopped")

    def get_stats(self):
        """Lấy thống kê detection"""
        with self.lock:
            stats = {}
            for camera_id, camera_info in self.active_cameras.items():
                stats[camera_id] = {
                    'url': camera_info['url'],
                    'frame_count': camera_info['frame_count'],
                    'detection_count': camera_info['detection_count'],
                    'conf_threshold': camera_info['conf_threshold'],
                    'iou_threshold': camera_info['iou_threshold']
                }
            return stats
