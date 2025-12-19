"""
Test License Plate Detection với Webcam
Chạy detection real-time từ webcam để kiểm tra performance
"""
import cv2
import time
from license_plate_detector import get_detector


def main():
    print("=" * 60)
    print("License Plate Detection - Webcam Test")
    print("=" * 60)
    print("\nControls:")
    print("  - Press 'q' to quit")
    print("  - Press 's' to save current frame")
    print("  - Press 'c' to toggle confidence threshold")
    print()

    # Load detector
    print("[LOADING] Loading license plate detector...")
    detector = get_detector()
    print("[OK] Detector loaded!\n")

    # Open webcam (0 = default camera, thử 1, 2 nếu không có camera 0)
    print("[CAMERA] Opening webcam...")
    cap = cv2.VideoCapture(0)  # Thay 0 bằng 1, 2 nếu không mở được

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam!")
        print("[TIP] Try changing VideoCapture(0) to VideoCapture(1) or VideoCapture(2)")
        return

    # Set camera resolution (optional)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

    print(f"[OK] Webcam opened: {actual_width}x{actual_height} @ {actual_fps}fps\n")

    # Detection settings
    conf_threshold = 0.25
    iou_threshold = 0.45

    # FPS calculation
    fps_counter = 0
    fps_start_time = time.time()
    current_fps = 0

    frame_count = 0
    detection_count = 0

    print("[RUNNING] Starting detection loop...")
    print("-" * 60)

    while True:
        # Read frame
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read frame")
            break

        frame_count += 1
        start_time = time.time()

        # Detect license plates
        detections = detector.detect_from_frame(
            frame,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )

        inference_time = (time.time() - start_time) * 1000  # ms

        # Draw detections
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            confidence = det['confidence']
            class_name = det['class_name']

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label
            label = f"{class_name} {confidence:.2f}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )

            # Label background
            cv2.rectangle(
                frame,
                (x1, y1 - label_h - 10),
                (x1 + label_w, y1),
                (0, 255, 0),
                -1
            )

            # Label text
            cv2.putText(
                frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

        detection_count += len(detections)

        # Calculate FPS
        fps_counter += 1
        if time.time() - fps_start_time >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_start_time = time.time()

        # Display info on frame
        info_text = [
            f"FPS: {current_fps}",
            f"Inference: {inference_time:.1f}ms",
            f"Detections: {len(detections)}",
            f"Conf: {conf_threshold:.2f}",
            f"Total: {detection_count}"
        ]

        y_offset = 30
        for text in info_text:
            cv2.putText(
                frame,
                text,
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            y_offset += 30

        # Show frame
        cv2.imshow('License Plate Detection - Webcam Test', frame)

        # Print stats every 30 frames
        if frame_count % 30 == 0:
            print(f"Frame {frame_count:4d} | FPS: {current_fps:2d} | "
                  f"Inference: {inference_time:5.1f}ms | Detections: {len(detections)}")

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\n[QUIT] Exiting...")
            break
        elif key == ord('s'):
            filename = f"detection_frame_{frame_count}.jpg"
            cv2.imwrite(filename, frame)
            print(f"\n[SAVED] Frame saved to {filename}")
        elif key == ord('c'):
            conf_threshold = 0.5 if conf_threshold == 0.25 else 0.25
            print(f"\n[CONF] Confidence threshold changed to {conf_threshold}")

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

    # Summary
    print("-" * 60)
    print("\n[SUMMARY]")
    print(f"Total frames: {frame_count}")
    print(f"Total detections: {detection_count}")
    print(f"Average FPS: {current_fps}")
    print(f"Average inference time: {inference_time:.1f}ms")
    print("\n[DONE] Test completed!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Stopped by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
