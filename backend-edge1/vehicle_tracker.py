"""
Vehicle Tracker - Production-grade vehicle tracking với ByteTrack
"""
import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import supervision as sv


class VehicleStateEnum(Enum):
    """State machine cho vehicle lifecycle"""
    ENTER = "ENTER"          # Xe vừa xuất hiện trong frame
    MOVING = "MOVING"        # Xe đang di chuyển
    STOPPED = "STOPPED"      # Xe đứng yên (OCR bây giờ!)
    CAPTURING = "CAPTURING"  # Đang capture + OCR intensive (PARKING_LOT)
    PARKED = "PARKED"        # Đã finalize, xe đang đỗ (PARKING_LOT)
    LEAVING = "LEAVING"      # Xe đang rời khỏi ROI (chốt biển!)
    DONE = "DONE"            # Xe đã rời hoàn toàn (cleanup)


@dataclass
class VehicleState:
    """
    State của 1 vehicle trong hệ thống tracking

    Lifecycle: ENTER → MOVING → STOPPED → LEAVING → DONE
    """
    vehicle_id: int
    state: VehicleStateEnum = VehicleStateEnum.ENTER

    # Tracking info
    bbox_history: List[Tuple[float, float, float, float]] = field(default_factory=list)  # [(x,y,w,h), ...]
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # Plate info (link với PlateTracker)
    plate_votes: List[str] = field(default_factory=list)  # OCR results
    final_plate: Optional[str] = None
    plate_finalized: bool = False

    # Movement tracking
    stopped_since: Optional[float] = None
    movement_threshold: float = 5.0  # pixels - nếu di chuyển < 5px → coi như đứng yên
    stopped_duration_threshold: float = 0.5  # seconds - đứng yên 0.5s → state STOPPED

    # ROI tracking
    in_roi: bool = True
    left_roi_time: Optional[float] = None

    # PARKING_LOT specific fields
    captured_frame: Optional[np.ndarray] = None  # Ảnh đã capture để OCR intensive
    capture_timestamp: Optional[float] = None
    ocr_attempts: int = 0  # Số lần OCR trên ảnh captured
    max_ocr_attempts: int = 5  # OCR tối đa 5 lần

    def update_bbox(self, bbox: Tuple[float, float, float, float]):
        """
        Update bbox và tính toán movement

        Args:
            bbox: (x, y, w, h)
        """
        self.bbox_history.append(bbox)
        self.last_seen = time.time()

        # Giữ tối đa 30 bbox gần nhất (1.5s @ 20fps)
        if len(self.bbox_history) > 30:
            self.bbox_history = self.bbox_history[-30:]

    def get_current_bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """Lấy bbox mới nhất"""
        return self.bbox_history[-1] if self.bbox_history else None

    def is_stationary(self) -> bool:
        """
        Check xe có đứng yên không

        Logic: So sánh bbox hiện tại với bbox 10 frames trước
        """
        if len(self.bbox_history) < 10:
            return False

        current = self.bbox_history[-1]
        past = self.bbox_history[-10]

        # Tính khoảng cách center
        curr_center_x = current[0] + current[2] / 2
        curr_center_y = current[1] + current[3] / 2
        past_center_x = past[0] + past[2] / 2
        past_center_y = past[1] + past[3] / 2

        distance = np.sqrt((curr_center_x - past_center_x)**2 + (curr_center_y - past_center_y)**2)

        return distance < self.movement_threshold

    def update_state(self, in_roi: bool):
        """
        Update state machine

        Args:
            in_roi: Xe có trong ROI không
        """
        current_time = time.time()
        self.in_roi = in_roi

        # State transitions
        if self.state == VehicleStateEnum.ENTER:
            # ENTER → MOVING (sau 0.2s)
            if current_time - self.first_seen > 0.2:
                self.state = VehicleStateEnum.MOVING

        elif self.state == VehicleStateEnum.MOVING:
            # MOVING → STOPPED (nếu đứng yên đủ lâu)
            if self.is_stationary():
                if self.stopped_since is None:
                    self.stopped_since = current_time
                elif current_time - self.stopped_since > self.stopped_duration_threshold:
                    self.state = VehicleStateEnum.STOPPED
            else:
                self.stopped_since = None

            # MOVING → LEAVING (nếu rời ROI mà chưa đủ votes)
            if not in_roi and not self.plate_finalized:
                self.state = VehicleStateEnum.LEAVING
                self.left_roi_time = current_time

        elif self.state == VehicleStateEnum.STOPPED:
            # STOPPED → MOVING (nếu xe bắt đầu di chuyển lại)
            if not self.is_stationary():
                self.state = VehicleStateEnum.MOVING
                self.stopped_since = None

            # STOPPED → LEAVING (nếu rời ROI)
            if not in_roi:
                self.state = VehicleStateEnum.LEAVING
                self.left_roi_time = current_time

        elif self.state == VehicleStateEnum.LEAVING:
            # LEAVING → DONE (xóa ngay khi rời ROI - delay rất nhỏ 0.01s)
            # Delay cực nhỏ để finalize plate nếu cần, nhưng vẫn xóa nhanh
            if self.left_roi_time and (current_time - self.left_roi_time > 0.01):
                self.state = VehicleStateEnum.DONE
            elif self.plate_finalized:
                self.state = VehicleStateEnum.DONE

    def should_ocr(self) -> bool:
        """
        Check có nên chạy OCR không

        Logic MỚI: OCR ngay cả khi xe đang di chuyển (không cần đợi dừng)
        - ENTER: OCR ngay khi xe vừa xuất hiện (mỗi 5 frames)
        - MOVING: OCR thường xuyên khi xe di chuyển (mỗi 3 frames)
        - STOPPED: OCR liên tục (mỗi frame)
        - LEAVING: OCR khẩn cấp (mỗi frame) nếu chưa finalize
        """
        if self.plate_finalized:
            return False  # Đã đọc được biển → không OCR nữa

        if self.state == VehicleStateEnum.STOPPED:
            return True  # OCR liên tục khi xe đứng yên (mỗi frame)
        elif self.state == VehicleStateEnum.LEAVING:
            return True  # OCR khẩn cấp khi xe sắp rời đi (mỗi frame)
        elif self.state == VehicleStateEnum.MOVING:
            # OCR thường xuyên khi xe di chuyển (mỗi 3 frames thay vì 10)
            # Để đọc được biển số ngay cả khi xe đi qua nhanh
            return len(self.bbox_history) % 3 == 0
        elif self.state == VehicleStateEnum.ENTER:
            # OCR ngay khi xe vừa xuất hiện (mỗi 5 frames)
            # Để không miss nếu xe đi qua quá nhanh
            return len(self.bbox_history) % 5 == 0

        return False

    def finalize_plate(self, plate_text: str):
        """Chốt biển số cuối cùng"""
        self.final_plate = plate_text
        self.plate_finalized = True

    def should_capture(self) -> bool:
        """
        Check có nên capture ảnh tĩnh không (cho PARKING_LOT intensive OCR)

        Returns:
            True nếu cần capture ảnh mới
        """
        # Đã finalize rồi → không cần capture nữa
        if self.plate_finalized:
            return False

        # Chưa capture lần nào → capture ngay
        if self.captured_frame is None:
            return True

        # Đã capture nhưng quá lâu (> 3s) → capture lại ảnh mới
        if self.capture_timestamp and (time.time() - self.capture_timestamp > 3.0):
            return True

        return False

    def should_ocr_captured(self) -> bool:
        """
        Check có nên OCR trên ảnh đã capture không (cho PARKING_LOT intensive OCR)

        Returns:
            True nếu cần OCR trên captured frame
        """
        # Đã finalize → không cần OCR nữa
        if self.plate_finalized:
            return False

        # Chưa có ảnh capture → không thể OCR
        if self.captured_frame is None:
            return False

        # Đã OCR đủ số lần → dừng
        if self.ocr_attempts >= self.max_ocr_attempts:
            return False

        return True

    def __repr__(self):
        return (f"Vehicle({self.vehicle_id}, state={self.state.value}, "
                f"plate={self.final_plate or 'pending'}, "
                f"age={time.time() - self.first_seen:.1f}s)")


class ROI:
    """Region of Interest - vùng quan tâm để track xe"""

    def __init__(self, polygon: Optional[List[Tuple[int, int]]] = None, name: str = "ROI"):
        """
        Args:
            polygon: List of (x, y) points định nghĩa ROI
                     None = toàn bộ frame
            name: Tên ROI
        """
        self.polygon = polygon
        self.name = name

    def contains_point(self, x: float, y: float) -> bool:
        """
        Check point (x, y) có trong ROI không

        Sử dụng ray casting algorithm
        """
        if self.polygon is None:
            return True  # Không có ROI = coi như trong ROI

        # Ray casting algorithm
        n = len(self.polygon)
        inside = False

        p1x, p1y = self.polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = self.polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def contains_bbox(self, bbox: Tuple[float, float, float, float], threshold: float = 0.5) -> bool:
        """
        Check bbox có trong ROI không

        Args:
            bbox: (x, y, w, h)
            threshold: Tỷ lệ bbox phải nằm trong ROI (0.5 = 50%)

        Returns:
            True nếu >= threshold% bbox nằm trong ROI
        """
        if self.polygon is None:
            return True

        x, y, w, h = bbox

        # Check 4 góc + center
        points = [
            (x, y),              # Top-left
            (x + w, y),          # Top-right
            (x, y + h),          # Bottom-left
            (x + w, y + h),      # Bottom-right
            (x + w/2, y + h/2)   # Center
        ]

        inside_count = sum(1 for px, py in points if self.contains_point(px, py))

        return (inside_count / len(points)) >= threshold


class VehicleTracker:
    """
    Production-grade vehicle tracker với ByteTrack

    Features:
    - Multi-vehicle tracking (ByteTrack)
    - State machine per vehicle
    - ROI support
    - Plate voting integration
    """

    def __init__(self,
                 track_thresh: float = 0.5,
                 match_thresh: float = 0.8,
                 frame_rate: int = 18,
                 roi: Optional[ROI] = None):
        """
        Args:
            track_thresh: Detection confidence threshold for tracking
            match_thresh: IOU threshold for matching
            frame_rate: Camera frame rate (IMX500 = 18 FPS)
            roi: Region of interest
        """
        # ByteTrack tracker from supervision
        self.tracker = sv.ByteTrack(
            track_thresh=track_thresh,
            match_thresh=match_thresh,
            frame_rate=frame_rate
        )

        # Vehicle states
        self.vehicles: Dict[int, VehicleState] = {}

        # ROI
        self.roi = roi or ROI(polygon=None, name="FULL_FRAME")

        # Stats
        self.total_vehicles = 0
        self.active_vehicles = 0

    def update(self,
               detections: List[Tuple[float, float, float, float, float]],
               class_ids: Optional[List[int]] = None) -> Dict[int, VehicleState]:
        """
        Update tracker với detections mới

        Args:
            detections: List of (x, y, w, h, confidence)
            class_ids: List of class IDs (optional)

        Returns:
            Dict of {vehicle_id: VehicleState}
        """
        # Convert to supervision format (cho phép detections rỗng)
        # supervision expects xyxy format
        xyxy = []
        confidences = []
        for det in detections:
            x, y, w, h, conf = det
            xyxy.append([x, y, x + w, y + h])
            confidences.append(conf)

        xyxy = np.array(xyxy)
        confidences = np.array(confidences)

        # Class IDs (default to 0 if not provided)
        if class_ids is None:
            class_ids = np.zeros(len(detections), dtype=int)
        else:
            class_ids = np.array(class_ids)

        # Create Detections object
        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidences,
            class_id=class_ids
        )

        # Update ByteTrack
        sv_detections = self.tracker.update_with_detections(sv_detections)

        # Update vehicle states
        current_vehicle_ids = set()

        for i, tracker_id in enumerate(sv_detections.tracker_id):
            vehicle_id = int(tracker_id)
            current_vehicle_ids.add(vehicle_id)

            # Convert xyxy back to xywh
            x1, y1, x2, y2 = sv_detections.xyxy[i]
            x, y, w, h = x1, y1, x2 - x1, y2 - y1
            bbox = (x, y, w, h)

            # Create or update vehicle state
            if vehicle_id not in self.vehicles:
                self.vehicles[vehicle_id] = VehicleState(vehicle_id=vehicle_id)
                self.total_vehicles += 1

            vehicle = self.vehicles[vehicle_id]
            vehicle.update_bbox(bbox)

            # Check ROI
            in_roi = self.roi.contains_bbox(bbox, threshold=0.5)
            vehicle.update_state(in_roi)

        # CRITICAL FIX: Mark vehicles LOST (không còn detection) → rời ROI
        for vehicle_id, vehicle in list(self.vehicles.items()):
            if vehicle_id not in current_vehicle_ids:
                # Vehicle không còn detection → Mark rời ROI → State = LEAVING → DONE
                vehicle.update_state(in_roi=False)
                # Nếu đã finalize plate → mark DONE ngay lập tức (không cần đợi delay)
                if vehicle.plate_finalized and vehicle.state == VehicleStateEnum.LEAVING:
                    vehicle.state = VehicleStateEnum.DONE

        # Cleanup DONE vehicles
        self._cleanup_done_vehicles()

        # Update stats
        self.active_vehicles = len([v for v in self.vehicles.values() if v.state != VehicleStateEnum.DONE])

        return self.vehicles

    def _cleanup_done_vehicles(self):
        """
        Remove vehicles đã DONE

        Timeout tùy camera type:
        - ENTRY/EXIT: 0.5s (xóa nhanh)
        - PARKING_LOT: 5s (giữ lâu để finalize)
        """
        import config

        # Lấy timeout dựa vào camera type
        camera_type = getattr(config, 'CAMERA_TYPE', 'ENTRY')
        if camera_type == 'PARKING_LOT':
            cleanup_timeout = 5.0  # Parking lot: giữ 5s
        else:
            cleanup_timeout = 0.0  # Entry/Exit: xóa ngay lập tức (0.0s) khi DONE

        current_time = time.time()
        to_remove = []

        for vehicle_id, vehicle in self.vehicles.items():
            if vehicle.state == VehicleStateEnum.DONE:
                # Nếu đã finalize plate → xóa ngay lập tức
                # Nếu chưa finalize → giữ lại 0.1s để có cơ hội finalize
                timeout = 0.0 if vehicle.plate_finalized else 0.1
                if current_time - vehicle.last_seen > timeout:
                    to_remove.append(vehicle_id)

        for vehicle_id in to_remove:
            del self.vehicles[vehicle_id]

    def get_vehicles_to_ocr(self) -> List[VehicleState]:
        """
        Lấy danh sách vehicles cần OCR

        Returns:
            List of VehicleState cần OCR
        """
        return [v for v in self.vehicles.values() if v.should_ocr()]

    def get_vehicles_to_finalize(self) -> List[VehicleState]:
        """
        Lấy danh sách vehicles cần chốt biển số

        Returns:
            List of VehicleState ở state LEAVING và chưa finalize
        """
        return [v for v in self.vehicles.values()
                if v.state == VehicleStateEnum.LEAVING and not v.plate_finalized]

    def get_all_vehicles(self) -> List[VehicleState]:
        """
        Lấy tất cả vehicles để broadcast

        CHỈ trả về vehicles ĐANG ACTIVE (không phải LEAVING hoặc DONE)
        → Khi vehicle rời đi → state = LEAVING → KHÔNG broadcast → Box xóa NGAY LẬP TỨC!
        """
        return [v for v in self.vehicles.values()
                if v.state not in (VehicleStateEnum.LEAVING, VehicleStateEnum.DONE)]
