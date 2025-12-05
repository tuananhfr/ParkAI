"""
Detection Service - Chạy AI detection trong thread riêng
"""
import threading
import time
import numpy as np
from functools import lru_cache

import config
from plate_tracker import get_plate_tracker


class Detection:
    """Detection object - Giống demo code"""
    def __init__(self, coords, category, conf, metadata, imx500, picam2):
        self.category = category
        self.conf = conf
        # Use IMX500 convert_inference_coords như demo code
        self.box = imx500.convert_inference_coords(coords, metadata, picam2)


class DetectionService:
    """Service chạy AI detection"""

    def __init__(self, camera_manager, websocket_manager, ocr_service=None, central_sync=None, barrier_controller=None, parking_manager=None):
        self.camera_manager = camera_manager
        self.websocket_manager = websocket_manager
        self.ocr_service = ocr_service
        self.central_sync = central_sync  # Central sync service để gửi ảnh
        self.barrier_controller = barrier_controller  # Barrier controller để mở/đóng
        self.parking_manager = parking_manager  # Parking manager để process entry

        self.intrinsics = camera_manager.get_intrinsics()
        self.imx500 = camera_manager.get_imx500()
        self.picam2 = camera_manager.get_picam2()

        self.running = False
        self.detection_thread = None

        # Stats
        self.total_detections = 0
        self.total_frames = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.frames_in_second = 0

        # OCR throttling - chỉ chạy mỗi N frames
        self.ocr_frame_skip = config.OCR_FRAME_SKIP

        # Plate tracker - Vote cho plate chính xác nhất
        self.plate_tracker = get_plate_tracker()

        # ĐƠN GIẢN: CHỈ CAPTURE VÀ OCR 
        # Capture ảnh tĩnh khi confidence cao, OCR trên ảnh đã capture
        self.captured_frame_full = None      # Full crop chưa preprocess (để gửi frontend)
        self.capture_timestamp = None        # Thời điểm capture
        self.is_processing = False           # Đang xử lý plate đã capture
        self.ocr_attempts = 0                # Số lần đã chạy OCR trên capture
        self.last_processed_time = 0         # Thời điểm xử lý xong (cooldown)
        self.captured_bbox = None            # Bbox của plate đã capture
        self.processed_plates = {}           # {plate_id: timestamp} - Track plates đã process trong 15s

        # Statistics for debugging
        self.outputs_success = 0
        self.outputs_fail = 0

    def start(self):
        """Bắt đầu detection thread"""
        if self.running:
            return
        
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
    
    def stop(self):
        """Dừng detection"""
        self.running = False

        if self.detection_thread:
            self.detection_thread.join(timeout=2)


    def _detection_loop(self):
        """Loop detection - TẬN DỤNG IMX500, CHỈ PARSE METADATA"""

        while self.running:
            try:
                frame_data = self.camera_manager.get_frame_for_detection()

                if frame_data is None:
                    continue

                # OPTIMIZATION: Không cần frame - IMX500 đã có bbox trong metadata
                metadata = frame_data['metadata']
                timestamp = frame_data['timestamp']
                frame_id = frame_data['frame_id']
                cached_outputs = frame_data.get('outputs')  # Get cached outputs (nếu có)

                # Parse detections từ IMX500 metadata (đã có bbox sẵn)
                detections = self._parse_detections(metadata, cached_outputs)

                # Update stats
                self.total_frames += 1
                self.frames_in_second += 1
                current_time = time.time()

                if current_time - self.last_fps_time >= 1.0:
                    self.fps = self.frames_in_second
                    self.frames_in_second = 0
                    self.last_fps_time = current_time


                # TRIGGER-BASED PROCESSING 
                # Chỉ capture và OCR khi confidence cao, không chạy OCR liên tục

                # Check timeout/cooldown để reset state
                current_time = time.time()

                # Check timeout: Nếu đang processing quá lâu (> CAPTURE_TIMEOUT) → Reset
                if (self.is_processing and 
                    self.capture_timestamp is not None and
                    current_time - self.capture_timestamp > config.CAPTURE_TIMEOUT):
                    self.last_processed_time = current_time
                    self._reset_capture_state()

                # Convert detections
                detection_results = []
                frame = frame_data.get('frame')

                for detection in detections:
                    # Detection object có .box (x, y, w, h) format
                    x, y, w, h = detection.box
                    category_idx = int(detection.category)
                    confidence = float(detection.conf)

                    labels = self._get_labels()
                    label = labels[category_idx] if category_idx < len(labels) else f"Class_{category_idx}"

                    detection_dict = {
                        'class': label,
                        'confidence': confidence,
                        'bbox': [int(x), int(y), int(w), int(h)],
                        'timestamp': timestamp,
                        'frame_id': frame_id
                    }

                    #== CAPTURE LOGIC: Capture ảnh khi confidence CAO ==
                    # Chỉ capture KHI:
                    # 1. KHÔNG đang xử lý plate khác
                    # 2. Confidence >= CAPTURE_CONFIDENCE_THRESHOLD
                    # 3. Đã qua cooldown (2s sau lần xử lý trước)

                    bbox = (x, y, w, h)

                    # Check cooldown
                    cooldown_ok = (current_time - self.last_processed_time >= config.CAPTURE_COOLDOWN)
                    

                    # Chỉ capture nếu:
                    # 1. Không đang xử lý plate khác
                    # 2. Đã qua cooldown
                    if (not self.is_processing and
                        cooldown_ok and
                        confidence >= config.CAPTURE_CONFIDENCE_THRESHOLD and
                        frame is not None):

                        try:
                            import cv2
                            import base64

                            # Validate bbox
                            frame_h, frame_w = frame.shape[:2]
                            x_valid = max(0, min(x, frame_w - 1))
                            y_valid = max(0, min(y, frame_h - 1))
                            w_valid = min(w, frame_w - x_valid)
                            h_valid = min(h, frame_h - y_valid)

                            # Crop detection region
                            if w_valid > 10 and h_valid > 10:
                                crop = frame[y_valid:y_valid+h_valid, x_valid:x_valid+w_valid]

                                if crop.size > 0:
                                    # CAPTURE! Lưu ảnh để xử lý
                                    self.captured_frame_full = crop.copy()  # RAW crop (gửi frontend)
                                    self.captured_bbox = bbox
                                    self.capture_timestamp = current_time
                                    self.is_processing = True
                                    self.ocr_attempts = 0

                                    # FLOW MỚI: GỬI ẢNH NGAY (chưa có text) 
                                    # BƯỚC 1: Encode và gửi ảnh về frontend NGAY (chưa OCR)
                                    _, buffer = cv2.imencode('.jpg', crop)
                                    crop_base64 = base64.b64encode(buffer).decode('utf-8')

                                    # Gửi ảnh TRƯỚC (chưa có text)
                                    image_only_result = {
                                        'class': 'license_plate',
                                        'confidence': confidence,
                                        'bbox': [int(x), int(y), int(w), int(h)],
                                        'plate_image': f"data:image/jpeg;base64,{crop_base64}",
                                        'ocr_status': 'processing',  # ← Đang OCR
                                        'timestamp': timestamp,
                                        'frame_id': frame_id
                                    }
                                    self.websocket_manager.broadcast_detections([image_only_result])

                        except Exception as e:
                            pass

                    # LUÔN ADD detection vào results
                    detection_results.append(detection_dict)

                #== OCR ON CAPTURED FRAME (TRIGGER-BASED) ==
                # Chỉ chạy OCR trên ảnh đã CAPTURE, KHÔNG chạy mỗi frame!

                if (self.is_processing and
                    self.captured_frame_full is not None and
                    self.ocr_attempts < config.MAX_OCR_ATTEMPTS and
                    config.ENABLE_OCR and
                    self.ocr_service and
                    self.ocr_service.is_ready()):

                    try:
                        import cv2

                        # Lấy crop đã capture
                        crop = self.captured_frame_full.copy()
                        h, w = crop.shape[:2]

                        # Preprocessing
                        # 1. Resize nếu quá nhỏ
                        if h < 60:
                            scale = 60 / h
                            new_w = int(w * scale)
                            crop = cv2.resize(crop, (new_w, 60), interpolation=cv2.INTER_CUBIC)

                        # 2. Denoise
                        crop = cv2.fastNlMeansDenoisingColored(crop, None, 10, 10, 7, 21)

                        # 3. CLAHE
                        lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB)
                        l, a, b = cv2.split(lab)
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                        l = clahe.apply(l)
                        crop = cv2.cvtColor(cv2.merge([l,a,b]), cv2.COLOR_LAB2RGB)

                        # OCR
                        self.ocr_attempts += 1
                        text = self.ocr_service.recognize(crop)

                        if text and self._is_valid_vietnamese_plate(text):
                            # OCR thành công!

                            # FLOW ĐƠN GIẢN: GỬI TEXT SAU KHI OCR XONG 
                            # BƯỚC 2: Gửi TEXT sau khi OCR xong (ảnh đã gửi ở BƯỚC 1)

                            # BƯỚC 3: CHECK BIỂN SỐ CÓ TRONG GARA CHƯA
                            validation_result = self._validate_plate_for_gate(text)

                            text_result = {
                                'class': 'license_plate',
                                'confidence': 0.95,  # High confidence vì đã capture tốt
                                'bbox': list(self.captured_bbox),
                                'text': text,
                                'finalized': True,
                                'ocr_status': 'success',  # ← OCR thành công
                                'validation_status': validation_result['status'],  # 'valid' | 'invalid'
                                'validation_message': validation_result.get('message', ''),
                                'timestamp': time.time(),
                                'frame_id': frame_id
                            }

                            # Gửi TEXT qua WebSocket (ảnh đã gửi trước đó)
                            self.websocket_manager.broadcast_detections([text_result])
                            

                            # Deduplication - Đã process plate này trong 15s gần đây chưa?
                            import re
                            plate_normalized = re.sub(r'[^A-Z0-9]', '', text.upper())
                            current_time_check = time.time()

                            # Clean expired entries
                            expired = [p for p, t in self.processed_plates.items() if current_time_check - t > 15.0]
                            for p in expired:
                                del self.processed_plates[p]

                            # Check duplicate
                            if plate_normalized in self.processed_plates:
                                self.ocr_attempts = config.MAX_OCR_ATTEMPTS
                                continue

                            # Mark as processed
                            self.processed_plates[plate_normalized] = current_time_check

                            # Reset state để sẵn sàng cho plate tiếp theo
                            self.last_processed_time = current_time_check
                            self._reset_capture_state()

                        else:
                            # OCR không hợp lệ

                            # Nếu đã hết attempts → OCR FAIL → Reset ngay (không mở barrier)
                            if self.ocr_attempts >= config.MAX_OCR_ATTEMPTS:
                                self.last_processed_time = current_time
                                self._reset_capture_state()

                    except Exception as e:
                        # Reset nếu lỗi (OCR error)
                        self.last_processed_time = current_time
                        self._reset_capture_state()

                if len(detection_results) > 0:
                    self.total_detections += len(detection_results)

                    # GỬI MỌI FRAME CÓ DETECTION (để boxes hiển thị liên tục)
                    self.websocket_manager.broadcast_detections(detection_results)

            except Exception as e:
                time.sleep(0.1)

    def _parse_detections(self, metadata, cached_outputs=None):
        """Parse detections từ IMX500 - Giống logic demo code"""
        try:
            # Use cached outputs từ camera_manager (nếu có) để tránh gọi get_outputs 2 lần
            if cached_outputs is not None:
                outputs = cached_outputs
            else:
                # Fallback: extract từ metadata (legacy path)
                outputs = self.imx500.get_outputs(metadata, add_batch=True)

            # Track statistics
            if outputs is None or len(outputs) < 3:
                self.outputs_fail += 1
                return []

            # Success
            self.outputs_success += 1

            # Check if model has postprocess built-in
            if self.intrinsics.postprocess == "nanodet":
                # Use nanodet postprocessing (như demo code)
                from picamera2.devices.imx500 import postprocess_nanodet_detection
                from picamera2.devices.imx500.postprocess import scale_boxes

                input_w, input_h = self.imx500.get_input_size()
                boxes, scores, classes = postprocess_nanodet_detection(
                    outputs=outputs[0],
                    conf=config.DETECTION_THRESHOLD,
                    iou_thres=config.IOU_THRESHOLD,
                    max_out_dets=config.MAX_DETECTIONS
                )[0]
                boxes = scale_boxes(boxes, 1, 1, input_h, input_w, False, False)
            else:
                # Model có built-in postprocessing - THEO DEMO CODE
                boxes, scores, classes = outputs[0][0], outputs[1][0], outputs[2][0]

                # Normalize boxes
                if self.intrinsics.bbox_normalization:
                    input_w, input_h = self.imx500.get_input_size()
                    boxes = boxes / input_h

                # Swap bbox order if needed
                if self.intrinsics.bbox_order == "xy":
                    boxes = boxes[:, [1, 0, 3, 2]]

                # Reshape - ĐÚNG NHƯ DEMO (không có flatten!)
                boxes = np.array_split(boxes, 4, axis=1)
                boxes = zip(*boxes)

            # Filter by threshold và create Detection objects
            detections = []
            raw_count = 0
            filtered_count = 0

            for box, score, category in zip(boxes, scores, classes):
                if score > config.DETECTION_THRESHOLD:
                    raw_count += 1

                    # DÙNG Detection class như demo code - convert_inference_coords() sẽ handle đúng!
                    detection = Detection(box, category, score, metadata, self.imx500, self.picam2)

                    # Get bbox đã được convert sang pixel coords
                    x, y, w, h = detection.box

                    # Calculate aspect ratio
                    aspect_ratio = w / h if h > 0 else 0

                    # Biển số Việt Nam: width/height thường 2.0 - 4.5
                    # Filter: chỉ accept boxes NẰM NGANG
                    if aspect_ratio > config.MIN_PLATE_ASPECT_RATIO:
                        detections.append(detection)
                        filtered_count += 1


            return detections

        except Exception as e:
            # LUÔN log exception đầu tiên, sau đó mỗi 50 frames
            if not hasattr(self, '_parse_error_logged') or self.total_frames % 50 == 0:
                self._parse_error_logged = True
            return []

    def _is_valid_vietnamese_plate(self, text):
        """
        Kiểm tra text có phù hợp với format biển số Việt Nam không

        Formats hợp lệ:
        - 1 dòng: 29A12345, 51F98765 (2-3 số + 1 chữ + 4-5 số)
        - 2 dòng: 29A-12345, 51F-98765 (có dấu -)
        - Biển xe máy: 29A112345

        CHÚ Ý: Cho phép cả dấu . (chấm) vì OCR có thể đọc nhầm
        Ví dụ: "29A-179.90" → normalize → "29A17990" → valid
        """
        import re

        if not text or len(text) < 7:  # Tối thiểu 7 ký tự
            return False

        # Clean text - BỎ TẤT CẢ KÝ TỰ ĐẶC BIỆT (giữ số + chữ + dấu -)
        clean = text.strip().upper().replace(" ", "").replace(".", "")

        # Patterns biển số VN - ACCEPT 1-2 CHỮ
        patterns = [
            # Xe ô tô (2 số + 1-2 chữ + 4-6 số)
            r'^\d{2}[A-Z]{1,2}\d{4,6}$',           # 29A12345, 29AB12345
            r'^\d{2}[A-Z]{1,2}-\d{4,6}$',          # 29A-12345, 29AB-12345

            # Xe công vụ (3 số + 1-2 chữ + 4-6 số)
            r'^\d{3}[A-Z]{1,2}\d{4,6}$',           # 123A12345, 123AB12345
            r'^\d{3}[A-Z]{1,2}-\d{4,6}$',          # 123A-12345

            # Xe máy có format đặc biệt (29A1-12345)
            r'^\d{2}[A-Z]\d-?\d{4,5}$',            # 29A112345, 29A1-12345
        ]

        for pattern in patterns:
            if re.match(pattern, clean):
                return True

        # Kiểm tra tỷ lệ số/chữ hợp lý
        digits = sum(c.isdigit() for c in clean)
        letters = sum(c.isalpha() for c in clean)

        # Biển số VN: 70-90% là số, 10-30% là chữ (accept 1-3 chữ)
        if len(clean) >= 7 and digits >= 5 and 1 <= letters <= 3:
            return True

        return False

    def _reset_capture_state(self):
        """Reset capture state để chờ plate tiếp theo"""
        self.captured_frame_full = None
        self.capture_timestamp = None
        self.is_processing = False
        self.ocr_attempts = 0
        self.captured_bbox = None


    def _validate_plate_for_gate(self, plate_text):
        """
        Validate biển số cho cổng VÀO/RA
        
        Logic:
        - Cổng VÀO (ENTRY): Xe chưa có trong gara → valid, đã có → invalid
        - Cổng RA (EXIT): Xe đã có trong gara → valid, chưa có → invalid
        
        Returns:
            {
                'status': 'valid' | 'invalid',
                'message': 'Error message nếu invalid'
            }
        """
        if not self.parking_manager:
            return {'status': 'valid', 'message': ''}
        
        import config
        import re
        
        # Validate và normalize plate
        plate_id, display_text = self.parking_manager.validate_plate(plate_text)
        if not plate_id:
            return {
                'status': 'invalid',
                'message': f'Biển số không hợp lệ: {plate_text}'
            }
        
        # Check trong DB
        existing = self.parking_manager.db.find_entry_in(plate_id)
        
        if config.CAMERA_TYPE == "ENTRY":
            # Cổng VÀO: Xe chưa có trong gara → valid
            if existing:
                return {
                    'status': 'invalid',
                    'message': f'Xe {display_text} đã VÀO lúc {existing["entry_time"]} tại {existing["entry_camera_name"]}'
                }
            else:
                return {'status': 'valid', 'message': ''}
        
        elif config.CAMERA_TYPE == "EXIT":
            # Cổng RA: Xe đã có trong gara → valid
            if existing:
                return {'status': 'valid', 'message': ''}
            else:
                return {
                    'status': 'invalid',
                    'message': f'Xe {display_text} không có trong gara!'
                }
        
        return {'status': 'valid', 'message': ''}

    @lru_cache
    def _get_labels(self):
        """Get labels"""
        labels = self.intrinsics.labels
        if self.intrinsics.ignore_dash_labels:
            labels = [label for label in labels if label and label != "-"]
        return labels