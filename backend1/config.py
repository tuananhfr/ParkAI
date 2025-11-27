# ==================== CONFIG - OPTIMAL FOR SMOOTH VIDEO ====================
MODEL_PATH = "/home/phamt/Desktop/best_bienso_imx_model/model_out/best_bienso_rpk/network.rpk"
LABELS_PATH = "/home/phamt/Desktop/best_bienso_imx_model/model_out/best_bienso_rpk/labels.txt"

# Camera settings - FULL HD RESOLUTION FOR MAXIMUM QUALITY
RESOLUTION_WIDTH = 1920
RESOLUTION_HEIGHT = 1080
CAMERA_FPS = 30

# Detection settings - GIẢM FPS để tránh lag OCR
DETECTION_FPS = 15  # Giảm xuống 15 để OCR không overload Pi 5
DETECTION_THRESHOLD = 0.3  # Giảm để test (was 0.55)
IOU_THRESHOLD = 0.65
MAX_DETECTIONS = 10

# Aspect ratio filter - Biển số phải nằm ngang
MIN_PLATE_ASPECT_RATIO = 1.5  # width/height > 1.5 (biển số VN: 2.0-4.5)

# Visual settings
BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255)
TEXT_BG_COLOR = (0, 255, 0)
BOX_THICKNESS = 2
TEXT_FONT_SCALE = 0.5
TEXT_FONT_THICKNESS = 1

COLOR_MODE = 'single'

# Performance settings - TẬN DỤNG IMX500, GIẢM CPU
MAX_FRAME_QUEUE_SIZE = 1  # Drop frames aggressively - chỉ giữ latest
MAX_DETECTION_QUEUE_SIZE = 1  # Chỉ metadata, không cần buffer nhiều

# OCR settings - CHỈ DÙNG TFLite hoặc ONNX (KHÔNG dùng PaddleOCR vì quá chậm)
ENABLE_OCR = True  # BẬT OCR để nhận diện text biển số
OCR_TYPE = "tflite"  # Chọn: "tflite" (fastest) hoặc "onnx" (fast alternative)
OCR_CONFIDENCE_THRESHOLD = 0.3  # Minimum confidence để accept OCR result
OCR_FRAME_SKIP = 10  # Chạy OCR mỗi N frames (10 = mỗi ~0.7s với 15 FPS detection)

# TFLite OCR model (RECOMMENDED - fastest cho Pi 5, ~30-50ms)
TFLITE_OCR_MODEL_PATH = None  # ví dụ: "backend/models/plate_ocr.tflite"
# Set to None nếu chưa có model → OCR sẽ BỊ TẮT (detect plate nhưng không đọc text)

# ONNX OCR model (Alternative fast option, ~50-100ms)
ONNX_OCR_MODEL_PATH = "/home/phamt/Desktop/parkAI/backend/models/ocr.onnx"  # ví dụ: "backend/models/plate_ocr.onnx"
# Nếu cả TFLite và ONNX đều None → OCR sẽ BỊ TẮT

# Server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# Barrier settings - Logic đóng/mở barrier
BARRIER_CLOSE_DELAY = 10  # Đóng barrier sau 10 giây không thấy xe
# ===========================================================================
