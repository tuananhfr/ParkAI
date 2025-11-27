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
from barrier_controller import BarrierController
from central_sync import CentralSyncService

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
parking_manager = None
barrier_controller = None
central_sync = None

# WebRTC
pcs = set()


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
@app.on_event("startup")
async def startup():
    global camera_manager, detection_service, ocr_service, parking_manager, barrier_controller, central_sync
    
    try:
        # QUAN TRỌNG: Set event loop cho WebSocket manager
        loop = asyncio.get_running_loop()
        websocket_manager.set_event_loop(loop)
        
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
        
        # Initialize parking manager
        print("💾 Initializing parking manager...")
        parking_manager = ParkingManager(db_file=config.DB_FILE)
        print(f"✅ Parking manager ready")

        # Initialize barrier controller
        print("🚪 Initializing barrier controller...")
        barrier_controller = BarrierController(
            enabled=config.BARRIER_ENABLED,
            gpio_pin=config.BARRIER_GPIO_PIN,
            auto_close_time=config.BARRIER_AUTO_CLOSE_TIME
        )
        print(f"✅ Barrier controller ready")

        # Initialize central sync service
        if config.CENTRAL_SYNC_ENABLED:
            print("🌐 Initializing central sync service...")
            central_sync = CentralSyncService(
                central_url=config.CENTRAL_SERVER_URL,
                camera_id=config.CAMERA_ID,
                camera_name=config.CAMERA_NAME,
                camera_type=config.CAMERA_TYPE
            )
            central_sync.start()
            print(f"✅ Central sync ready (URL: {config.CENTRAL_SERVER_URL})")
        else:
            print("⚠️  Central sync disabled")

        # Initialize detection service
        detection_service = DetectionService(
            camera_manager,
            websocket_manager,
            ocr_service
        )
        detection_service.start()

    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()

@app.on_event("shutdown")
async def shutdown():
    global camera_manager, detection_service, barrier_controller

    if detection_service:
        detection_service.stop()

    if camera_manager:
        camera_manager.stop()

    if barrier_controller:
        barrier_controller.cleanup()

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
        await pc.setLocalDescription(answer)

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
        await pc.setLocalDescription(answer)

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


# ==================== Parking Management API ====================

@app.post("/api/open-barrier")
async def open_barrier(request: Request):
    """
    User nhấn nút mở cửa

    Body: {
        "plate_text": "30G56789",
        "confidence": 0.92,
        "source": "auto" | "manual"
    }
    """
    global parking_manager, barrier_controller, central_sync

    try:
        data = await request.json()

        plate_text = data.get('plate_text', '').strip()
        confidence = data.get('confidence', 0.0)
        source = data.get('source', 'manual')

        if not plate_text:
            return JSONResponse({
                "success": False,
                "error": "Biển số không được để trống"
            }, status_code=400)

        # Process entry với config của camera này
        result = parking_manager.process_entry(
            plate_text=plate_text,
            camera_id=config.CAMERA_ID,
            camera_type=config.CAMERA_TYPE,
            camera_name=config.CAMERA_NAME,
            confidence=confidence,
            source=source
        )

        if not result['success']:
            return JSONResponse(result, status_code=400)

        # Mở barrier
        if barrier_controller and config.BARRIER_ENABLED:
            barrier_controller.open_barrier()

        # Sync to central server
        if central_sync:
            event_type = "ENTRY" if config.CAMERA_TYPE == "ENTRY" else "EXIT"
            central_sync.send_event(event_type, {
                "plate_text": plate_text,
                "plate_id": result.get('plate_id'),
                "confidence": confidence,
                "source": source,
                "action": result.get('action'),
                "entry_id": result.get('entry_id')
            })

        return JSONResponse({
            **result,
            "barrier_opened": config.BARRIER_ENABLED,
            "camera_info": {
                "id": config.CAMERA_ID,
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE
            }
        })

    except Exception as e:
        print(f"❌ Error in open_barrier: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/history")
async def get_history(limit: int = 100, today_only: bool = False, status: str = None):
    """Lấy lịch sử xe vào/ra"""
    global parking_manager

    try:
        history = parking_manager.get_history(
            limit=limit,
            today_only=today_only,
            status=status
        )
        stats = parking_manager.get_stats()

        return JSONResponse({
            "success": True,
            "count": len(history),
            "stats": stats,
            "history": history
        })
    except Exception as e:
        print(f"❌ Error in get_history: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/stats")
async def get_stats():
    """Thống kê"""
    global parking_manager

    try:
        stats = parking_manager.get_stats()
        return JSONResponse({
            "success": True,
            **stats
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/camera/info")
async def camera_info():
    """Thông tin camera này"""
    return JSONResponse({
        "success": True,
        "camera": {
            "id": config.CAMERA_ID,
            "name": config.CAMERA_NAME,
            "type": config.CAMERA_TYPE,
            "location": config.CAMERA_LOCATION
        }
    })


@app.get("/api/barrier/status")
async def barrier_status():
    """Trạng thái barrier"""
    global barrier_controller

    if barrier_controller:
        return JSONResponse({
            "success": True,
            **barrier_controller.get_status()
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Barrier controller not initialized"
        }, status_code=500)


# ==================== Run Server ====================
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )