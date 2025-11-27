"""
Detection Service - Chạy AI detection trong thread riêng
"""
import threading
import time
import numpy as np
from functools import lru_cache

import config


class Detection:
    """Detection object - Giống demo code"""
    def __init__(self, coords, category, conf, metadata, imx500, picam2):
        self.category = category
        self.conf = conf
        # Use IMX500 convert_inference_coords như demo code
        self.box = imx500.convert_inference_coords(coords, metadata, picam2)


class DetectionService:
    """Service chạy AI detection"""
    
    def __init__(self, camera_manager, websocket_manager, ocr_service=None):
        self.camera_manager = camera_manager
        self.websocket_manager = websocket_manager
        self.ocr_service = ocr_service
        
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
        self.last_ocr_results = {}  # Cache OCR results by bbox

        # Statistics for debugging
        self.outputs_success = 0
        self.outputs_fail = 0

        # VEHICLE TRACKING - tránh duplicate detections cho cùng 1 xe
        self.current_vehicle = None  # {'text': str, 'confidence': float, 'first_seen': time, 'last_seen': time, 'best_confidence': float}
        self.vehicle_timeout = 10.0  # Sau 10s không thấy xe, cho phép xe mới vào
        self.similarity_threshold = 0.7  # Nếu text giống > 70%, coi là cùng xe

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


                # Convert detections và run OCR nếu enabled
                detection_results = []
                frame = frame_data.get('frame')

                # Check xem frame này có chạy OCR không
                should_run_ocr = (self.total_frames % self.ocr_frame_skip == 0)

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

                    # Run OCR - CHỈ MỖI N FRAMES để giảm lag
                    if config.ENABLE_OCR and self.ocr_service and self.ocr_service.is_ready() and frame is not None:
                        # Tạo bbox key để cache
                        bbox_key = (x, y, w, h)

                        if should_run_ocr:
                            try:
                                # Validate bbox trong frame boundaries
                                frame_h, frame_w = frame.shape[:2]
                                x_valid = max(0, min(x, frame_w - 1))
                                y_valid = max(0, min(y, frame_h - 1))
                                w_valid = min(w, frame_w - x_valid)
                                h_valid = min(h, frame_h - y_valid)

                                # Crop detection region
                                if w_valid > 10 and h_valid > 10:  # Chỉ crop nếu đủ lớn
                                    crop = frame[y_valid:y_valid+h_valid, x_valid:x_valid+w_valid]

                                    if crop.size > 0:
                                        text = self.ocr_service.recognize(crop)
                                        if text:
                                            # LỌC PATTERN BIỂN SỐ VIỆT NAM
                                            if self._is_valid_vietnamese_plate(text):
                                                # VEHICLE TRACKING LOGIC
                                                is_new_vehicle = self._process_vehicle_detection(text, confidence, current_time)

                                                # Chỉ thêm text vào detection nếu là xe mới hoặc update xe hiện tại
                                                if is_new_vehicle or self.current_vehicle:
                                                    detection_dict['text'] = text
                                                    self.last_ocr_results[bbox_key] = text
                                            else:
                                                print(f"⚠️  Filtered invalid plate: '{text}'")
                            except Exception as e:
                                print(f"❌ OCR error: {e}")
                        else:
                            # Dùng cached result nếu có
                            if bbox_key in self.last_ocr_results:
                                detection_dict['text'] = self.last_ocr_results[bbox_key]

                    detection_results.append(detection_dict)

                if len(detection_results) > 0:
                    self.total_detections += len(detection_results)

                    # GỬI MỌI FRAME CÓ DETECTION (để boxes hiển thị liên tục)
                    self.websocket_manager.broadcast_detections(detection_results)

                    # Log được xử lý trong _process_vehicle_detection rồi, không cần log lại ở đây

                # Cleanup OCR cache mỗi 100 frames để tránh memory leak
                if self.total_frames % 100 == 0:
                    self.last_ocr_results.clear()

            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
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
                # Model có built-in postprocessing - THEO ĐÚNG DEMO CODE
                boxes = outputs[0][0]      # Shape: (300, 4)
                scores = outputs[1][0]     # Shape: (300,)
                classes = outputs[2][0]    # Shape: (300,)

                # Normalize ĐÚNG như demo code
                if self.intrinsics.bbox_normalization:
                    input_w, input_h = self.imx500.get_input_size()
                    boxes = boxes / input_h  # CHỈ chia cho HEIGHT

                # Swap bbox order ĐÚNG như demo code
                if self.intrinsics.bbox_order == "xy":
                    boxes = boxes[:, [1, 0, 3, 2]]  # Swap y↔x: (x,y,x,y) → (y,x,y,x)

                # Reshape ĐÚNG như demo code
                boxes = np.array_split(boxes, 4, axis=1)
                boxes = [arr.flatten() for arr in boxes]
                boxes = zip(*boxes)  # Generator, giống demo code

            # Filter by threshold và create Detection objects
            detections = []
            for box, score, category in zip(boxes, scores, classes):
                if score > config.DETECTION_THRESHOLD:
                    # DÙNG Detection class như demo code - convert_inference_coords() sẽ handle đúng!
                    detection = Detection(box, category, score, metadata, self.imx500, self.picam2)

                    # Get bbox đã được convert sang pixel coords
                    x, y, w, h = detection.box

                    # Calculate aspect ratio
                    aspect_ratio = w / h if h > 0 else 0

                    # Debug: Collect info
                    # Biển số Việt Nam: width/height thường 2.0 - 4.5
                    # Filter: chỉ accept boxes NẰM NGANG
                    if aspect_ratio > config.MIN_PLATE_ASPECT_RATIO:
                        detections.append(detection)

            return detections

        except Exception as e:
            # LUÔN log exception đầu tiên, sau đó mỗi 50 frames
            if not hasattr(self, '_parse_error_logged') or self.total_frames % 50 == 0:
                print(f"❌ Parse detection error: {e}")
                import traceback
                traceback.print_exc()
                self._parse_error_logged = True
            return []

    def _process_vehicle_detection(self, text, confidence, current_time):
        """
        Xử lý vehicle tracking - tránh duplicate detections

        Return: True nếu là xe mới (cần log/broadcast), False nếu là xe cũ
        """
        # Nếu không có xe nào đang track
        if self.current_vehicle is None:
            # Xe mới vào
            self.current_vehicle = {
                'text': text,
                'confidence': confidence,
                'first_seen': current_time,
                'last_seen': current_time,
                'best_confidence': confidence
            }
            print(f"🚗 NEW VEHICLE: {text} (confidence: {confidence:.2f})")
            return True

        # Đã có xe đang track
        time_since_last_seen = current_time - self.current_vehicle['last_seen']

        # Check timeout - nếu quá 10s không thấy xe, xe đã đi
        if time_since_last_seen > self.vehicle_timeout:
            # Xe cũ đã đi, xe mới vào
            print(f"⏱️  Vehicle timeout ({time_since_last_seen:.1f}s), accepting new vehicle")
            self.current_vehicle = {
                'text': text,
                'confidence': confidence,
                'first_seen': current_time,
                'last_seen': current_time,
                'best_confidence': confidence
            }
            print(f"🚗 NEW VEHICLE: {text} (confidence: {confidence:.2f})")
            return True

        # Xe vẫn trong view - check similarity
        similarity = self._levenshtein_similarity(text, self.current_vehicle['text'])

        if similarity >= self.similarity_threshold:
            # Cùng xe - update last_seen
            self.current_vehicle['last_seen'] = current_time

            # Update text nếu confidence cao hơn
            if confidence > self.current_vehicle['best_confidence']:
                old_text = self.current_vehicle['text']
                self.current_vehicle['text'] = text
                self.current_vehicle['confidence'] = confidence
                self.current_vehicle['best_confidence'] = confidence
                print(f"📝 UPDATE: {old_text} → {text} (confidence: {confidence:.2f}, similarity: {similarity:.2%})")
            else:
                # Confidence thấp hơn, giữ nguyên text cũ
                print(f"📌 KEEP: {self.current_vehicle['text']} (new reading: {text}, similarity: {similarity:.2%})")

            return False  # Không phải xe mới
        else:
            # Text khác xa (< 70% similar) - CHỜ THÊM ĐỂ CHẮC CHẮN
            # Có thể là: (1) OCR đọc sai hoặc (2) xe khác
            # Nếu đã thấy xe cũ trong vòng 5s gần đây, ignore reading mới (coi như OCR sai)
            time_in_view = current_time - self.current_vehicle['first_seen']

            if time_in_view < 5.0:
                # Xe mới vào chưa lâu, có thể OCR đang ổn định → ignore
                print(f"⚠️  IGNORE: {text} (similarity: {similarity:.2%} with {self.current_vehicle['text']}, vehicle still in view)")
                return False
            else:
                # Xe đã ở trong view > 5s, reading mới quá khác → có thể là xe mới
                # Accept như xe mới
                print(f"🔄 REPLACE: {self.current_vehicle['text']} → {text} (similarity: {similarity:.2%}, long time in view)")
                self.current_vehicle = {
                    'text': text,
                    'confidence': confidence,
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'best_confidence': confidence
                }
                return True

    def _levenshtein_similarity(self, s1, s2):
        """
        Tính similarity giữa 2 string bằng Levenshtein distance
        Return: 0.0 - 1.0 (1.0 = hoàn toàn giống)
        """
        if s1 == s2:
            return 1.0

        if len(s1) == 0 or len(s2) == 0:
            return 0.0

        # Levenshtein distance algorithm
        len1, len2 = len(s1), len(s2)
        distances = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            distances[i][0] = i
        for j in range(len2 + 1):
            distances[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                distances[i][j] = min(
                    distances[i-1][j] + 1,      # deletion
                    distances[i][j-1] + 1,      # insertion
                    distances[i-1][j-1] + cost  # substitution
                )

        # Convert distance to similarity (0-1)
        max_len = max(len1, len2)
        similarity = 1.0 - (distances[len1][len2] / max_len)
        return similarity

    def _is_valid_vietnamese_plate(self, text):
        """
        Kiểm tra text có phù hợp với format biển số Việt Nam không

        Formats hợp lệ:
        - 1 dòng: 29A12345, 51F98765 (2-3 số + 1 chữ + 4-5 số)
        - 2 dòng: 29A-12345, 51F-98765 (có dấu -)
        """
        import re

        if not text or len(text) < 6:
            return False

        # Remove spaces và uppercase
        text = text.strip().upper().replace(" ", "")

        # Pattern biển số VN:
        # - Bắt đầu: 2-3 chữ số (mã tỉnh)
        # - Theo sau: 1 chữ cái (A-Z, không có I, O, Q, W)
        # - Kết thúc: 4-5 chữ số
        # - Có thể có dấu - ở giữa (biển 2 dòng)

        patterns = [
            r'^\d{2}[A-HJ-NP-Z]\d{4,5}$',      # 29A12345
            r'^\d{2}[A-HJ-NP-Z]-?\d{4,5}$',    # 29A-12345
            r'^\d{3}[A-HJ-NP-Z]\d{4,5}$',      # 123A12345 (xe công vụ)
            r'^\d{3}[A-HJ-NP-Z]-?\d{4,5}$',    # 123A-12345
        ]

        for pattern in patterns:
            if re.match(pattern, text):
                return True

        return False

    @lru_cache
    def _get_labels(self):
        """Get labels"""
        labels = self.intrinsics.labels
        if self.intrinsics.ignore_dash_labels:
            labels = [label for label in labels if label and label != "-"]
        return labels