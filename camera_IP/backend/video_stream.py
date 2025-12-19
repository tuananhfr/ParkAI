"""
Video Stream với License Plate Detection - Giống backend-edge1
Vẽ bounding boxes trực tiếp lên stream
"""
import cv2
import time
from typing import Optional
from license_plate_detector import get_detector


class VideoStreamWithDetection:
    """Stream video với detection overlay (vẽ trực tiếp lên frame)"""

    def __init__(self, rtsp_url: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        self.rtsp_url = rtsp_url
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.detector = None
        self.cap = None

    def __enter__(self):
        """Context manager entry - mở camera"""
        # Load detector
        print("[STREAM] Loading detector...")
        self.detector = get_detector()
        print("[STREAM] Detector loaded!")

        # Mở camera
        print(f"[STREAM] Opening camera: {self.rtsp_url}")

        # Strip go2rtc params (#video=copy#audio=copy) - OpenCV không hiểu cú pháp này
        clean_rtsp_url = self.rtsp_url.split('#')[0] if '#' in self.rtsp_url else self.rtsp_url
        if clean_rtsp_url != self.rtsp_url:
            print(f"[STREAM] Cleaned RTSP URL: {clean_rtsp_url}")

        if clean_rtsp_url.isdigit():
            self.cap = cv2.VideoCapture(int(clean_rtsp_url))
        else:
            self.cap = cv2.VideoCapture(clean_rtsp_url, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera: {self.rtsp_url}")

        print("[STREAM] Camera opened successfully")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - đóng camera"""
        if self.cap:
            self.cap.release()
            print("[STREAM] Camera released")

    def generate_frames(self):
        """
        Generator để stream frames với detection overlay
        Yields JPEG frames với bounding boxes đã vẽ sẵn
        """
        frame_count = 0
        detection_count = 0

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("[WARNING] Failed to read frame, retrying...")
                time.sleep(0.1)
                continue

            frame_count += 1

            try:
                # Detect license plates
                detections, output_frame = self.detector.detect_and_draw(
                    frame,
                    conf_threshold=self.conf_threshold,
                    iou_threshold=self.iou_threshold,
                    color=(0, 255, 0),  # Green
                    thickness=3
                )

                if len(detections) > 0:
                    detection_count += len(detections)
                    print(f"[STREAM] Frame {frame_count}: Detected {len(detections)} plate(s)")

                # Vẽ thông tin lên frame
                info_text = f"Frame: {frame_count} | Detections: {len(detections)}"
                cv2.putText(
                    output_frame,
                    info_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),  # Yellow
                    2
                )

                # Encode frame thành JPEG
                ret, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    continue

                # Yield frame dưới dạng multipart/x-mixed-replace
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            except Exception as e:
                print(f"[ERROR] Detection error: {e}")
                # Nếu lỗi detection, vẫn stream frame gốc
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            # Throttle để tránh CPU quá tải
            time.sleep(0.033)  # ~30 FPS
