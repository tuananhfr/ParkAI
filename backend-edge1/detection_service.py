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
        # Use IMX500 convert_inference_coords nhu demo code
        self.box = imx500.convert_inference_coords(coords, metadata, picam2)


class DetectionService:
    """Service chạy AI detection"""

    def __init__(self, camera_manager, websocket_manager, ocr_service=None, central_sync=None, parking_manager=None):
        self.camera_manager = camera_manager
        self.websocket_manager = websocket_manager
        self.ocr_service = ocr_service
        self.central_sync = central_sync  # Central sync service de gui len central
        self.parking_manager = parking_manager  # Parking manager de process entry tu dong

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

        # OCR throttling - chi chay moi N frames
        self.ocr_frame_skip = config.OCR_FRAME_SKIP

        # Plate tracker - Vote cho plate chinh xac nhat
        self.plate_tracker = get_plate_tracker()

        # DON GIAN: CHI CAPTURE VA OCR
        # Capture anh tinh khi confidence cao, OCR tren anh da capture
        self.captured_frame_full = None      # Full crop chua preprocess (de gui frontend)
        self.capture_timestamp = None        # Thoi diem capture
        self.is_processing = False           # Dang xu ly plate da capture
        self.ocr_attempts = 0                # So lan da chay OCR tren capture
        self.last_processed_time = 0         # Thoi diem xu ly xong (cooldown)
        self.captured_bbox = None            # Bbox cua plate da capture
        self.processed_plates = {}           # {plate_id: timestamp} - Track plates da process trong 15s

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

                # OPTIMIZATION: Khong can frame - IMX500 da co bbox trong metadata
                metadata = frame_data['metadata']
                timestamp = frame_data['timestamp']
                frame_id = frame_data['frame_id']
                cached_outputs = frame_data.get('outputs')  # Get cached outputs (nếu có)

                # Parse detections tu IMX500 metadata (da co bbox san)
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
                # Chi capture va OCR khi confidence cao, khong chay OCR lien tuc

                # Check timeout/cooldown de reset state
                current_time = time.time()

                # Check timeout: Neu dang processing qua lau (> CAPTURE_TIMEOUT) → Reset
                if (self.is_processing and 
                    self.capture_timestamp is not None and
                    current_time - self.capture_timestamp > config.CAPTURE_TIMEOUT):
                    self.last_processed_time = current_time
                    self._reset_capture_state()

                # Convert detections
                detection_results = []
                frame = frame_data.get('frame')

                for detection in detections:
                    # Detection object co .box (x, y, w, h) format
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

                    # == CAPTURE LOGIC: Capture anh khi confidence CAO ==
                    # Chi capture KHI:
                    # 1. KHONG dang xu ly plate khac
                    # 2. Confidence >= CAPTURE_CONFIDENCE_THRESHOLD
                    # 3. Da qua cooldown (2s sau lan xu ly truoc)

                    bbox = (x, y, w, h)

                    # Check cooldown
                    cooldown_ok = (current_time - self.last_processed_time >= config.CAPTURE_COOLDOWN)
                    

                    # Chi capture neu:
                    # 1. Khong dang xu ly plate khac
                    # 2. Da qua cooldown
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
                                    # CAPTURE! Luu anh de xu ly
                                    self.captured_frame_full = crop.copy()  # RAW crop (gui frontend)
                                    self.captured_bbox = bbox
                                    self.capture_timestamp = current_time
                                    self.is_processing = True
                                    self.ocr_attempts = 0

                                    # FLOW MOI: GUI ANH NGAY (chua co text)
                                    # BUOC 1: Encode va gui anh ve frontend NGAY (chua OCR)
                                    _, buffer = cv2.imencode('.jpg', crop)
                                    crop_base64 = base64.b64encode(buffer).decode('utf-8')

                                    # Gui anh TRUOC (chua co text)
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

                    # LUON ADD detection vao results
                    detection_results.append(detection_dict)

                # == OCR ON CAPTURED FRAME (TRIGGER-BASED) ==
                # Chi chay OCR tren anh da CAPTURE, KHONG chay moi frame!

                if (self.is_processing and
                    self.captured_frame_full is not None and
                    self.ocr_attempts < config.MAX_OCR_ATTEMPTS and
                    config.ENABLE_OCR and
                    self.ocr_service and
                    self.ocr_service.is_ready()):

                    try:
                        import cv2

                        # Lay crop da capture
                        crop = self.captured_frame_full.copy()
                        h, w = crop.shape[:2]

                        # Preprocessing
                        # 1. Resize neu qua nho
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
                            # OCR thanh cong!

                            # BUOC 1: CHECK BIEN SO CO TRONG GARA CHUA
                            validation_result = self._validate_plate_for_gate(text)

                            # Deduplication - Da process plate nay trong 15s gan day chua?
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

                            # BUOC 2: TU DONG LUU DB NEU VALID
                            entry_saved = False
                            entry_result = None

                            if validation_result['status'] == 'valid' and self.parking_manager:
                                # Luu vao DB ngay (khong can barrier)
                                entry_result = self.parking_manager.process_entry(
                                    plate_text=text,
                                    camera_id=config.CAMERA_ID,
                                    camera_type=config.CAMERA_TYPE,
                                    camera_name=config.CAMERA_NAME,
                                    confidence=0.95,
                                    source='auto'
                                )

                                if entry_result.get('success'):
                                    entry_saved = True
                                    print(f"Auto saved: {text} - {entry_result.get('message')}")

                                    # Sync to Central (neu co)
                                    if self.central_sync:
                                        event_type = "ENTRY" if config.CAMERA_TYPE == "ENTRY" else "EXIT"
                                        sync_data = {
                                            "plate_text": text,
                                            "confidence": 0.95,
                                            "source": "auto",
                                            "entry_id": entry_result.get('entry_id')
                                        }

                                        # Them thong tin cho EXIT
                                        if event_type == "EXIT":
                                            if entry_result.get('entry_time'):
                                                sync_data['entry_time'] = entry_result.get('entry_time')
                                            if entry_result.get('duration'):
                                                sync_data['duration'] = entry_result.get('duration')
                                            if entry_result.get('fee') is not None:
                                                sync_data['fee'] = entry_result.get('fee')

                                        self.central_sync.send_event(event_type, sync_data)

                            # BUOC 3: GUI KET QUA QUA WEBSOCKET
                            text_result = {
                                'class': 'license_plate',
                                'confidence': 0.95,
                                'bbox': list(self.captured_bbox),
                                'text': text,
                                'finalized': True,
                                'ocr_status': 'success',
                                'validation_status': validation_result['status'],
                                'validation_message': validation_result.get('message', ''),
                                'entry_saved': entry_saved,  # Flag: đã lưu DB chưa
                                'entry_result': entry_result,  # Kết quả lưu DB (nếu có)
                                'timestamp': time.time(),
                                'frame_id': frame_id
                            }

                            # Gui TEXT qua WebSocket
                            self.websocket_manager.broadcast_detections([text_result])

                            # Reset state de san sang cho plate tiep theo
                            self.last_processed_time = current_time_check
                            self._reset_capture_state()

                        else:
                            # OCR khong hop le

                            # Neu da het attempts → OCR FAIL → Reset ngay (khong mo barrier)
                            if self.ocr_attempts >= config.MAX_OCR_ATTEMPTS:
                                self.last_processed_time = current_time
                                self._reset_capture_state()

                    except Exception as e:
                        # Reset neu loi (OCR error)
                        self.last_processed_time = current_time
                        self._reset_capture_state()

                if len(detection_results) > 0:
                    self.total_detections += len(detection_results)

                    # GUI MOI FRAME CO DETECTION (de boxes hien thi lien tuc)
                    self.websocket_manager.broadcast_detections(detection_results)

            except Exception as e:
                time.sleep(0.1)

    def _parse_detections(self, metadata, cached_outputs=None):
        """Parse detections từ IMX500 - Giống logic demo code"""
        try:
            # Use cached outputs tu camera_manager (neu co) de tranh goi get_outputs 2 lan
            if cached_outputs is not None:
                outputs = cached_outputs
            else:
                # Fallback: extract tu metadata (legacy path)
                outputs = self.imx500.get_outputs(metadata, add_batch=True)

            # Track statistics
            if outputs is None or len(outputs) < 3:
                self.outputs_fail += 1
                return []

            # Success
            self.outputs_success += 1

            # Check if model has postprocess built-in
            if self.intrinsics.postprocess == "nanodet":
                # Use nanodet postprocessing (nhu demo code)
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
                # Model co built-in postprocessing - THEO DEMO CODE
                boxes, scores, classes = outputs[0][0], outputs[1][0], outputs[2][0]

                # Normalize boxes
                if self.intrinsics.bbox_normalization:
                    input_w, input_h = self.imx500.get_input_size()
                    boxes = boxes / input_h

                # Swap bbox order if needed
                if self.intrinsics.bbox_order == "xy":
                    boxes = boxes[:, [1, 0, 3, 2]]

                # Reshape - DUNG NHU DEMO (khong co flatten!)
                boxes = np.array_split(boxes, 4, axis=1)
                boxes = zip(*boxes)

            # Filter by threshold va create Detection objects
            detections = []
            raw_count = 0
            filtered_count = 0

            for box, score, category in zip(boxes, scores, classes):
                if score > config.DETECTION_THRESHOLD:
                    raw_count += 1

                    # DUNG Detection class nhu demo code - convert_inference_coords() se handle dung!
                    detection = Detection(box, category, score, metadata, self.imx500, self.picam2)

                    # Get bbox da duoc convert sang pixel coords
                    x, y, w, h = detection.box

                    # Calculate aspect ratio
                    aspect_ratio = w / h if h > 0 else 0

                    # Bien so Viet Nam: width/height thuong 2.0 - 4.5
                    # Filter: chi accept boxes NAM NGANG
                    if aspect_ratio > config.MIN_PLATE_ASPECT_RATIO:
                        detections.append(detection)
                        filtered_count += 1


            return detections

        except Exception as e:
            # LUON log exception dau tien, sau do moi 50 frames
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

        if not text or len(text) < 7:  # Toi thieu 7 ky tu
            return False

        # Clean text - BO TAT CA KY TU DAC BIET (giu so + chu + dau -)
        clean = text.strip().upper().replace(" ", "").replace(".", "")

        # Patterns bien so VN - ACCEPT 1-2 CHU
        patterns = [
            # Xe o to (2 so + 1-2 chu + 4-6 so)
            r'^\d{2}[A-Z]{1,2}\d{4,6}$',           # 29A12345, 29AB12345
            r'^\d{2}[A-Z]{1,2}-\d{4,6}$',          # 29A-12345, 29AB-12345

            # Xe cong vu (3 so + 1-2 chu + 4-6 so)
            r'^\d{3}[A-Z]{1,2}\d{4,6}$',           # 123A12345, 123AB12345
            r'^\d{3}[A-Z]{1,2}-\d{4,6}$',          # 123A-12345

            # Xe may co format dac biet (29A1-12345)
            r'^\d{2}[A-Z]\d-?\d{4,5}$',            # 29A112345, 29A1-12345
        ]

        for pattern in patterns:
            if re.match(pattern, clean):
                return True

        # Kiem tra ty le so/chu hop ly
        digits = sum(c.isdigit() for c in clean)
        letters = sum(c.isalpha() for c in clean)

        # Bien so VN: 70-90% la so, 10-30% la chu (accept 1-3 chu)
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
        
        # Validate va normalize plate
        plate_id, display_text = self.parking_manager.validate_plate(plate_text)
        if not plate_id:
            return {
                'status': 'invalid',
                'message': f'Biển số không hợp lệ: {plate_text}'
            }
        
        # Check trong DB
        existing = self.parking_manager.db.find_entry_in(plate_id)
        
        if config.CAMERA_TYPE == "ENTRY":
            # Cong VAO: Xe chua co trong gara → valid
            if existing:
                return {
                    'status': 'invalid',
                    'message': f'Xe {display_text} đã VÀO lúc {existing["entry_time"]} tại {existing["entry_camera_name"]}'
                }
            else:
                return {'status': 'valid', 'message': ''}
        
        elif config.CAMERA_TYPE == "EXIT":
            # Cong RA: Xe da co trong gara → valid
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