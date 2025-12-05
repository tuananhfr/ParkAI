"""
OCR Service - Đọc text từ license plate
CHỈ DÙNG YOLO (Ultralytics) hoặc ONNX Runtime
"""
import cv2
import numpy as np
import os

import config


class OCRService:
    """Service OCR - YOLO (priority) hoặc ONNX"""

    def __init__(self):
        self.ocr = None
        self.ocr_type = 'none'
        self._ready = False
        self.error = None
        self.ocr_provider = None
        self.class_names = None

        # PRIORITY 1: YOLO (ultralytics - ĐƠN GIẢN NHẤT)
        if self._try_init_yolo():
            return

        # PRIORITY 2: Raw ONNX (phức tạp hơn)
        print(" YOLO not available, trying raw ONNX...")
        self.input_shape = None
        self.input_name = None

        if self._try_init_onnx():
            return

        # Failed
        self.ocr_type = 'none'
        self._ready = False

    def is_ready(self):
        return self._ready

    def get_status(self):
        return {
            "type": self.ocr_type,
            "ready": self._ready,
            "provider": self.ocr_provider,
            "error": self.error
        }

    # YOLO (Ultralytics) 
    def _try_init_yolo(self):
        """Khởi tạo YOLO OCR - GIỐNG CODE DEMO"""
        model_path = config.ONNX_OCR_MODEL_PATH

        if model_path is None:
            self.error = "ONNX_OCR_MODEL_PATH chưa được cấu hình"
            return False

        if not model_path.endswith('.onnx'):
            self.error = f"YOLO chỉ hỗ trợ .onnx (got: {model_path})"
            return False

        if not os.path.exists(model_path):
            self.error = f"Model không tồn tại: {model_path}"
            return False

        try:
            from ultralytics import YOLO
            self.ocr = YOLO(model_path, task='detect')
            self.ocr_type = 'yolo'
            self.ocr_provider = 'ultralytics'
            self._ready = True
            self.error = None
            print(f"YOLO OCR ready")
            return True
        except ImportError:
            self.error = "Thiếu ultralytics (pip install ultralytics)"
            return False
        except Exception as exc:
            self.error = f"YOLO init lỗi: {exc}"
            return False

    def _read_yolo(self, plate_img):
        """YOLO OCR inference"""
        try:
            # Run inference - Confidence balanced
            ocr_results = self.ocr(plate_img, conf=0.25, verbose=False, imgsz=640)

            # Parse character boxes
            char_data = []
            for cr in ocr_results:
                for cb in cr.boxes:
                    bx1, by1, bx2, by2 = map(int, cb.xyxy[0])
                    char_data.append([
                        bx1, by1, bx2, by2,
                        float(cb.conf[0]),
                        int(cb.cls[0])
                    ])

            if not char_data:
                return None

            # Sort và ghép text
            text = self._sort_chars_yolo(char_data)
            return text

        except Exception as e:
            print(f"YOLO OCR error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _sort_chars_yolo(self, boxes):
        """Sắp xếp ký tự"""
        if not boxes:
            return ""

        # Get class names (fallback nếu None)
        if self.ocr.names is None:
            # Vietnamese plate charset (36 classes: 0-9, A-Z)
            charset = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            names = {i: c for i, c in enumerate(charset)}
        else:
            names = self.ocr.names

        chars = []
        for box in boxes:
            x1, y1, x2, y2 = box[:4]
            cls = int(box[5])
            label = names.get(cls, str(cls))

            # Cho phép đọc TẤT CẢ ký tự (bao gồm -, .)
            # Voting sẽ normalize sau
            if label:
                chars.append([(x1+x2)/2, (y1+y2)/2, str(label)])

        y_coords = [c[1] for c in chars]
        mean_y = sum(y_coords) / len(y_coords) if y_coords else 0

        # Check if 2 lines
        is_two_lines = False
        if len(chars) > 2:
            spread = max(y_coords) - min(y_coords)
            if spread > (max(y_coords) + min(y_coords)) * 0.15:
                is_two_lines = True

        if is_two_lines:
            top = sorted([c for c in chars if c[1] < mean_y], key=lambda x: x[0])
            bot = sorted([c for c in chars if c[1] >= mean_y], key=lambda x: x[0])
            return "".join([c[2] for c in top]) + "-" + "".join([c[2] for c in bot])
        else:
            return "".join([c[2] for c in sorted(chars, key=lambda x: x[0])])

    # ONNX Runtime 
    def _try_init_onnx(self):
        """Khởi tạo ONNX OCR"""
        model_path = config.ONNX_OCR_MODEL_PATH

        if model_path is None:
            self.error = "ONNX_OCR_MODEL_PATH chưa được cấu hình"
            return False

        if not os.path.exists(model_path):
            self.error = f"ONNX model không tồn tại: {model_path}"
            return False

        try:
            import onnxruntime as ort
        except ImportError:
            self.error = "Thiếu onnxruntime (pip install onnxruntime)"
            return False

        try:
            self.ocr = ort.InferenceSession(model_path)
            self.input_name = self.ocr.get_inputs()[0].name
            self.input_shape = self.ocr.get_inputs()[0].shape

            # Load class names from metadata
            self.class_names = self._load_onnx_class_names(model_path)

            self.ocr_type = 'onnx'
            self.ocr_provider = "onnxruntime"
            self._ready = True
            self.error = None
            print(f"ONNX OCR ready")
            return True
        except Exception as exc:
            self.error = f"ONNX init lỗi: {exc}"
            return False

    def _load_onnx_class_names(self, model_path):
        """Load class names từ ONNX metadata"""
        try:
            import onnx
            model = onnx.load(model_path)

            for prop in model.metadata_props:
                if prop.key == 'names':
                    import ast
                    names_dict = ast.literal_eval(prop.value)
                    max_idx = max(names_dict.keys())
                    class_names = [names_dict.get(i, str(i)) for i in range(max_idx + 1)]
                    return class_names
        except Exception as e:
            print(f" Cannot load class names from ONNX: {e}")

        return None

    def _read_onnx(self, img):
        """ONNX OCR inference"""
        try:
            # Preprocess
            processed = self._preprocess_onnx(img)

            # Run inference
            outputs = self.ocr.run(None, {self.input_name: processed})

            # Parse YOLO output
            text = self._decode_yolo_output(outputs, img)

            if text and len(text) > 0:
                return {
                    'text': text.strip(),
                    'confidence': 0.9
                }

            return None

        except Exception as e:
            print(f"ONNX OCR error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _preprocess_onnx(self, img):
        """Preprocess image cho ONNX (YOLO format - NCHW)"""
        # Get input size
        if len(self.input_shape) == 4:
            batch, channels, h, w = self.input_shape
        else:
            h, w, channels = 640, 640, 3

        # Resize
        img = cv2.resize(img, (w, h))

        # Normalize
        img = img.astype(np.float32) / 255.0

        # HWC → CHW
        img = np.transpose(img, (2, 0, 1))

        # Add batch dimension
        img = np.expand_dims(img, axis=0)

        return img

    def _decode_yolo_output(self, outputs, img):
        """Parse YOLO v8 output"""
        try:
            # Find main output
            detections = None
            for out in outputs:
                if len(out.shape) == 3:
                    detections = out
                    break

            if detections is None:
                return None

            # Transpose if needed: (1, 4+C, 8400) → (1, 8400, 4+C)
            if detections.shape[1] < detections.shape[2]:
                detections = detections.transpose(0, 2, 1)

            detections = detections[0]  # (8400, 4+C)

            # Split bbox and scores
            boxes = detections[:, :4]  # (8400, 4) - [x, y, w, h]
            scores = detections[:, 4:]  # (8400, num_classes)

            # Get best class
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)

            # Filter by confidence
            conf_threshold = 0.5
            mask = confidences > conf_threshold

            if not np.any(mask):
                return None

            boxes = boxes[mask]
            class_ids = class_ids[mask]
            confidences = confidences[mask]

            # Apply NMS
            boxes, class_ids, confidences = self._apply_class_aware_nms(
                boxes, class_ids, confidences, iou_threshold=0.45
            )

            if len(boxes) == 0:
                return None

            # Get image size
            img_h, img_w = img.shape[:2] if len(img.shape) >= 2 else (640, 640)

            # Get model size
            if len(self.input_shape) == 4:
                model_h, model_w = self.input_shape[2:4]
            else:
                model_h, model_w = 640, 640

            # Scale factors
            scale_x = img_w / model_w
            scale_y = img_h / model_h

            # Convert boxes và tạo char_data
            char_data = []
            for box, cls, conf in zip(boxes, class_ids, confidences):
                x_center, y_center, w, h = box

                # Scale to image size
                x_center *= scale_x
                y_center *= scale_y
                w *= scale_x
                h *= scale_y

                # Convert to xyxy
                x1 = int(x_center - w/2)
                y1 = int(y_center - h/2)
                x2 = int(x_center + w/2)
                y2 = int(y_center + h/2)

                # Clamp
                x1 = max(0, min(x1, img_w))
                y1 = max(0, min(y1, img_h))
                x2 = max(0, min(x2, img_w))
                y2 = max(0, min(y2, img_h))

                char_data.append([x1, y1, x2, y2, float(conf), int(cls)])

            # Sort và ghép text
            text = self._sort_chars(char_data)
            return text

        except Exception as e:
            print(f"Decode YOLO output error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _apply_class_aware_nms(self, boxes, class_ids, confidences, iou_threshold=0.45):
        """Class-aware NMS"""
        if len(boxes) == 0:
            return boxes, class_ids, confidences

        # Convert to xyxy
        boxes_xyxy = []
        for box in boxes:
            x_center, y_center, w, h = box
            x1 = x_center - w/2
            y1 = y_center - h/2
            x2 = x_center + w/2
            y2 = y_center + h/2
            boxes_xyxy.append([x1, y1, x2, y2])

        boxes_xyxy = np.array(boxes_xyxy)

        # NMS per class
        indices_to_keep = []
        unique_classes = np.unique(class_ids)

        for cls in unique_classes:
            cls_mask = class_ids == cls
            cls_indices = np.where(cls_mask)[0]

            if len(cls_indices) == 0:
                continue

            cls_boxes = boxes_xyxy[cls_indices]
            cls_confs = confidences[cls_indices]

            # Sort by confidence
            sorted_idx = np.argsort(cls_confs)[::-1]
            cls_indices = cls_indices[sorted_idx]
            cls_boxes = cls_boxes[sorted_idx]

            # NMS
            keep = []
            while len(cls_indices) > 0:
                keep.append(cls_indices[0])

                if len(cls_indices) == 1:
                    break

                current_box = cls_boxes[0]
                remaining_boxes = cls_boxes[1:]

                ious = self._compute_iou(current_box, remaining_boxes)

                keep_mask = ious < iou_threshold
                cls_indices = cls_indices[1:][keep_mask]
                cls_boxes = cls_boxes[1:][keep_mask]

            indices_to_keep.extend(keep)

        return boxes[indices_to_keep], class_ids[indices_to_keep], confidences[indices_to_keep]

    def _compute_iou(self, box, boxes):
        """Compute IoU"""
        x1 = np.maximum(box[0], boxes[:, 0])
        y1 = np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[2], boxes[:, 2])
        y2 = np.minimum(box[3], boxes[:, 3])

        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        box_area = (box[2] - box[0]) * (box[3] - box[1])
        boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])

        union = box_area + boxes_area - intersection

        return intersection / (union + 1e-6)

    def _sort_chars(self, boxes):
        """Sắp xếp ký tự"""
        if not boxes:
            return ""

        # Use class names
        if self.class_names:
            charset = self.class_names
        else:
            charset = "0123456789ABCDEFGHKLMNPSTUVXYZ"
            print(" Using fallback charset")

        chars = []
        for box in boxes:
            x1, y1, x2, y2, conf, cls = box
            label = charset[cls] if cls < len(charset) else str(cls)

            # Cho phép đọc TẤT CẢ ký tự (bao gồm -, .)
            # Voting sẽ normalize sau
            if label:
                chars.append([(x1+x2)/2, (y1+y2)/2, str(label)])

        y_coords = [c[1] for c in chars]
        mean_y = sum(y_coords) / len(y_coords) if y_coords else 0

        # Check 2 lines
        is_two_lines = False
        if len(chars) >= 6:
            spread = max(y_coords) - min(y_coords)
            if spread > (max(y_coords) + min(y_coords)) * 0.25:
                is_two_lines = True

        if is_two_lines:
            top = sorted([c for c in chars if c[1] < mean_y], key=lambda x: x[0])
            bot = sorted([c for c in chars if c[1] >= mean_y], key=lambda x: x[0])
            return "".join([c[2] for c in top]) + "-" + "".join([c[2] for c in bot])
        else:
            return "".join([c[2] for c in sorted(chars, key=lambda x: x[0])])

    # Public API 
    def recognize(self, plate_img):
        """Đọc text từ plate image"""
        if not self.is_ready():
            return None

        try:
            if self.ocr_type == 'yolo':
                return self._read_yolo(plate_img)
            elif self.ocr_type == 'onnx':
                result = self._read_onnx(plate_img)
                return result['text'] if result else None
            else:
                return None

        except Exception as e:
            print(f"OCR recognize error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def read_plate(self, plate_img):
        """Đọc text từ plate (với confidence)"""
        if not self.is_ready():
            return None

        try:
            if self.ocr_type == 'onnx':
                return self._read_onnx(plate_img)
            else:
                # YOLO không return confidence riêng
                text = self.recognize(plate_img)
                if text:
                    return {'text': text, 'confidence': 0.9}
                return None

        except Exception as e:
            return None
