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

        # MULTI-TARGET SUPPORT: Track each plate individually
        # Mỗi plate có riêng state: captured_frame, bbox, timestamp, ocr_attempts
        self.processing_plates = {}          # {plate_key: processing_data}
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

    def _get_plate_key(self, bbox):
        """Convert bbox to hashable key (rounded to 10px tolerance)"""
        x, y, w, h = bbox
        return (round(x / 10) * 10, round(y / 10) * 10, round(w / 10) * 10, round(h / 10) * 10)

    def _cleanup_old_processing_plates(self, current_time):
        """Xóa plates đã xử lý xong hoặc timeout"""
        timeout = config.CAPTURE_TIMEOUT
        keys_to_remove = []

        for key, data in self.processing_plates.items():
            # Remove if: OCR done OR timeout
            if data.get('done') or (current_time - data.get('timestamp', 0) > timeout):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.processing_plates[key]

    def _is_plate_ready_to_capture(self, plate_key, confidence, current_time):
        """Check if plate can be captured (not already processing and meets confidence)"""
        # Check if already processing this plate
        if plate_key in self.processing_plates:
            return False

        # Check confidence threshold
        if confidence < config.CAPTURE_CONFIDENCE_THRESHOLD:
            return False

        return True

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

                # DEBUG: Log số lượng detections
                if len(detections) > 0:
                    print(f"[DEBUG] Frame {frame_id}: Detected {len(detections)} plates")

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

                # Cleanup old processing plates (timeout or done)
                self._cleanup_old_processing_plates(current_time)

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

                    # == MULTI-TARGET CAPTURE LOGIC ==
                    # Capture mỗi plate riêng biệt (không block nhau)

                    bbox = (x, y, w, h)
                    plate_key = self._get_plate_key(bbox)

                    # Check if this plate can be captured
                    if (self._is_plate_ready_to_capture(plate_key, confidence, current_time) and
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
                                    # CAPTURE! Luu state cho plate nay
                                    self.processing_plates[plate_key] = {
                                        'captured_frame': crop.copy(),
                                        'bbox': bbox,
                                        'timestamp': current_time,
                                        'ocr_attempts': 0,
                                        'done': False,
                                        'confidence': confidence
                                    }

                                    # GUI ANH NGAY (chua co text)
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

                # == MULTI-TARGET OCR ==
                # Process OCR for ALL captured plates (not just one)

                if (config.ENABLE_OCR and
                    self.ocr_service and
                    self.ocr_service.is_ready()):

                    # Process each captured plate
                    for plate_key, plate_data in list(self.processing_plates.items()):
                        # Skip if already done or exceeded max attempts
                        if plate_data.get('done') or plate_data.get('ocr_attempts', 0) >= config.MAX_OCR_ATTEMPTS:
                            continue

                        try:
                            import cv2

                            # Lay crop da capture cho plate nay
                            crop = plate_data['captured_frame'].copy()
                            bbox = plate_data['bbox']
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
                            plate_data['ocr_attempts'] += 1
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
                                    plate_data['done'] = True  # Mark as done
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

                                    # Check if skipped (already at location)
                                    if entry_result.get('skip'):
                                        # SKIP: Xe đã ở vị trí này rồi, không cần sync
                                        print(f"[SKIP] {text} - {entry_result.get('message')}")
                                    elif entry_result.get('success'):
                                        entry_saved = True
                                        print(f"Auto saved: {text} - {entry_result.get('message')}")

                                        # Sync to Central (neu co)
                                        if self.central_sync:
                                            # Determine event type based on camera type and action
                                            action = entry_result.get('action', '')

                                            if config.CAMERA_TYPE == "PARKING_LOT":
                                                # PARKING_LOT camera: LOCATION_UPDATE or AUTO_ENTRY
                                                if action == "LOCATION_UPDATE":
                                                    event_type = "LOCATION_UPDATE"
                                                elif action == "AUTO_ENTRY":
                                                    event_type = "ENTRY"  # Auto-created entry (anomaly)
                                                else:
                                                    event_type = "LOCATION_UPDATE"  # Default for parking lot
                                            elif config.CAMERA_TYPE == "ENTRY":
                                                event_type = "ENTRY"
                                            else:
                                                event_type = "EXIT"

                                            sync_data = {
                                                "plate_text": text,
                                                "plate_id": entry_result.get("plate_id"),
                                                "confidence": 0.95,
                                                "source": "auto",
                                                "event_id": entry_result.get("event_id"),  # Include event_id
                                            }

                                            # Add type-specific data
                                            if event_type == "ENTRY":
                                                sync_data['entry_id'] = entry_result.get('entry_id')
                                                sync_data['entry_time'] = entry_result.get('entry_time')
                                                # Include anomaly flag if auto-created
                                                if entry_result.get('is_anomaly'):
                                                    sync_data['is_anomaly'] = True
                                            elif event_type == "EXIT":
                                                sync_data['entry_id'] = entry_result.get('entry_id')
                                                if entry_result.get('duration'):
                                                    sync_data['duration'] = entry_result.get('duration')
                                                if entry_result.get('fee') is not None:
                                                    sync_data['fee'] = entry_result.get('fee')
                                            elif event_type == "LOCATION_UPDATE":
                                                sync_data['location'] = entry_result.get('location')
                                                sync_data['location_time'] = entry_result.get('location_time')

                                            self.central_sync.send_event(event_type, sync_data)

                                # BUOC 3: GUI KET QUA QUA WEBSOCKET
                                text_result = {
                                    'class': 'license_plate',
                                    'confidence': 0.95,
                                    'bbox': list(bbox),
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

                                # Mark plate as done (OCR success)
                                plate_data['done'] = True

                            else:
                                # OCR khong hop le
                                # Neu da het attempts → Mark as done
                                if plate_data.get('ocr_attempts', 0) >= config.MAX_OCR_ATTEMPTS:
                                    plate_data['done'] = True

                        except Exception as e:
                            # Mark plate as done on error
                            plate_data['done'] = True
                            print(f"[OCR Error] {e}")

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

        elif config.CAMERA_TYPE == "PARKING_LOT":
            # Camera trong bãi: Luôn valid (xử lý cả 2 trường hợp trong process_entry)
            # - Có trong bãi: Update location
            # - Không trong bãi: Auto-create entry (anomaly)
            return {'status': 'valid', 'message': ''}
        
        return {'status': 'valid', 'message': ''}

    @lru_cache
    def _get_labels(self):
        """Get labels"""
        labels = self.intrinsics.labels
        if self.intrinsics.ignore_dash_labels:
            labels = [label for label in labels if label and label != "-"]
        return labels