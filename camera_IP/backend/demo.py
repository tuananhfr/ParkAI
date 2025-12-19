"""
Demo đơn giản: Detect biển số từ camera và vẽ box
Chỉ cần chạy: python demo.py
"""
import cv2
from license_plate_detector import get_detector

# Cấu hình
CAMERA_INDEX = 0  # 0 = webcam mặc định, 1, 2,... = camera khác
CONFIDENCE_THRESHOLD = 0.25  # Ngưỡng confidence (0.0 - 1.0)
IOU_THRESHOLD = 0.45

def main():
    print("=" * 60)
    print("  License Plate Detection Demo - Real-time")
    print("=" * 60)

    # Load detector
    print("\n[1/3] Loading detector...")
    detector = get_detector()
    print("✅ Detector loaded!")

    # Open camera
    print(f"\n[2/3] Opening camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("❌ Failed to open camera!")
        print("\nTips:")
        print("  - Kiểm tra camera có kết nối không")
        print("  - Thử đổi CAMERA_INDEX = 1 hoặc 2")
        print("  - Nếu dùng RTSP, sửa code: cv2.VideoCapture('rtsp://...')")
        return

    print("✅ Camera opened!")

    # Set resolution (optional)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("\n[3/3] Starting detection...")
    print("\n" + "=" * 60)
    print("  INSTRUCTIONS:")
    print("  - Giơ biển số trước camera")
    print("  - Nhấn 'q' để thoát")
    print("  - Nhấn 's' để lưu ảnh screenshot")
    print("=" * 60 + "\n")

    frame_count = 0
    total_detections = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️  Failed to read frame")
            continue

        frame_count += 1

        # Detect và vẽ box
        detections, output_frame = detector.detect_and_draw(
            frame,
            conf_threshold=CONFIDENCE_THRESHOLD,
            iou_threshold=IOU_THRESHOLD,
            color=(0, 255, 0),  # Green box
            thickness=3
        )

        # Đếm detections
        num_detections = len(detections)
        total_detections += num_detections

        # Vẽ thông tin lên frame
        # Frame counter
        cv2.putText(
            output_frame,
            f"Frame: {frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),  # Cyan
            2
        )

        # Detection count
        color = (0, 255, 0) if num_detections > 0 else (0, 0, 255)  # Green if detected, red if not
        cv2.putText(
            output_frame,
            f"Detected: {num_detections}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2
        )

        # Instructions
        cv2.putText(
            output_frame,
            "Press 'q' to quit | 's' to save",
            (10, output_frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        # Hiển thị frame
        cv2.imshow('License Plate Detection', output_frame)

        # In ra console nếu detect được
        if num_detections > 0:
            print(f"[Frame {frame_count}] 🎯 Detected {num_detections} license plate(s):")
            for i, det in enumerate(detections, 1):
                bbox = det['bbox']
                conf = det['confidence']
                print(f"  {i}. BBox: {bbox}, Confidence: {conf:.2f}")

        # Xử lý phím nhấn
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\n🛑 Stopping...")
            break
        elif key == ord('s'):
            filename = f"screenshot_{frame_count}.jpg"
            cv2.imwrite(filename, output_frame)
            print(f"💾 Screenshot saved: {filename}")

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total frames processed: {frame_count}")
    print(f"  Total detections: {total_detections}")
    if frame_count > 0:
        print(f"  Detection rate: {(total_detections/frame_count)*100:.1f}%")
    print("=" * 60)
    print("\n✅ Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
