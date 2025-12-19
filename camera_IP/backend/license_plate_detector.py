import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import torch
from ultralytics import YOLO


class LicensePlateDetector:
    """License plate detection service using YOLO"""

    def __init__(self, model_path: str = "models/license_plate.pt"):
        """
        Initialize the license plate detector

        Args:
            model_path: Path to YOLO model file
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load YOLO model
        print(f"[LOADING] Loading license plate detection model from {model_path}")
        self.model = YOLO(str(self.model_path))
        print(f"[LOADED] License plate detection model loaded successfully")

        # Check if CUDA is available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[DEVICE] Using device: {self.device}")

        # Print GPU info if available
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"[GPU] {gpu_name} - {gpu_mem:.1f}GB VRAM")

    def detect_from_frame(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> List[dict]:
        """
        Detect license plates in a frame

        Args:
            frame: Input image as numpy array (BGR format from cv2)
            conf_threshold: Confidence threshold for detection
            iou_threshold: IOU threshold for NMS

        Returns:
            List of detection dictionaries with keys:
            - bbox: [x1, y1, x2, y2] bounding box coordinates
            - confidence: Detection confidence score
            - class_id: Class ID (0 for license plate)
            - class_name: Class name
        """
        if frame is None or frame.size == 0:
            return []

        # Run YOLO detection
        results = self.model.predict(
            frame,
            conf=conf_threshold,
            iou=iou_threshold,
            device=self.device,
            verbose=False
        )

        detections = []

        # Process results
        for result in results:
            boxes = result.boxes

            for box in boxes:
                # Get box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                # Get confidence and class
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())

                detection = {
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": "license_plate"
                }

                detections.append(detection)

        return detections

    def detect_from_image_path(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> Tuple[List[dict], np.ndarray]:
        """
        Detect license plates from an image file

        Args:
            image_path: Path to image file
            conf_threshold: Confidence threshold for detection
            iou_threshold: IOU threshold for NMS

        Returns:
            Tuple of (detections list, original image)
        """
        # Read image
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image from {image_path}")

        # Detect
        detections = self.detect_from_frame(frame, conf_threshold, iou_threshold)

        return detections, frame

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[dict],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
        show_confidence: bool = True
    ) -> np.ndarray:
        """
        Draw bounding boxes on frame

        Args:
            frame: Input image
            detections: List of detections from detect_from_frame
            color: BGR color for bounding box
            thickness: Line thickness
            show_confidence: Whether to show confidence score

        Returns:
            Frame with drawn bounding boxes
        """
        output_frame = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            confidence = det["confidence"]

            # Draw rectangle
            cv2.rectangle(output_frame, (x1, y1), (x2, y2), color, thickness)

            # Draw label
            if show_confidence:
                label = f"License Plate {confidence:.2f}"
            else:
                label = "License Plate"

            # Get label size for background
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )

            # Draw label background
            cv2.rectangle(
                output_frame,
                (x1, y1 - label_h - 10),
                (x1 + label_w, y1),
                color,
                -1
            )

            # Draw label text
            cv2.putText(
                output_frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        return output_frame

    def detect_and_draw(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> Tuple[List[dict], np.ndarray]:
        """
        Convenience method to detect and draw in one call

        Args:
            frame: Input image
            conf_threshold: Confidence threshold
            iou_threshold: IOU threshold
            color: BGR color for boxes
            thickness: Line thickness

        Returns:
            Tuple of (detections, frame with boxes drawn)
        """
        detections = self.detect_from_frame(frame, conf_threshold, iou_threshold)
        output_frame = self.draw_detections(frame, detections, color, thickness)
        return detections, output_frame


# Global detector instance (singleton)
_detector_instance: Optional[LicensePlateDetector] = None


def get_detector() -> LicensePlateDetector:
    """Get or create the global detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LicensePlateDetector()
    return _detector_instance
