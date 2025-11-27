"""
Debug script - Test detection service
"""
import time
import config
from camera_manager import CameraManager
from detection_service import DetectionService
from websocket_manager import WebSocketManager

print("=" * 60)
print("🐛 DEBUG MODE - Testing Detection")
print("=" * 60)

# Initialize camera
print("\n1️⃣ Initializing camera...")
camera_manager = CameraManager(config.MODEL_PATH, config.LABELS_PATH)
camera_manager.start()

# Initialize websocket manager (without event loop for testing)
print("\n2️⃣ Initializing WebSocket manager...")
websocket_manager = WebSocketManager()

# Initialize detection service
print("\n3️⃣ Initializing detection service...")
detection_service = DetectionService(
    camera_manager,
    websocket_manager,
    ocr_service=None
)

print("\n4️⃣ Starting detection...")
detection_service.start()

print("\n▶️  Detection running... Press Ctrl+C to stop")
print("=" * 60)

try:
    while True:
        time.sleep(1)
        # Print stats every second
        if detection_service.total_detections > 0:
            print(f"📊 Detections: {detection_service.total_detections} | "
                  f"FPS: {detection_service.fps} | "
                  f"Frames: {detection_service.total_frames}")
        else:
            print(f"⏳ Waiting for detections... FPS: {detection_service.fps}")

except KeyboardInterrupt:
    print("\n\n🛑 Stopping...")
    detection_service.stop()
    camera_manager.stop()
    print("✅ Stopped")
