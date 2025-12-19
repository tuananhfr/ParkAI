"""
GPU Batch Detection Service - Tối ưu cho xử lý nhiều camera với 1 GPU

Kiến trúc:
1. Camera Threads: Mỗi camera 1 thread riêng để đọc frame (I/O bound)
2. Frame Queue: Queue chứa frames từ tất cả cameras
3. GPU Worker Thread: Lấy batch frames, inference GPU, trả kết quả
4. Results Queue: Broadcast qua WebSocket

Performance:
- Batch size tự động điều chỉnh theo GPU
- GPU utilization ~80-95% (tối ưu)
- Hỗ trợ 1-8 cameras mượt mà
"""

import cv2
import threading
import queue
import time
import torch
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass
from license_plate_detector import get_detector
from websocket_manager import WebSocketManager


@dataclass
class FrameJob:
    """Frame job for processing"""
    camera_id: str
    frame: np.ndarray
    frame_id: int
    timestamp: float
    conf_threshold: float
    iou_threshold: float


@dataclass
class DetectionResult:
    """Detection result"""
    camera_id: str
    frame_id: int
    timestamp: float
    detections: List[dict]


class GPUBatchDetectionService:
    """
    Service xử lý detection cho nhiều cameras sử dụng GPU batch processing

    Auto-tuning:
    - Tự động detect GPU memory
    - Tự động điều chỉnh batch size
    - Tự động giảm batch size nếu GPU OOM
    """

    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.detector = None

        # Threading control
        self.running = False
        self.lock = threading.Lock()

        # Camera management
        self.active_cameras: Dict[str, dict] = {}  # {camera_id: camera_info}
        self.camera_threads: Dict[str, threading.Thread] = {}

        # Frame & Result queues
        self.frame_queue = queue.Queue(maxsize=100)  # Buffer 100 frames max
        self.result_queue = queue.Queue(maxsize=100)

        # GPU worker thread
        self.gpu_worker_thread: Optional[threading.Thread] = None
        self.result_worker_thread: Optional[threading.Thread] = None

        # GPU settings (auto-detect và auto-tune)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.batch_size = self._auto_detect_batch_size()
        self.target_size = 640  # YOLO standard input size

        # Statistics
        self.stats = {
            'total_frames': 0,
            'total_detections': 0,
            'avg_batch_size': 0,
            'avg_inference_time_ms': 0,
            'gpu_utilization': 0
        }

        print(f"[GPU BATCH] Initialized with device={self.device}, batch_size={self.batch_size}")

    def _auto_detect_batch_size(self) -> int:
        """
        Tự động detect batch size tối ưu dựa trên GPU memory

        Returns:
            Optimal batch size
        """
        if not torch.cuda.is_available():
            return 1  # CPU mode

        try:
            # Get GPU memory
            gpu_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3

            # Ước lượng batch size dựa trên GPU memory
            # YOLOv8 cần ~1.5GB cho batch size 4 ở input 640x640
            if gpu_mem_gb >= 12:  # RTX 3080/3090, A4000, etc.
                batch_size = 8
            elif gpu_mem_gb >= 8:  # RTX 3070, RTX 4060 Ti
                batch_size = 6
            elif gpu_mem_gb >= 6:  # RTX 3060, GTX 1660 Ti
                batch_size = 4
            elif gpu_mem_gb >= 4:  # GTX 1650, GTX 1050 Ti
                batch_size = 2
            else:
                batch_size = 1

            print(f"[GPU BATCH] GPU Memory: {gpu_mem_gb:.1f}GB → Batch Size: {batch_size}")
            return batch_size

        except Exception as e:
            print(f"[GPU BATCH] Failed to detect GPU memory: {e}, using batch_size=4")
            return 4

    def start_detection(
        self,
        camera_id: str,
        rtsp_url: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> bool:
        """
        Start detection cho 1 camera

        Args:
            camera_id: Camera ID
            rtsp_url: RTSP URL hoặc camera index
            conf_threshold: Confidence threshold
            iou_threshold: IOU threshold

        Returns:
            True if success
        """
        with self.lock:
            # Kiểm tra camera đã active
            if camera_id in self.active_cameras:
                print(f"[GPU BATCH] Camera {camera_id} already running")
                return False

            # Mở camera
            try:
                print(f"[GPU BATCH] Opening camera {camera_id}: {rtsp_url}")

                # Clean RTSP URL (remove go2rtc params)
                clean_url = rtsp_url.split('#')[0] if '#' in rtsp_url else rtsp_url

                # Open camera
                if clean_url.isdigit():
                    cap = cv2.VideoCapture(int(clean_url))
                else:
                    cap = cv2.VideoCapture(clean_url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency

                if not cap.isOpened():
                    print(f"[GPU BATCH] Failed to open camera {camera_id}")
                    return False

                # Test read frame
                ret, frame = cap.read()
                if not ret or frame is None:
                    print(f"[GPU BATCH] Failed to read frame from {camera_id}")
                    cap.release()
                    return False

                print(f"[GPU BATCH] Camera {camera_id} opened, frame size: {frame.shape}")

                # Load detector nếu chưa có
                if self.detector is None:
                    print("[GPU BATCH] Loading detector...")
                    self.detector = get_detector()
                    print("[GPU BATCH] Detector loaded")

                # Lưu camera info
                self.active_cameras[camera_id] = {
                    'cap': cap,
                    'url': rtsp_url,
                    'conf_threshold': conf_threshold,
                    'iou_threshold': iou_threshold,
                    'frame_count': 0,
                    'detection_count': 0,
                    'fps': cap.get(cv2.CAP_PROP_FPS) or 30
                }

                # Start camera thread
                camera_thread = threading.Thread(
                    target=self._camera_reader_loop,
                    args=(camera_id,),
                    daemon=True
                )
                camera_thread.start()
                self.camera_threads[camera_id] = camera_thread

                # Start GPU worker thread nếu chưa chạy
                if not self.running:
                    self.running = True

                    # Start GPU worker
                    self.gpu_worker_thread = threading.Thread(
                        target=self._gpu_worker_loop,
                        daemon=True
                    )
                    self.gpu_worker_thread.start()

                    # Start result worker
                    self.result_worker_thread = threading.Thread(
                        target=self._result_worker_loop,
                        daemon=True
                    )
                    self.result_worker_thread.start()

                    print("[GPU BATCH] GPU worker threads started")

                print(f"[GPU BATCH] Camera {camera_id} started successfully")
                return True

            except Exception as e:
                print(f"[GPU BATCH] Error starting camera {camera_id}: {e}")
                return False

    def stop_detection(self, camera_id: str) -> bool:
        """Stop detection cho 1 camera"""
        with self.lock:
            if camera_id not in self.active_cameras:
                return False

            # Release camera
            camera_info = self.active_cameras[camera_id]
            camera_info['cap'].release()

            # Remove from active cameras
            del self.active_cameras[camera_id]

            # Thread sẽ tự dừng khi không tìm thấy camera trong active_cameras
            if camera_id in self.camera_threads:
                del self.camera_threads[camera_id]

            print(f"[GPU BATCH] Camera {camera_id} stopped")

            # Stop worker threads nếu không còn camera nào
            if len(self.active_cameras) == 0:
                self.running = False
                print("[GPU BATCH] All cameras stopped, stopping workers")

            return True

    def stop_all(self):
        """Stop tất cả cameras"""
        with self.lock:
            camera_ids = list(self.active_cameras.keys())

        for camera_id in camera_ids:
            self.stop_detection(camera_id)

        self.running = False
        print("[GPU BATCH] All cameras stopped")

    def _camera_reader_loop(self, camera_id: str):
        """
        Camera reader thread - đọc frame từ camera và đưa vào queue
        Mỗi camera 1 thread riêng để tránh blocking
        """
        print(f"[GPU BATCH] Camera reader thread started for {camera_id}")

        while self.running:
            try:
                with self.lock:
                    if camera_id not in self.active_cameras:
                        break  # Camera đã bị stop

                    camera_info = self.active_cameras[camera_id]
                    cap = camera_info['cap']

                # Read frame (I/O operation - có thể mất vài ms)
                ret, frame = cap.read()

                if not ret or frame is None:
                    print(f"[GPU BATCH] Failed to read frame from {camera_id}")
                    time.sleep(0.1)
                    continue

                # Preprocess frame (resize) để giảm GPU workload
                original_h, original_w = frame.shape[:2]
                if max(original_h, original_w) > self.target_size:
                    scale = self.target_size / max(original_h, original_w)
                    new_w = int(original_w * scale)
                    new_h = int(original_h * scale)
                    resized_frame = cv2.resize(frame, (new_w, new_h))
                else:
                    resized_frame = frame
                    scale = 1.0

                # Update frame count
                with self.lock:
                    camera_info['frame_count'] += 1
                    frame_id = camera_info['frame_count']

                # Create frame job
                job = FrameJob(
                    camera_id=camera_id,
                    frame=resized_frame,
                    frame_id=frame_id,
                    timestamp=time.time(),
                    conf_threshold=camera_info['conf_threshold'],
                    iou_threshold=camera_info['iou_threshold']
                )

                # Push to queue (non-blocking)
                try:
                    self.frame_queue.put(job, block=False)
                except queue.Full:
                    # Queue full - skip frame (giảm latency)
                    print(f"[GPU BATCH] Frame queue full, skipping frame from {camera_id}")

                # Control frame rate (tránh overwhelm GPU)
                # Đọc frame theo FPS của camera
                time.sleep(1.0 / camera_info['fps'])

            except Exception as e:
                print(f"[GPU BATCH] Error in camera reader {camera_id}: {e}")
                time.sleep(0.1)

        print(f"[GPU BATCH] Camera reader thread stopped for {camera_id}")

    def _gpu_worker_loop(self):
        """
        GPU worker thread - lấy batch frames, chạy inference, trả kết quả
        Chỉ có 1 thread này để tận dụng GPU batch processing
        """
        print("[GPU BATCH] GPU worker thread started")

        batch_buffer = []
        last_inference_time = time.time()
        max_wait_time = 0.05  # 50ms timeout để tạo batch

        while self.running:
            try:
                # Collect frames into batch
                timeout_start = time.time()

                while len(batch_buffer) < self.batch_size:
                    # Timeout nếu chờ quá lâu (tránh latency cao khi có ít camera)
                    if time.time() - timeout_start > max_wait_time:
                        break

                    try:
                        job = self.frame_queue.get(timeout=0.01)
                        batch_buffer.append(job)
                    except queue.Empty:
                        break

                # Nếu không có frame nào, chờ tiếp
                if len(batch_buffer) == 0:
                    time.sleep(0.001)
                    continue

                # Run batch inference
                start_time = time.time()
                results = self._batch_inference(batch_buffer)
                inference_time = (time.time() - start_time) * 1000  # ms

                # Update statistics
                self.stats['total_frames'] += len(batch_buffer)
                self.stats['avg_batch_size'] = len(batch_buffer)
                self.stats['avg_inference_time_ms'] = inference_time

                # Push results to result queue
                for result in results:
                    try:
                        self.result_queue.put(result, block=False)
                    except queue.Full:
                        print("[GPU BATCH] Result queue full, dropping result")

                # Log performance
                fps = len(batch_buffer) / (inference_time / 1000)
                print(f"[GPU BATCH] Processed batch={len(batch_buffer)}, "
                      f"inference={inference_time:.1f}ms, "
                      f"throughput={fps:.1f} FPS")

                # Clear batch buffer
                batch_buffer.clear()
                last_inference_time = time.time()

            except Exception as e:
                print(f"[GPU BATCH] Error in GPU worker: {e}")
                batch_buffer.clear()
                time.sleep(0.1)

        print("[GPU BATCH] GPU worker thread stopped")

    def _batch_inference(self, jobs: List[FrameJob]) -> List[DetectionResult]:
        """
        Chạy batch inference trên GPU

        Args:
            jobs: List of frame jobs

        Returns:
            List of detection results
        """
        if len(jobs) == 0:
            return []

        try:
            # Extract frames
            frames = [job.frame for job in jobs]

            # Batch inference (YOLO tự động batch nếu truyền list frames)
            # Sử dụng conf và iou của frame đầu tiên (giả sử cùng settings)
            results = self.detector.model.predict(
                frames,
                conf=jobs[0].conf_threshold,
                iou=jobs[0].iou_threshold,
                device=self.device,
                verbose=False
            )

            # Process results
            detection_results = []

            for idx, (job, result) in enumerate(zip(jobs, results)):
                detections = []

                # Parse YOLO results
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())

                    # Convert to [x, y, w, h] format
                    w = int(x2 - x1)
                    h = int(y2 - y1)

                    detections.append({
                        'class': 'license_plate',
                        'confidence': confidence,
                        'bbox': [int(x1), int(y1), w, h],
                        'camera_id': job.camera_id,
                        'frame_id': job.frame_id,
                        'timestamp': job.timestamp
                    })

                # Update detection count
                if len(detections) > 0:
                    with self.lock:
                        if job.camera_id in self.active_cameras:
                            self.active_cameras[job.camera_id]['detection_count'] += len(detections)
                    self.stats['total_detections'] += len(detections)

                detection_results.append(DetectionResult(
                    camera_id=job.camera_id,
                    frame_id=job.frame_id,
                    timestamp=job.timestamp,
                    detections=detections
                ))

            return detection_results

        except RuntimeError as e:
            if "out of memory" in str(e):
                # GPU OOM - tự động giảm batch size
                print(f"[GPU BATCH] GPU OOM! Reducing batch size from {self.batch_size}")
                self.batch_size = max(1, self.batch_size - 1)
                torch.cuda.empty_cache()
                print(f"[GPU BATCH] New batch size: {self.batch_size}")
            raise

    def _result_worker_loop(self):
        """
        Result worker thread - broadcast kết quả qua WebSocket
        Tách riêng để không block GPU worker
        """
        print("[GPU BATCH] Result worker thread started")

        while self.running:
            try:
                # Get result from queue
                result = self.result_queue.get(timeout=0.1)

                # Broadcast via WebSocket
                if len(result.detections) > 0:
                    message = {
                        'detections': result.detections,
                        'camera_id': result.camera_id,
                        'frame_id': result.frame_id
                    }
                    self.websocket_manager.broadcast_detections(message)

                    print(f"[GPU BATCH] Camera {result.camera_id} - "
                          f"Frame {result.frame_id}: {len(result.detections)} detection(s)")

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[GPU BATCH] Error in result worker: {e}")

        print("[GPU BATCH] Result worker thread stopped")

    def get_stats(self) -> dict:
        """Get detection statistics"""
        with self.lock:
            camera_stats = {}
            for camera_id, camera_info in self.active_cameras.items():
                camera_stats[camera_id] = {
                    'url': camera_info['url'],
                    'frame_count': camera_info['frame_count'],
                    'detection_count': camera_info['detection_count'],
                    'conf_threshold': camera_info['conf_threshold'],
                    'iou_threshold': camera_info['iou_threshold']
                }

            return {
                'cameras': camera_stats,
                'global': {
                    'device': self.device,
                    'batch_size': self.batch_size,
                    'total_frames': self.stats['total_frames'],
                    'total_detections': self.stats['total_detections'],
                    'avg_batch_size': self.stats['avg_batch_size'],
                    'avg_inference_time_ms': self.stats['avg_inference_time_ms'],
                    'frame_queue_size': self.frame_queue.qsize(),
                    'result_queue_size': self.result_queue.qsize()
                }
            }
