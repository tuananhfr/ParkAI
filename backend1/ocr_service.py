"""
OCR Service - Đọc text từ license plate
DÙNG ULTRALYTICS YOLO - giống script test.py (đã hoạt động tốt)
"""
import cv2
import numpy as np
import os

import config


class OCRService:
    """Service để OCR license plates - CHỈ TFLite và ONNX"""

    def __init__(self):
        self.ocr = None
        self.ocr_type = 'none'
        self._ready = False
        self.error = None

        # PRIORITY: Try YOLO first (giống script test.py - ĐÃ HOẠT ĐỘNG TỐT!)
        if self._try_init_yolo():
            return

        # Fallback: raw ONNX/TFLite (phức tạp hơn, dễ lỗi)
        print("⚠️  YOLO not available, trying raw ONNX/TFLite...")
        self.input_details = None
        self.output_details = None
        self.input_shape = None
        self.ocr_provider = None
        self.class_names = None

        if config.OCR_TYPE == "tflite":
            init_order = [self._try_init_tflite, self._try_init_onnx]
        elif config.OCR_TYPE == "onnx":
            init_order = [self._try_init_onnx, self._try_init_tflite]
        else:
            init_order = [self._try_init_tflite, self._try_init_onnx]

        for init_fn in init_order:
            if init_fn():
                return

        self.ocr_type = 'none'
        self._ready = False

    def is_ready(self):
        return self._ready

    def get_status(self):
        return {
            "type": self.ocr_type,
            "ready": self._ready,
            "provider": getattr(self, "ocr_provider", "ultralytics"),
            "error": self.error
        }

    def _try_init_yolo(self):
        """Thử khởi tạo YOLO OCR (GIỐNG SCRIPT TEST.PY - ƯU TIÊN!)"""
        # Check ONNX model path
        model_path = config.ONNX_OCR_MODEL_PATH or config.TFLITE_OCR_MODEL_PATH

        if model_path is None:
            self.error = "OCR_MODEL_PATH chưa được cấu hình"
            return False

        # YOLO chỉ support ONNX, không support TFLite
        if not model_path.endswith('.onnx'):
            self.error = f"YOLO chỉ hỗ trợ .onnx, không hỗ trợ {model_path}"
            return False

        if not os.path.exists(model_path):
            self.error = f"YOLO model không tồn tại: {model_path}"
            return False

        try:
            from ultralytics import YOLO
            self.ocr = YOLO(model_path, task='detect')
            self.ocr_type = 'yolo'
            self.ocr_provider = 'ultralytics'
            self._ready = True
            self.error = None
            print(f"✅ YOLO OCR ready")
            return True
        except ImportError:
            self.error = "Thiếu ultralytics library (pip install ultralytics)"
            return False
        except Exception as exc:
            self.error = f"YOLO init lỗi: {exc}"
            self.ocr = None
            return False

    def _read_yolo(self, plate_img):
        """
        YOLO OCR - GIỐNG SCRIPT TEST.PY
        Đơn giản, đúng, không cần implement lại parsing/NMS
        """
        try:
            print(f"🔍 YOLO OCR - Input image shape: {plate_img.shape}")

            # Run YOLO inference (conf=0.5, imgsz=640 - GIỐNG SCRIPT)
            ocr_results = self.ocr(plate_img, conf=0.5, verbose=False, imgsz=640)

            # Parse character boxes (GIỐNG SCRIPT)
            char_data = []
            for cr in ocr_results:
                print(f"🔍 YOLO OCR - Detected {len(cr.boxes)} boxes")
                for cb in cr.boxes:
                    bx1, by1, bx2, by2 = map(int, cb.xyxy[0])
                    conf = float(cb.conf[0])
                    cls = int(cb.cls[0])
                    print(f"  Box: ({bx1},{by1},{bx2},{by2}), conf={conf:.2f}, class={cls}")
                    char_data.append([
                        bx1, by1, bx2, by2,
                        conf,
                        cls
                    ])

            if not char_data:
                print("⚠️  YOLO OCR - No characters detected")
                return None

            # Sort và ghép text (GIỐNG SCRIPT)
            text = self._sort_chars_yolo(char_data)
            print(f"🔍 YOLO OCR - Final text: '{text}'")
            return text

        except Exception as e:
            print(f"❌ YOLO OCR error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _sort_chars_yolo(self, boxes):
        """Sắp xếp ký tự - GIỐNG SCRIPT TEST.PY"""
        if not boxes:
            return ""

        chars = []
        for box in boxes:
            x1, y1, x2, y2 = box[:4]
            cls = int(box[5])
            label = self.ocr.names[cls]  # Lấy từ model names (GIỐNG SCRIPT!)
            chars.append([(x1+x2)/2, (y1+y2)/2, label])

        y_coords = [c[1] for c in chars]
        mean_y = sum(y_coords) / len(y_coords) if y_coords else 0

        # Check if 2 lines (GIỐNG SCRIPT - threshold 0.15)
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

    def _try_init_tflite(self):
        """Thử khởi tạo TFLite OCR (ưu tiên tflite_runtime, fallback TensorFlow)"""
        model_path = config.TFLITE_OCR_MODEL_PATH

        if model_path is None:
            self.error = "TFLITE_OCR_MODEL_PATH chưa được cấu hình"
            return False

        if not os.path.exists(model_path):
            self.error = f"TFLite model không tồn tại: {model_path}"
            return False

        interpreter_cls = None
        provider = None

        try:
            from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter
            interpreter_cls = TFLiteInterpreter
            provider = "tflite_runtime"
        except ImportError:
            try:
                import tensorflow as tf
                interpreter_cls = tf.lite.Interpreter
                provider = "tensorflow"
            except ImportError:
                self.error = "Thiếu tflite_runtime và tensorflow"
                return False

        try:
            self.ocr = interpreter_cls(model_path=model_path)
            self.ocr.allocate_tensors()
            self.input_details = self.ocr.get_input_details()
            self.output_details = self.ocr.get_output_details()
            self.input_shape = self.input_details[0]['shape']
            self.ocr_type = 'tflite'
            self.ocr_provider = provider
            self._ready = True
            self.error = None
            return True
        except Exception as exc:
            self.error = f"TFLite init lỗi: {exc}"
            self.ocr = None
            return False

    def _try_init_onnx(self):
        """Thử khởi tạo ONNX OCR (Fast alternative)"""
        model_path = config.ONNX_OCR_MODEL_PATH

        if model_path is None:
            return False

        if not os.path.exists(model_path):
            self.error = f"ONNX model không tồn tại: {model_path}"
            return False

        try:
            import onnxruntime as ort
        except ImportError:
            self.error = "Thiếu onnxruntime"
            return False

        try:
            self.ocr = ort.InferenceSession(model_path)
            self.input_name = self.ocr.get_inputs()[0].name
            self.input_shape = self.ocr.get_inputs()[0].shape

            # Try to load class names from ONNX metadata
            self.class_names = self._load_onnx_class_names(model_path)

            self.ocr_type = 'onnx'
            self.ocr_provider = "onnxruntime"
            self._ready = True
            self.error = None
            print(f"✅ ONNX class names: {self.class_names}")
            return True
        except Exception as exc:
            self.error = f"ONNX init lỗi: {exc}"
            self.ocr = None
            return False

    def _load_onnx_class_names(self, model_path):
        """Load class names from ONNX model metadata"""
        try:
            import onnx
            model = onnx.load(model_path)

            # Try to find class names in metadata
            for prop in model.metadata_props:
                if prop.key == 'names':
                    # Parse names string: "{0: '0', 1: '1', 2: '2', ...}"
                    import ast
                    names_dict = ast.literal_eval(prop.value)
                    # Convert to list
                    max_idx = max(names_dict.keys())
                    class_names = [names_dict.get(i, str(i)) for i in range(max_idx + 1)]
                    return class_names
        except Exception as e:
            print(f"⚠️  Cannot load class names from ONNX: {e}")

        # Fallback: default charset
        return None
    
    def recognize(self, plate_img):
        """
        Đọc text từ plate image

        Args:
            plate_img: numpy array of plate image

        Returns:
            text string or None
        """
        # Nếu không có OCR engine, return None ngay
        if not self.is_ready():
            return None

        try:
            if self.ocr_type == 'yolo':
                # DÙNG YOLO - GIỐNG SCRIPT TEST.PY (ĐƠN GIẢN VÀ ĐÚNG!)
                return self._read_yolo(plate_img)
            elif self.ocr_type == 'tflite':
                result = self._read_tflite(plate_img)
                return result['text'] if result else None
            elif self.ocr_type == 'onnx':
                result = self._read_onnx(plate_img)
                return result['text'] if result else None
            else:
                return None

        except Exception as e:
            print(f"❌ OCR recognize error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def read_plate(self, plate_img):
        """
        Đọc text từ plate image (với confidence)

        Args:
            plate_img: numpy array of plate image

        Returns:
            dict with 'text' and 'confidence' or None
        """
        # Nếu không có OCR engine, return None ngay
        if not self.is_ready():
            return None

        # Chỉ handle TFLite và ONNX
        try:
            if self.ocr_type == 'tflite':
                return self._read_tflite(plate_img)
            elif self.ocr_type == 'onnx':
                return self._read_onnx(plate_img)
            else:
                return None

        except Exception as e:
            return None

    def _read_tflite(self, img):
        """TFLite OCR - YOLO-based character detection"""
        try:
            # Preprocess for TFLite
            processed = self._preprocess_tflite(img)

            # Set input tensor
            self.ocr.set_tensor(self.input_details[0]['index'], processed)

            # Run inference
            self.ocr.invoke()

            # Get all outputs (YOLO model có multiple outputs)
            outputs = []
            for output_detail in self.output_details:
                output = self.ocr.get_tensor(output_detail['index'])
                outputs.append(output)

            # Debug: Log output shapes lần đầu
            if not hasattr(self, '_output_shapes_logged'):
                print(f"🔍 TFLite outputs: {len(outputs)} tensors")
                for i, out in enumerate(outputs):
                    print(f"  Output[{i}]: shape={out.shape}, dtype={out.dtype}")
                self._output_shapes_logged = True

            # Parse YOLO detections
            text = self._decode_yolo_tflite_output(outputs, img)

            if text and len(text) > 0:
                return {
                    'text': text.strip(),
                    'confidence': 0.9
                }

            return None

        except Exception as e:
            print(f"❌ TFLite OCR error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _preprocess_tflite(self, img):
        """Preprocess image for TFLite model (YOLO format)"""
        # Get input size
        h, w = self.input_shape[1:3]

        # NOTE: Camera format is already RGB888, no need to convert from BGR
        # (camera_manager.py line 50: "format": "RGB888")

        # Resize to model input size
        img = cv2.resize(img, (w, h))

        # Normalize to [0, 1]
        img = img.astype(np.float32) / 255.0

        # Add batch dimension (TFLite uses NHWC format)
        img = np.expand_dims(img, axis=0)

        return img

    def _decode_yolo_tflite_output(self, outputs, img):
        """Parse YOLO v8 output và sort characters"""
        try:
            # YOLO v8 output format: (1, 4+num_classes, num_anchors)
            # Example: (1, 40, 8400) → 40 = 4 bbox + 36 classes

            # Try to find the main output
            detections = None
            for out in outputs:
                if len(out.shape) == 3:
                    detections = out
                    break

            if detections is None:
                return None

            # YOLO v8: (1, 4+C, 8400) → transpose to (1, 8400, 4+C)
            if detections.shape[1] < detections.shape[2]:
                detections = detections.transpose(0, 2, 1)

            # detections shape: (1, num_anchors, 4+C) → (num_anchors, 4+C)
            detections = detections[0]

            # Split bbox and class scores
            boxes = detections[:, :4]  # (num_anchors, 4) - [x, y, w, h]
            scores = detections[:, 4:]  # (num_anchors, num_classes)

            # Get best class and confidence for each anchor
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)

            # Debug: Show confidence distribution
            max_conf = np.max(confidences)
            top10_conf = np.sort(confidences)[-10:][::-1]
            print(f"🔍 Confidence: max={max_conf:.3f}, top10={top10_conf}")

            # Filter by confidence threshold - KHỚP với script test.py
            conf_threshold = 0.5
            mask = confidences > conf_threshold

            if not np.any(mask):
                print(f"⚠️  No detections above threshold {conf_threshold}")
                print(f"   Try lowering threshold or check input preprocessing")
                return None

            boxes = boxes[mask]
            class_ids = class_ids[mask]
            confidences = confidences[mask]

            print(f"🔍 Before NMS: {len(boxes)} characters with conf > {conf_threshold}")

            # Apply class-aware NMS (giống YOLO - chỉ suppress trong cùng class)
            boxes, class_ids, confidences = self._apply_class_aware_nms(boxes, class_ids, confidences, iou_threshold=0.45)

            print(f"🔍 After NMS: {len(boxes)} characters remaining")

            if len(boxes) == 0:
                return None

            # Get original crop image dimensions
            img_h, img_w = img.shape[:2] if len(img.shape) >= 2 else (640, 640)

            # Get model input size (boxes are in model input scale)
            if hasattr(self, 'input_shape') and len(self.input_shape) >= 3:
                if self.ocr_type == 'onnx':
                    # ONNX: (1, 3, H, W)
                    model_h, model_w = self.input_shape[2:4]
                else:
                    # TFLite: (1, H, W, 3)
                    model_h, model_w = self.input_shape[1:3]
            else:
                model_h, model_w = 640, 640

            # Scale factors: model_size → crop_size
            scale_x = img_w / model_w
            scale_y = img_h / model_h

            print(f"🔍 Model size: ({model_w}, {model_h}), Crop size: ({img_w}, {img_h}), Scale: ({scale_x:.3f}, {scale_y:.3f})")

            # Convert boxes to xyxy and create char_data
            char_data = []
            for box, cls, conf in zip(boxes, class_ids, confidences):
                x_center, y_center, w, h = box

                # Scale from model input size to crop size
                x_center *= scale_x
                y_center *= scale_y
                w *= scale_x
                h *= scale_y

                # Convert to xyxy format
                x1 = int(x_center - w/2)
                y1 = int(y_center - h/2)
                x2 = int(x_center + w/2)
                y2 = int(y_center + h/2)

                # Clamp to image boundaries
                x1 = max(0, min(x1, img_w))
                y1 = max(0, min(y1, img_h))
                x2 = max(0, min(x2, img_w))
                y2 = max(0, min(y2, img_h))

                char_data.append([x1, y1, x2, y2, float(conf), int(cls)])
                print(f"  Char class={cls}, conf={conf:.2f}, bbox=({x1},{y1},{x2},{y2})")

            # Sort và ghép text
            text = self._sort_chars(char_data)
            return text

        except Exception as e:
            print(f"❌ Decode YOLO output error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _apply_class_aware_nms(self, boxes, class_ids, confidences, iou_threshold=0.45):
        """Apply class-aware NMS - chỉ suppress trong cùng class (giống YOLO)"""
        if len(boxes) == 0:
            return boxes, class_ids, confidences

        # Convert boxes from center format to xyxy for NMS
        boxes_xyxy = []
        for box in boxes:
            x_center, y_center, w, h = box
            x1 = x_center - w/2
            y1 = y_center - h/2
            x2 = x_center + w/2
            y2 = y_center + h/2
            boxes_xyxy.append([x1, y1, x2, y2])

        boxes_xyxy = np.array(boxes_xyxy)

        # Class-aware NMS: apply NMS per class
        indices_to_keep = []
        unique_classes = np.unique(class_ids)

        for cls in unique_classes:
            # Get indices for this class
            cls_mask = class_ids == cls
            cls_indices = np.where(cls_mask)[0]

            if len(cls_indices) == 0:
                continue

            # Get boxes and confidences for this class
            cls_boxes = boxes_xyxy[cls_indices]
            cls_confs = confidences[cls_indices]

            # Sort by confidence (high to low)
            sorted_idx = np.argsort(cls_confs)[::-1]
            cls_indices = cls_indices[sorted_idx]
            cls_boxes = cls_boxes[sorted_idx]

            # NMS within this class
            keep = []
            while len(cls_indices) > 0:
                # Keep highest confidence box
                keep.append(cls_indices[0])

                if len(cls_indices) == 1:
                    break

                # Compute IoU with remaining boxes
                current_box = cls_boxes[0]
                remaining_boxes = cls_boxes[1:]

                ious = self._compute_iou(current_box, remaining_boxes)

                # Keep only boxes with IoU < threshold
                keep_mask = ious < iou_threshold
                cls_indices = cls_indices[1:][keep_mask]
                cls_boxes = cls_boxes[1:][keep_mask]

            indices_to_keep.extend(keep)

        # Return filtered results
        return boxes[indices_to_keep], class_ids[indices_to_keep], confidences[indices_to_keep]

    def _compute_iou(self, box, boxes):
        """Compute IoU between one box and multiple boxes"""
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
        """Sắp xếp ký tự từ trái sang phải, hỗ trợ 2 dòng (giống script test.py)"""
        if not boxes:
            return ""

        # Use class names from model metadata (giống script test.py)
        if self.class_names:
            charset = self.class_names
        else:
            # Fallback: default charset
            charset = "0123456789ABCDEFGHKLMNPSTUVXYZ"
            print("⚠️  Using fallback charset - may be incorrect!")

        chars = []
        for box in boxes:
            x1, y1, x2, y2, conf, cls = box
            label = charset[cls] if cls < len(charset) else str(cls)
            chars.append([(x1+x2)/2, (y1+y2)/2, label])

        y_coords = [c[1] for c in chars]
        mean_y = sum(y_coords) / len(y_coords) if y_coords else 0

        # Check if 2 lines - Biển số VN 2 dòng thường có >= 6 ký tự
        is_two_lines = False
        if len(chars) >= 6:  # Phải có ít nhất 6 ký tự mới có thể 2 dòng
            spread = max(y_coords) - min(y_coords)
            # Tăng threshold lên 0.25 để tránh false positive với crop nhỏ
            if spread > (max(y_coords) + min(y_coords)) * 0.25:
                is_two_lines = True

        if is_two_lines:
            top = sorted([c for c in chars if c[1] < mean_y], key=lambda x: x[0])
            bot = sorted([c for c in chars if c[1] >= mean_y], key=lambda x: x[0])
            return "".join([c[2] for c in top]) + "-" + "".join([c[2] for c in bot])
        else:
            return "".join([c[2] for c in sorted(chars, key=lambda x: x[0])])

    def _read_onnx(self, img):
        """ONNX OCR - YOLO-based character detection"""
        try:
            # Preprocess for ONNX
            processed = self._preprocess_onnx(img)

            # Run inference - YOLO model có multiple outputs
            outputs = self.ocr.run(None, {self.input_name: processed})

            # Debug: Log output shapes lần đầu
            if not hasattr(self, '_onnx_output_shapes_logged'):
                print(f"🔍 ONNX outputs: {len(outputs)} tensors")
                for i, out in enumerate(outputs):
                    print(f"  Output[{i}]: shape={out.shape}, dtype={out.dtype}")
                self._onnx_output_shapes_logged = True

            # Parse YOLO detections (dùng chung logic với TFLite)
            text = self._decode_yolo_tflite_output(outputs, img)

            if text and len(text) > 0:
                return {
                    'text': text.strip(),
                    'confidence': 0.9
                }

            return None

        except Exception as e:
            print(f"❌ ONNX OCR error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _preprocess_onnx(self, img):
        """Preprocess image for ONNX model (YOLO format - NCHW)"""
        # ONNX YOLO model expects NCHW format: (batch, channels, height, width)

        # Get target size from input shape
        # ONNX shape: (1, 3, 640, 640) → need (batch=1, channels=3, h=640, w=640)
        if len(self.input_shape) == 4:
            batch, channels, h, w = self.input_shape
        else:
            # Fallback to default YOLO size
            h, w, channels = 640, 640, 3

        # NOTE: Camera format is already RGB888, no need to convert from BGR
        # (camera_manager.py line 50: "format": "RGB888")

        # Resize image
        img = cv2.resize(img, (w, h))

        # Normalize to [0, 1]
        img = img.astype(np.float32) / 255.0

        # Convert from HWC to CHW (transpose)
        # (H, W, C) → (C, H, W)
        img = np.transpose(img, (2, 0, 1))

        # Add batch dimension
        # (C, H, W) → (1, C, H, W)
        img = np.expand_dims(img, axis=0)

        return img

    # Legacy CTC decoding - không dùng cho YOLO model
    # def _decode_onnx_output(self, output):
    #     """Decode ONNX output to text"""
    #     indices = np.argmax(output[0], axis=-1)
    #     chars = []
    #     prev_idx = -1
    #     for idx in indices:
    #         if idx != prev_idx and idx != 0:
    #             char = self._idx_to_char(int(idx))
    #             if char:
    #                 chars.append(char)
    #         prev_idx = idx
    #     return ''.join(chars)