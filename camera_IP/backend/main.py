from fastapi import FastAPI, HTTPException, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional, List
import yaml
import asyncio
import aiohttp
from pathlib import Path
import os
import cv2
import numpy as np
from io import BytesIO
from license_plate_detector import get_detector
from websocket_manager import WebSocketManager
from detection_stream import DetectionStreamService
from batch_detection_service import GPUBatchDetectionService
from video_stream import VideoStreamWithDetection

app = FastAPI(title="Camera Stream API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
CONFIG_PATH = Path(__file__).parent / "go2rtc.yaml"
PORT = 5000

# In-memory cache
config_cache = None
is_writing = False
write_queue = []

# WebSocket Manager
websocket_manager = WebSocketManager()

# Detection Stream Service
# Chọn service phù hợp:
# - DetectionStreamService: Threading (đơn giản, CPU friendly)
# - GPUBatchDetectionService: GPU Batch Processing (tối ưu GPU, production)
USE_GPU_BATCH = True  # Set False để dùng threading service cũ

if USE_GPU_BATCH:
    detection_service = GPUBatchDetectionService(websocket_manager)
    print("[MAIN] Using GPU Batch Detection Service (optimized for 1-8 cameras)")
else:
    detection_service = DetectionStreamService(websocket_manager)
    print("[MAIN] Using Threading Detection Service (simple)")


# Pydantic models
class CameraMetadata(BaseModel):
    name: str
    type: str = "rtsp"


class Camera(BaseModel):
    id: str
    name: str
    type: str
    url: str


class CameraCreate(BaseModel):
    id: str
    url: str
    name: Optional[str] = None
    type: str = "rtsp"


class CameraUpdate(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None


class DetectionResult(BaseModel):
    bbox: List[int]
    confidence: float
    class_id: int
    class_name: str


class DetectionResponse(BaseModel):
    detections: List[DetectionResult]
    count: int
    processing_time_ms: float


# Config management functions
def load_config_sync():
    """Load config into memory at startup"""
    global config_cache
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_cache = yaml.safe_load(f) or {}
        if "streams" not in config_cache:
            config_cache["streams"] = {}
        if "metadata" not in config_cache:
            config_cache["metadata"] = {}
        print("[OK] Config loaded into memory")
        return config_cache
    except Exception as e:
        print(f"Error reading config: {e}")
        config_cache = {"streams": {}, "metadata": {}}
        return config_cache


def read_config() -> dict:
    """Read config from memory (fast!)"""
    global config_cache
    if config_cache is None:
        load_config_sync()
    return config_cache


async def write_config(config: dict):
    """Write config to file (async with queue to prevent race conditions)"""
    global config_cache, is_writing, write_queue

    # Update cache immediately
    config_cache = config

    # Queue the write operation
    future = asyncio.Future()
    write_queue.append((config, future))

    # Process queue if not already processing
    if not is_writing:
        asyncio.create_task(process_write_queue())

    return await future


async def process_write_queue():
    """Process write queue sequentially"""
    global is_writing, write_queue

    if is_writing or len(write_queue) == 0:
        return

    is_writing = True

    while write_queue:
        config, future = write_queue.pop(0)

        try:
            yaml_str = yaml.dump(config, allow_unicode=True, sort_keys=False, default_flow_style=False)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(yaml_str)
            future.set_result(True)
        except Exception as e:
            print(f"Error writing config: {e}")
            future.set_exception(HTTPException(status_code=500, detail="Failed to write config file"))

    is_writing = False


async def add_stream_to_runtime(stream_id: str, url: str):
    """Add stream to go2rtc runtime"""
    try:
        async with aiohttp.ClientSession() as session:
            data = {"streams": {stream_id: url}}
            async with session.patch(
                "http://localhost:1984/api/config",
                json=data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=500, detail=f"go2rtc API returned {response.status}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def remove_stream_from_runtime(stream_id: str):
    """Remove stream from go2rtc runtime"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"http://localhost:1984/api/streams/{stream_id}") as response:
                if response.status != 200:
                    raise HTTPException(status_code=500, detail=f"go2rtc API returned {response.status}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API Endpoints
@app.get("/api/cameras", response_model=List[Camera])
async def get_cameras():
    """Get all cameras"""
    try:
        config = read_config()
        streams = config.get("streams", {})
        metadata = config.get("metadata", {})

        cameras = []
        for camera_id, url in streams.items():
            if camera_id.startswith("#"):  # Ignore comments
                continue

            meta = metadata.get(camera_id, {})
            name = meta.get("name") or camera_id.replace("_", " ").title()
            cam_type = meta.get("type") or ("rtsp" if url.startswith("rtsp://") else "public")

            cameras.append(Camera(
                id=camera_id,
                name=name,
                type=cam_type,
                url=url
            ))

        return cameras
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cameras")
async def create_camera(camera: CameraCreate):
    """Add a new camera"""
    try:
        if not camera.id or not camera.url:
            raise HTTPException(status_code=400, detail="Missing id or url")

        config = read_config()

        # Initialize streams and metadata if not exists
        if "streams" not in config:
            config["streams"] = {}
        if "metadata" not in config:
            config["metadata"] = {}

        # Add low-latency params for RTSP streams
        final_url = camera.url
        if camera.type == "rtsp" and camera.url.startswith("rtsp://") and "#" not in camera.url:
            final_url = f"{camera.url}#video=copy#audio=copy"

        # Add new camera stream
        config["streams"][camera.id] = final_url

        # Add camera metadata
        config["metadata"][camera.id] = {
            "name": camera.name or camera.id,
            "type": camera.type
        }

        # Write to file
        await write_config(config)

        return {"success": True, "message": "Camera added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cameras/{camera_id}")
async def update_camera(camera_id: str, camera: CameraUpdate):
    """Update a camera"""
    try:
        config = read_config()

        if "streams" not in config or camera_id not in config["streams"]:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Update camera stream if URL changed
        if camera.url:
            final_url = camera.url
            # Add low-latency params for RTSP streams
            if camera.type == "rtsp" and camera.url.startswith("rtsp://") and "#" not in camera.url:
                final_url = f"{camera.url}#video=copy#audio=copy"
            config["streams"][camera_id] = final_url

        # Update camera metadata
        if "metadata" not in config:
            config["metadata"] = {}
        if camera_id not in config["metadata"]:
            config["metadata"][camera_id] = {}

        if camera.name is not None:
            config["metadata"][camera_id]["name"] = camera.name
        if camera.type is not None:
            config["metadata"][camera_id]["type"] = camera.type

        # Write to file
        await write_config(config)

        return {"success": True, "message": "Camera updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    """Remove a camera"""
    try:
        config = read_config()

        if "streams" not in config or camera_id not in config["streams"]:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Remove camera stream
        del config["streams"][camera_id]

        # Remove camera metadata
        if "metadata" in config and camera_id in config["metadata"]:
            del config["metadata"][camera_id]

        # Write to file
        await write_config(config)

        return {"success": True, "message": "Camera removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/api/stream/{camera_id}")
async def stream_video_with_detection(
    camera_id: str,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
):
    """
    Stream video với license plate detection overlay (vẽ trực tiếp lên frame)
    Giống backend-edge1 - không cần WebSocket hay Canvas

    Chỉ cần mở URL này trong browser hoặc <img> tag là thấy video với boxes!

    Example:
        http://localhost:5000/api/stream/camera1
        http://localhost:5000/api/stream/camera1?conf_threshold=0.2
    """
    try:
        # Lấy RTSP URL từ config
        config = read_config()
        streams = config.get("streams", {})

        if camera_id not in streams:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

        rtsp_url = streams[camera_id]

        # Tạo video stream với detection
        with VideoStreamWithDetection(rtsp_url, conf_threshold, iou_threshold) as stream:
            return StreamingResponse(
                stream.generate_frames(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")


@app.get("/api/stream/rtsp")
async def stream_rtsp_with_detection(
    rtsp_url: str,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
):
    """
    Stream video trực tiếp từ RTSP URL với detection overlay

    Example:
        http://localhost:5000/api/stream/rtsp?rtsp_url=0  (webcam)
        http://localhost:5000/api/stream/rtsp?rtsp_url=rtsp://...
    """
    try:
        with VideoStreamWithDetection(rtsp_url, conf_threshold, iou_threshold) as stream:
            return StreamingResponse(
                stream.generate_frames(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")


# License Plate Detection Endpoints
@app.post("/api/detect/upload", response_model=DetectionResponse)
async def detect_license_plate_upload(
    file: UploadFile = File(...),
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
):
    """
    Detect license plates from uploaded image file

    Args:
        file: Image file (jpg, png, etc.)
        conf_threshold: Confidence threshold (0.0 - 1.0)
        iou_threshold: IOU threshold for NMS (0.0 - 1.0)

    Returns:
        Detection results with bounding boxes and confidence scores
    """
    import time

    try:
        # Read uploaded file
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Get detector
        detector = get_detector()

        # Perform detection
        start_time = time.time()
        detections = detector.detect_from_frame(frame, conf_threshold, iou_threshold)
        processing_time = (time.time() - start_time) * 1000  # Convert to ms

        return DetectionResponse(
            detections=detections,
            count=len(detections),
            processing_time_ms=round(processing_time, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@app.post("/api/detect/upload/visualize")
async def detect_and_visualize_upload(
    file: UploadFile = File(...),
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    color_r: int = 0,
    color_g: int = 255,
    color_b: int = 0,
    thickness: int = 2
):
    """
    Detect license plates and return image with drawn bounding boxes

    Args:
        file: Image file (jpg, png, etc.)
        conf_threshold: Confidence threshold (0.0 - 1.0)
        iou_threshold: IOU threshold for NMS (0.0 - 1.0)
        color_r: Red channel (0-255)
        color_g: Green channel (0-255)
        color_b: Blue channel (0-255)
        thickness: Line thickness

    Returns:
        Image with bounding boxes drawn
    """
    try:
        # Read uploaded file
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Get detector
        detector = get_detector()

        # Detect and draw
        color = (color_b, color_g, color_r)  # BGR format
        detections, output_frame = detector.detect_and_draw(
            frame, conf_threshold, iou_threshold, color, thickness
        )

        # Encode image to JPEG
        success, encoded_image = cv2.imencode('.jpg', output_frame)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to encode image")

        # Return as streaming response
        return StreamingResponse(
            BytesIO(encoded_image.tobytes()),
            media_type="image/jpeg",
            headers={"X-Detection-Count": str(len(detections))}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@app.post("/api/detect/rtsp", response_model=DetectionResponse)
async def detect_license_plate_rtsp(
    rtsp_url: str,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
):
    """
    Detect license plates from RTSP stream (single frame)

    Args:
        rtsp_url: RTSP URL
        conf_threshold: Confidence threshold (0.0 - 1.0)
        iou_threshold: IOU threshold for NMS (0.0 - 1.0)

    Returns:
        Detection results from single frame
    """
    import time

    try:
        # Open RTSP stream
        cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Failed to open RTSP stream")

        # Read one frame
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise HTTPException(status_code=400, detail="Failed to read frame from RTSP stream")

        # Get detector
        detector = get_detector()

        # Perform detection
        start_time = time.time()
        detections = detector.detect_from_frame(frame, conf_threshold, iou_threshold)
        processing_time = (time.time() - start_time) * 1000

        return DetectionResponse(
            detections=detections,
            count=len(detections),
            processing_time_ms=round(processing_time, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


# WebSocket Endpoints
@app.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    """
    WebSocket endpoint for real-time license plate detections
    Client connects and receives detection messages in format:
    {
        "type": "detections",
        "data": [
            {
                "class": "license_plate",
                "confidence": 0.95,
                "bbox": [x, y, w, h],
                "camera_id": "camera1",
                "frame_id": 123,
                "timestamp": 1234567890.123
            }
        ]
    }
    """
    await websocket_manager.connect(websocket)
    try:
        # Keep connection alive and wait for client disconnect
        while True:
            # Receive any message from client (just to keep connection alive)
            data = await websocket.receive_text()
            # Echo back or ignore
            pass
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS ERROR] {e}")
        websocket_manager.disconnect(websocket)


@app.post("/api/detection/start/{camera_id}")
async def start_camera_detection(
    camera_id: str,
    rtsp_url: Optional[str] = None,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45
):
    """
    Start real-time detection for a camera

    Args:
        camera_id: Unique camera identifier
        rtsp_url: RTSP URL or camera index (0, 1, 2...). If not provided, will lookup from config
        conf_threshold: Confidence threshold (0.0-1.0)
        iou_threshold: IOU threshold for NMS (0.0-1.0)

    Returns:
        Success status
    """
    try:
        # If no RTSP URL provided, lookup from config
        if not rtsp_url:
            config = load_config_sync()
            if camera_id not in config.get("streams", {}):
                raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found in config")
            rtsp_url = config["streams"][camera_id]
            print(f"[DETECTION] Resolved RTSP URL for {camera_id}: {rtsp_url}")

        success = detection_service.start_detection(
            camera_id, rtsp_url, conf_threshold, iou_threshold
        )
        if success:
            return {"success": True, "message": f"Detection started for camera {camera_id}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to start detection")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detection/stop/{camera_id}")
async def stop_camera_detection(camera_id: str):
    """
    Stop real-time detection for a camera

    Args:
        camera_id: Camera identifier

    Returns:
        Success status
    """
    try:
        success = detection_service.stop_detection(camera_id)
        if success:
            return {"success": True, "message": f"Detection stopped for camera {camera_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/detection/stats")
async def get_detection_stats():
    """
    Get detection statistics for all active cameras

    Returns:
        Dictionary with stats for each camera
    """
    return detection_service.get_stats()


@app.on_event("startup")
async def startup_event():
    """Load config into memory at startup"""
    # Set event loop for WebSocket manager
    loop = asyncio.get_event_loop()
    websocket_manager.set_event_loop(loop)

    config = load_config_sync()
    stream_count = len(config.get("streams", {}))
    print(f"[STARTED] Backend API running on http://localhost:{PORT}")
    print(f"[CONFIG] Config file: {CONFIG_PATH}")
    print(f"[CAMERAS] Loaded {stream_count} cameras")
    print(f"[WS] WebSocket endpoint: ws://localhost:{PORT}/ws/detections")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    detection_service.stop_all()
    print("[SHUTDOWN] Detection service stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
