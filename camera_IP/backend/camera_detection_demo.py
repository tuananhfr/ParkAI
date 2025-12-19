"""
Real-time license plate detection from camera
Vẽ bounding box trực tiếp lên video stream
"""
import cv2
import argparse
from license_plate_detector import get_detector


def main():
    parser = argparse.ArgumentParser(description='Real-time license plate detection')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--rtsp', type=str, default=None, help='RTSP URL (e.g., rtsp://admin:pass@192.168.1.100:554/stream)')
    parser.add_argument('--conf', type=float, default=0.25, help='Confidence threshold (default: 0.25)')
    parser.add_argument('--iou', type=float, default=0.45, help='IOU threshold (default: 0.45)')
    parser.add_argument('--width', type=int, default=1280, help='Display width (default: 1280)')
    parser.add_argument('--height', type=int, default=720, help='Display height (default: 720)')
    args = parser.parse_args()

    # Load detector
    print("[INFO] Loading license plate detector...")
    detector = get_detector()
    print("[INFO] Detector loaded successfully!")

    # Open camera or RTSP stream
    if args.rtsp:
        print(f"[INFO] Opening RTSP stream: {args.rtsp}")
        cap = cv2.VideoCapture(args.rtsp)
    else:
        print(f"[INFO] Opening camera: {args.camera}")
        cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print("[ERROR] Failed to open camera/stream!")
        return

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    print("[INFO] Starting detection... Press 'q' to quit")
    print(f"[INFO] Confidence threshold: {args.conf}")
    print(f"[INFO] IOU threshold: {args.iou}")

    frame_count = 0
    detection_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Failed to read frame, retrying...")
            continue

        frame_count += 1

        # Detect license plates
        detections, output_frame = detector.detect_and_draw(
            frame,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
            color=(0, 255, 0),  # Green
            thickness=3
        )

        # Update detection count
        if len(detections) > 0:
            detection_count += len(detections)

        # Draw info on frame
        info_text = f"Frame: {frame_count} | Detections: {len(detections)}"
        cv2.putText(
            output_frame,
            info_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),  # Yellow
            2
        )

        # Draw instructions
        cv2.putText(
            output_frame,
            "Press 'q' to quit | 's' to save screenshot",
            (10, output_frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # Show frame
        cv2.imshow('License Plate Detection - Real-time', output_frame)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n[INFO] Quitting...")
            break
        elif key == ord('s'):
            filename = f"screenshot_{frame_count}.jpg"
            cv2.imwrite(filename, output_frame)
            print(f"[INFO] Screenshot saved: {filename}")

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

    print(f"\n[SUMMARY]")
    print(f"  Total frames: {frame_count}")
    print(f"  Total detections: {detection_count}")
    print(f"  Average detections per frame: {detection_count/frame_count if frame_count > 0 else 0:.2f}")


if __name__ == "__main__":
    main()
