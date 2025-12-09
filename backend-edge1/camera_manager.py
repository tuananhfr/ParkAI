"""
Camera Manager - Quản lý camera capture
"""
import threading
import time
from queue import Queue, Empty
import numpy as np
import cv2
from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import NetworkIntrinsics

import config


class CameraManager:
    """Quản lý camera capture trong thread riêng"""
    
    def __init__(self, model_path, labels_path=None):
        # Load IMX500
        self.imx500 = IMX500(model_path)
        self.intrinsics = self.imx500.network_intrinsics
        
        if not self.intrinsics:
            self.intrinsics = NetworkIntrinsics()
            self.intrinsics.task = "object detection"
        
        # Load labels
        if labels_path:
            with open(labels_path, 'r') as f:
                self.intrinsics.labels = f.read().splitlines()
        
        # Set intrinsics - MATCH voi demo code args
        self.intrinsics.bbox_normalization = True
        self.intrinsics.ignore_dash_labels = True
        self.intrinsics.bbox_order = "xy"
        # Set postprocess neu model can (check model type)
        # Neu model KHONG co built-in postprocessing thi set "nanodet"
        # Neu co built-in thi de None hoac ""
        if not hasattr(self.intrinsics, 'postprocess') or self.intrinsics.postprocess is None:
            self.intrinsics.postprocess = ""  # Model có built-in postprocessing
        self.intrinsics.update_with_defaults()

        # Initialize camera
        self.picam2 = Picamera2(self.imx500.camera_num)
        
        camera_config = self.picam2.create_video_configuration(
            main={
                "size": (config.RESOLUTION_WIDTH, config.RESOLUTION_HEIGHT),
                "format": "RGB888"
            },
            controls={"FrameRate": config.CAMERA_FPS},
            buffer_count=4
        )
        
        self.picam2.configure(camera_config)
        
        self.imx500.show_network_fw_progress_bar()
        
        self.picam2.start()
        
        if self.intrinsics.preserve_aspect_ratio:
            self.imx500.set_auto_aspect_ratio()
        
        # Frame queue cho detection service
        self.frame_queue = Queue(maxsize=config.MAX_FRAME_QUEUE_SIZE)

        # Raw frame queue cho WebRTC (khong co detections)
        self.raw_frame_queue = Queue(maxsize=config.MAX_FRAME_QUEUE_SIZE)

        # Annotated frame queue cho WebRTC (CO boxes ve san tu backend)
        self.annotated_frame_queue = Queue(maxsize=config.MAX_FRAME_QUEUE_SIZE)

        # Control
        self.running = False
        self.capture_thread = None
        
        time.sleep(1)
    
    def start(self):
        """Bắt đầu capture thread"""
        if self.running:
            return
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def stop(self):
        """Dừng capture"""
        self.running = False
        
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
        
    
    def _capture_loop(self):
        """Loop capture - TẬN DỤNG IMX500, GIẢM CPU"""
        frame_count = 0
        detection_frame_skip = config.CAMERA_FPS // config.DETECTION_FPS

        while self.running:
            try:
                frame_count += 1

                # === OPTIMIZATION 1: Capture metadata + frame cung luc ===
                # IMX500 da run inference, metadata co san bbox
                request = self.picam2.capture_request()

                try:
                    # Lay frame tu request (zero-copy neu possible)
                    frame = request.make_array("main")
                    metadata = request.get_metadata()

                    if frame is None:
                        continue

                    # === OPTIMIZATION 2: Raw frame cho WebRTC (NO COPY neu duoc) ===
                    # Chi copy khi queue day can drop
                    if not self.raw_frame_queue.full():
                        self.raw_frame_queue.put_nowait(frame)  # No copy!
                    else:
                        # Drop old frame
                        try:
                            self.raw_frame_queue.get_nowait()
                            self.raw_frame_queue.put_nowait(frame)
                        except:
                            pass

                    # === OPTIMIZATION 3: Detection + OCR ===
                    # CHI gui frames CO IMX500 outputs (de tranh 50% frames = None)
                    # Pre-extract outputs de cache (tranh goi get_outputs 2 lan)
                    outputs = None
                    try:
                        outputs = self.imx500.get_outputs(metadata, add_batch=True)
                    except:
                        pass

                    has_outputs = outputs is not None and len(outputs) >= 3

                    # GUI TAT CA frames co outputs (bo frame_skip de tranh miss detections)
                    # IMX500 tu throttle ~15 FPS inference, nen tu nhien se co ~15 FPS outputs
                    if has_outputs:
                        frame_for_ocr = frame.copy() if config.ENABLE_OCR else None

                        frame_data = {
                            'frame': frame_for_ocr,
                            'metadata': metadata,
                            'outputs': outputs,  # Cache outputs để detection_service không cần gọi lại
                            'timestamp': time.time(),
                            'frame_id': frame_count
                        }

                        if not self.frame_queue.full():
                            self.frame_queue.put_nowait(frame_data)
                        else:
                            # Drop old detection
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put_nowait(frame_data)
                            except:
                                pass

                        # VE BOXES LEN FRAME cho annotated video (DEBUG)
                        annotated_frame = self._draw_boxes(frame.copy(), outputs, metadata)

                        if not self.annotated_frame_queue.full():
                            self.annotated_frame_queue.put_nowait(annotated_frame)
                        else:
                            # Drop old frame
                            try:
                                self.annotated_frame_queue.get_nowait()
                                self.annotated_frame_queue.put_nowait(annotated_frame)
                            except:
                                pass

                finally:
                    # Release request de free memory
                    request.release()

            except Exception as e:
                print(f"Capture error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.001)
    
    def get_raw_frame(self):
        """Lấy raw frame cho WebRTC"""
        try:
            return self.raw_frame_queue.get(timeout=1.0)
        except Empty:
            return None
    
    def get_frame_for_detection(self):
        """Lấy frame cho detection service"""
        try:
            return self.frame_queue.get(timeout=1.0)
        except Empty:
            return None

    def get_annotated_frame(self):
        """Lấy annotated frame (đã vẽ boxes) cho WebRTC"""
        try:
            return self.annotated_frame_queue.get(timeout=1.0)
        except Empty:
            return None

    def get_intrinsics(self):
        """Get intrinsics"""
        return self.intrinsics
    
    def get_imx500(self):
        """Get IMX500 instance"""
        return self.imx500
    
    def get_picam2(self):
        """Get Picamera2 instance"""
        return self.picam2

    def _draw_boxes(self, frame, outputs, metadata):
        """Vẽ boxes lên frame cho DEBUG - Tự động vẽ ĐÚNG"""
        try:
            if outputs is None or len(outputs) < 3:
                return frame

            # Parse giong detection_service - THEO DEMO CODE
            boxes = outputs[0][0]      # Shape: (300, 4)
            scores = outputs[1][0]     # Shape: (300,)
            classes = outputs[2][0]    # Shape: (300,)

            # Normalize DUNG nhu demo code
            if self.intrinsics.bbox_normalization:
                input_w, input_h = self.imx500.get_input_size()
                boxes = boxes / input_h

            # Swap bbox order DUNG nhu demo code
            if self.intrinsics.bbox_order == "xy":
                boxes = boxes[:, [1, 0, 3, 2]]

            # Reshape boxes
            boxes = np.array_split(boxes, 4, axis=1)
            boxes = [arr.flatten() for arr in boxes]
            boxes = zip(*boxes)

            # Ve boxes len frame - DUNG Detection class de convert
            for box, score, category in zip(boxes, scores, classes):
                if score > config.DETECTION_THRESHOLD:
                    # Dung Detection class nhu demo code
                    from detection_service import Detection
                    detection = Detection(box, category, score, metadata, self.imx500, self.picam2)
                    x, y, w, h = detection.box

                    # FILTER: Chi ve boxes NAM NGANG
                    aspect_ratio = w / h if h > 0 else 0
                    if aspect_ratio <= config.MIN_PLATE_ASPECT_RATIO:
                        continue  # Skip boxes nam doc

                    # Ve rectangle (mau xanh = ACCEPTED)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Ve text (confidence + aspect ratio)
                    label = f"{score:.2f} | {aspect_ratio:.1f}:1"
                    cv2.putText(frame, label, (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            return frame

        except Exception as e:
            print(f"Draw boxes error: {e}")
            return frame