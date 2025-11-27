"""
Main FastAPI Application
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import uvicorn
import asyncio
import numpy as np

import config
from camera_manager import CameraManager
from detection_service import DetectionService
from ocr_service import OCRService
from websocket_manager import WebSocketManager
from parking_manager import ParkingManager 

# ==================== FastAPI App ====================
app = FastAPI(title="License Plate Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Global Instances ====================
camera_manager = None
detection_service = None
ocr_service = None
websocket_manager = WebSocketManager()
parking_manager = ParkingManager() 

# WebRTC
pcs = set()

# Latest OCR results - for real-time API
latest_plates = []  # Lưu danh sách biển số mới nhất (max 10)
MAX_PLATES_HISTORY = 10

# Barrier state - Mở/đóng barrier tự động
barrier_state = {
    "open": False,
    "plate_text": None,
    "status": None,
    "time": None,
    "message": None,
    "last_seen": 0  # Timestamp lần cuối thấy xe
}


def add_plate_detection(plate_text, confidence, bbox, timestamp):
    global latest_plates, barrier_state
    import time

    # Process với parking_manager để lấy status (IN/OUT)
    parking_result = parking_manager.process_plate(plate_text)

    # Tạo plate_data với thông tin đầy đủ
    plate_data = {
        "text": plate_text,
        "confidence": confidence,
        "bbox": bbox,
        "timestamp": timestamp,
        "status": parking_result['status'] if parking_result else None,
        "time": parking_result['time'] if parking_result else None,
        "message": parking_result['message'] if parking_result else None
    }

    latest_plates.insert(0, plate_data)
    if len(latest_plates) > MAX_PLATES_HISTORY:
        latest_plates = latest_plates[:MAX_PLATES_HISTORY]

    # QUAN TRỌNG: CẬP NHẬT BARRIER (Không phụ thuộc parking_result cooldown)
    # Barrier chỉ cần biết có xe hay không
    if parking_result:
        # Lần đầu detect xe → Cập nhật thông tin (dùng text đã format từ parking_result)
        print(f"🅿️  {parking_result['message']}")
        barrier_state["open"] = True
        barrier_state["plate_text"] = parking_result['text']  # plate_view đã format (89A-4969)
        barrier_state["status"] = parking_result['status']
        barrier_state["time"] = parking_result['time']
        barrier_state["message"] = parking_result['message']
        barrier_state["last_seen"] = time.time()

        # Broadcast plate state qua WebSocket
        websocket_manager.broadcast_plate_state({
            "barrier_open": True,
            "text": barrier_state["plate_text"],
            "status": barrier_state["status"],
            "time": barrier_state["time"],
            "message": barrier_state["message"]
        })
    else:
        # Không có parking_result (trong cooldown hoặc OCR lỗi)
        # Kiểm tra xem có phải xe đang ở barrier không
        current_plate_id, current_display = parking_manager.validate_plate(plate_text)

        if current_plate_id and barrier_state.get("open"):
            # Lấy plate_view từ history để so sánh
            history = parking_manager.get_history_list()
            for record in history:
                if record['plate_id'] == current_plate_id and record['status'] == 'IN':
                    # Đúng xe đang ở barrier → Reset timer
                    barrier_state["last_seen"] = time.time()
                    break

def _ocr_state():
    """Trả về trạng thái OCR hiện tại cho API"""
    if not config.ENABLE_OCR:
        return {
            "enabled": False,
            "ready": False,
            "type": "none",
            "provider": None,
            "error": "disabled_in_config"
        }

    if ocr_service and ocr_service.is_ready():
        return {
            "enabled": True,
            "ready": True,
            "type": ocr_service.ocr_type,
            "provider": ocr_service.ocr_provider,
            "error": None
        }

    return {
        "enabled": True,
        "ready": False,
        "type": getattr(ocr_service, "ocr_type", "none"),
        "provider": getattr(ocr_service, "ocr_provider", None),
        "error": getattr(ocr_service, "error", "not_initialized")
    }

# ==================== WebRTC Video Track ====================
class CameraVideoTrack(VideoStreamTrack):
    """Video track - chỉ stream raw camera"""
    kind = "video"

    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager
        self.frame_count = 0

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = self.camera_manager.get_raw_frame()

        if frame is None or frame.size == 0:
            frame = np.zeros(
                (config.RESOLUTION_HEIGHT, config.RESOLUTION_WIDTH, 3),
                dtype=np.uint8
            )
        else:
            self.frame_count += 1
            # FIX: Convert RGB to BGR (swap Red and Blue channels)
            frame = frame[:, :, ::-1]

        new_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base

        return new_frame


class AnnotatedVideoTrack(VideoStreamTrack):
    """Video track - stream annotated video (có boxes vẽ sẵn từ backend)"""
    kind = "video"

    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager
        self.frame_count = 0

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = self.camera_manager.get_annotated_frame()

        if frame is None or frame.size == 0:
            frame = np.zeros(
                (config.RESOLUTION_HEIGHT, config.RESOLUTION_WIDTH, 3),
                dtype=np.uint8
            )
        else:
            self.frame_count += 1
            # FIX: Convert RGB to BGR (swap Red and Blue channels)
            frame = frame[:, :, ::-1]

        new_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base

        return new_frame

# ==================== Startup & Shutdown ====================
async def barrier_auto_close():
    """Background task: Tự động đóng barrier sau BARRIER_CLOSE_DELAY giây"""
    global barrier_state
    import time

    while True:
        await asyncio.sleep(1)  # Check mỗi giây

        if barrier_state["open"]:
            now = time.time()
            elapsed = now - barrier_state["last_seen"]

            if elapsed >= config.BARRIER_CLOSE_DELAY:
                # Đã quá 10s không thấy xe → Đóng barrier
                print(f"🚧 Barrier đóng (xe đã đi qua)")
                barrier_state["open"] = False
                barrier_state["plate_text"] = None
                barrier_state["status"] = None
                barrier_state["time"] = None
                barrier_state["message"] = None

                # Broadcast barrier closed qua WebSocket
                websocket_manager.broadcast_plate_state({
                    "barrier_open": False,
                    "text": None,
                    "status": None,
                    "time": None,
                    "message": None
                })

@app.on_event("startup")
async def startup():
    global camera_manager, detection_service, ocr_service

    try:
        # QUAN TRỌNG: Set event loop cho WebSocket manager
        loop = asyncio.get_running_loop()
        websocket_manager.set_event_loop(loop)

        # Start background task: Barrier auto-close
        asyncio.create_task(barrier_auto_close())
        
        # Initialize camera
        camera_manager = CameraManager(config.MODEL_PATH, config.LABELS_PATH)
        camera_manager.start()
        
        # Initialize OCR
        if config.ENABLE_OCR:
            print("🔍 Initializing OCR service...")
            ocr_service = OCRService()
            if ocr_service.is_ready():
                status = ocr_service.get_status()
                print(f"✅ OCR ready: {status['type']} ({status['provider']})")
            else:
                status = ocr_service.get_status()
                print(f"❌ OCR failed: {status['error']}")
        else:
            print("⚠️  OCR disabled in config")
            ocr_service = None
        
        # Initialize detection service
        detection_service = DetectionService(
            camera_manager,
            websocket_manager,
            ocr_service,
            plate_callback=add_plate_detection  # Truyền callback function
        )
        detection_service.start()
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()

@app.on_event("shutdown")
async def shutdown():
    global camera_manager, detection_service
    
    if detection_service:
        detection_service.stop()
    
    if camera_manager:
        camera_manager.stop()
    
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    

# ==================== HTTP Routes ====================
@app.get("/")
async def index():
    return {
        "status": "running",
        "camera": "ready" if camera_manager else "not ready",
        "video_fps": config.CAMERA_FPS,
        "detection_fps": config.DETECTION_FPS,
        "ocr": _ocr_state()
    }

@app.get("/api/status")
async def status():
    return {
        "status": "running",
        "camera": "ready" if camera_manager else "not ready",
        "resolution": f"{config.RESOLUTION_WIDTH}x{config.RESOLUTION_HEIGHT}",
        "video_fps": config.CAMERA_FPS,
        "detection_fps": config.DETECTION_FPS,
        "ocr_enabled": config.ENABLE_OCR,
        "ocr_ready": bool(ocr_service and ocr_service.is_ready()),
        "ocr_status": _ocr_state(),
        "model": config.MODEL_PATH.split("/")[-1],
        "active_ws": len(websocket_manager.active_connections),
        "active_webrtc": len(pcs)
    }

@app.get("/api/plates/latest")
async def get_latest_plates():
    """Lấy danh sách biển số OCR mới nhất (real-time)"""
    global latest_plates
    return {
        "total": len(latest_plates),
        "plates": latest_plates
    }

@app.get("/api/plates/last")
async def get_last_plate():
    """Lấy barrier state (thông tin xe hiện tại đang ở barrier)"""
    global barrier_state

    if barrier_state["open"]:
        return {
            "barrier_open": True,
            "text": barrier_state["plate_text"],
            "status": barrier_state["status"],
            "time": barrier_state["time"],
            "message": barrier_state["message"]
        }
    else:
        return {
            "barrier_open": False,
            "text": None,
            "status": None,
            "time": None,
            "message": None
        }

@app.post("/offer")
async def webrtc_offer(request: Request):
    """WebRTC offer endpoint"""
    global camera_manager

    try:
        if camera_manager is None:
            return JSONResponse({"error": "Camera not ready"}, status_code=500)

        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["failed", "closed"]:
                await pc.close()
                pcs.discard(pc)

        camera_track = CameraVideoTrack(camera_manager)
        pc.addTrack(camera_track)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()

        # Modify SDP to increase bitrate for better quality BEFORE setLocalDescription
        sdp_lines = answer.sdp.split('\r\n')
        modified_sdp = []
        for line in sdp_lines:
            modified_sdp.append(line)
            # Add high bitrate after video codec line
            if line.startswith('a=rtpmap:') and 'VP8' in line:
                modified_sdp.append('b=AS:8000')  # 8 Mbps max bitrate
                modified_sdp.append('a=fmtp:' + line.split(':')[1].split(' ')[0] + ' max-fr=30;max-fs=8192')

        modified_answer = RTCSessionDescription(
            sdp='\r\n'.join(modified_sdp),
            type=answer.type
        )
        await pc.setLocalDescription(modified_answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
        
    except Exception as e:
        print(f"❌ WebRTC error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/offer-annotated")
async def webrtc_offer_annotated(request: Request):
    """WebRTC offer endpoint cho ANNOTATED video (có boxes vẽ sẵn từ backend)"""
    global camera_manager

    try:
        if camera_manager is None:
            return JSONResponse({"error": "Camera not ready"}, status_code=500)

        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["failed", "closed"]:
                await pc.close()
                pcs.discard(pc)

        # SỬ DỤNG AnnotatedVideoTrack thay vì CameraVideoTrack
        annotated_track = AnnotatedVideoTrack(camera_manager)
        pc.addTrack(annotated_track)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()

        # Modify SDP to increase bitrate for better quality BEFORE setLocalDescription
        sdp_lines = answer.sdp.split('\r\n')
        modified_sdp = []
        for line in sdp_lines:
            modified_sdp.append(line)
            # Add high bitrate after video codec line
            if line.startswith('a=rtpmap:') and 'VP8' in line:
                modified_sdp.append('b=AS:8000')  # 8 Mbps max bitrate
                modified_sdp.append('a=fmtp:' + line.split(':')[1].split(' ')[0] + ' max-fr=30;max-fs=8192')

        modified_answer = RTCSessionDescription(
            sdp='\r\n'.join(modified_sdp),
            type=answer.type
        )
        await pc.setLocalDescription(modified_answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    except Exception as e:
        print(f"❌ WebRTC (ANNOTATED) error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== WebSocket Route ====================
@app.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    """WebSocket endpoint cho detections"""
    await websocket_manager.connect(websocket)

    try:
        # Keep alive loop với ping every 10s
        while True:
            try:
                # Timeout 10s để send ping
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)

                # Handle commands
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send ping để keep connection alive
                try:
                    await websocket.send_text("ping")
                except:
                    break  # Connection lost

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        websocket_manager.disconnect(websocket)

@app.get("/api/parking-history")
async def get_history_table():
    return parking_manager.get_history_list()

# ==================== Run Server ====================
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )