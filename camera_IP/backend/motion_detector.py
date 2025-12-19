"""
Motion Detector - Chỉ chạy YOLO khi có chuyển động
Giảm CPU từ 80% → 10-20%
"""
import cv2
import numpy as np


class MotionDetector:
    """Detect motion để trigger license plate detection"""

    def __init__(self, threshold=25, min_area=500):
        """
        Args:
            threshold: Ngưỡng diff giữa frames (0-255)
            min_area: Diện tích tối thiểu để coi là có motion (pixels)
        """
        self.threshold = threshold
        self.min_area = min_area
        self.prev_frame = None
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=False
        )

    def detect(self, frame):
        """
        Detect motion trong frame

        Args:
            frame: BGR frame từ camera

        Returns:
            bool: True nếu có motion, False nếu không
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # First frame - initialize
        if self.prev_frame is None:
            self.prev_frame = gray
            return False

        # Compute difference
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]

        # Dilate to fill gaps
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Check if any contour is large enough
        has_motion = False
        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                has_motion = True
                break

        # Update previous frame
        self.prev_frame = gray

        return has_motion

    def detect_advanced(self, frame):
        """
        Detect motion using background subtraction (better cho outdoor)

        Args:
            frame: BGR frame từ camera

        Returns:
            bool: True nếu có motion
        """
        # Apply background subtraction
        fg_mask = self.background_subtractor.apply(frame)

        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        # Count white pixels (motion)
        motion_pixels = cv2.countNonZero(fg_mask)

        # Threshold based on percentage of frame
        frame_area = frame.shape[0] * frame.shape[1]
        motion_ratio = motion_pixels / frame_area

        # Consider motion if > 1% of frame changed
        return motion_ratio > 0.01
