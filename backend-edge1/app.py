"""
Main FastAPI Application
"""
from typing import Set
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import uvicorn
import asyncio
import json
import numpy as np
import os
from pathlib import Path
import cv2
import time

import config
import httpx
from camera_manager import CameraManager
from detection_service import DetectionService
from ocr_service import OCRService
from websocket_manager import WebSocketManager
from parking_manager import ParkingManager
from central_sync import CentralSyncService
from config_manager import ConfigManager

# FastAPI App
app = FastAPI(title="License Plate Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instances
camera_manager = None
detection_service = None
ocr_service = None
websocket_manager = WebSocketManager()
parking_manager = None
central_sync = None
config_manager = ConfigManager()

# WebRTC
pcs = set()


def _suppress_stun_errors(loop, context):
    """
    Suppress các InvalidStateError từ STUN transactions
    Đây là bug đã biết trong aioice - các STUN transactions vẫn chạy sau khi connection đã close
    Không ảnh hưởng đến functionality, chỉ là warning
    """
    exception = context.get('exception')
    message = context.get('message', '')
    source_traceback = str(context.get('source_traceback', ''))
    
    # Ignore InvalidStateError tu STUN transaction retries
    if exception and isinstance(exception, asyncio.InvalidStateError):
        if 'Transaction.__retry' in message or 'stun' in message.lower() or 'Transaction.__retry' in source_traceback:
            return  # Suppress loi nay
    
    # In cac loi khac nhu binh thuong
    default_handler = loop.get_exception_handler()
    if default_handler and default_handler != _suppress_stun_errors:
        default_handler(loop, context)
    else:
        # Fallback: in ra console neu khong co handler mac dinh
        if exception:
            import traceback
            traceback.print_exception(type(exception), exception, exception.__traceback__)


async def safe_close_pc(pc):
    """
    Cleanup peer connection một cách an toàn
    Đợi một chút để STUN transactions có thời gian dừng trước khi close
    """
    if pc is None:
        return
    try:
        # Doi mot chut de STUN transactions co thoi gian dung
        await asyncio.sleep(0.1)
        await pc.close()
    except Exception:
        # Ignore tat ca errors khi cleanup - co the la STUN transaction da bi cancel
        pass
    finally:
        pcs.discard(pc)


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

# WebRTC Video Track
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
            # Convert RGB to BGR (swap Red and Blue channels)
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
            # Convert RGB to BGR (swap Red and Blue channels)
            frame = frame[:, :, ::-1]

        new_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base

        return new_frame

# Startup & Shutdown
@app.on_event("startup")
async def startup():
    # Suppress STUN transaction InvalidStateError warnings
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_suppress_stun_errors)
    global camera_manager, detection_service, ocr_service, parking_manager, central_sync

    try:
        # Set event loop cho WebSocket manager
        loop = asyncio.get_running_loop()
        websocket_manager.set_event_loop(loop)

        # Initialize camera
        camera_manager = CameraManager(config.MODEL_PATH, config.LABELS_PATH)
        camera_manager.start()

        # Initialize OCR
        if config.ENABLE_OCR:
            ocr_service = OCRService()
            if not ocr_service.is_ready():
                status = ocr_service.get_status()
        else:
            ocr_service = None

        # Initialize parking manager
        parking_manager = ParkingManager(db_file=config.DB_FILE)

        # Initialize central sync service
        # Theo thiet ke: neu co CENTRAL_SERVER_URL thi tu bat sync (khong bat user tick them flag)
        if config.CENTRAL_SERVER_URL:
            central_sync = CentralSyncService(
                central_url=config.CENTRAL_SERVER_URL,
                camera_id=config.CAMERA_ID,
                camera_name=config.CAMERA_NAME,
                camera_type=config.CAMERA_TYPE,
                parking_manager=parking_manager,  # Pass parking_manager for incoming event sync
                event_loop=loop,
                history_broadcaster=broadcast_history_update
            )
            central_sync.start()
        else:
            central_sync = None

        # Initialize detection service (voi central_sync, parking_manager)
        detection_service = DetectionService(
            camera_manager,
            websocket_manager,
            ocr_service,
            central_sync,  # ← Pass central_sync de gui event len Central
            parking_manager  # ← Pass parking_manager de tu dong luu DB
        )
        detection_service.start()

    except Exception as e:
        import traceback
        traceback.print_exc()

@app.on_event("shutdown")
async def shutdown():
    global camera_manager, detection_service

    if detection_service:
        detection_service.stop()

    if camera_manager:
        camera_manager.stop()

    # Cleanup tat ca peer connections
    coros = [safe_close_pc(pc) for pc in list(pcs)]
    await asyncio.gather(*coros, return_exceptions=True)
    pcs.clear()
    

# HTTP Routes
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


# MJPEG Streaming (for PyQt6 Desktop App)

# Cache de broadcast frames den nhieu clients ma chi encode 1 lan
# Moi stream co timestamp rieng de tranh collision
_mjpeg_cache = {
    "raw": {"data": None, "timestamp": 0},
    "annotated": {"data": None, "timestamp": 0}
}

def generate_mjpeg_frames(annotated: bool = True):
    """
    Generator function để stream MJPEG frames
    SỬ DỤNG CACHE để broadcast 1 frame đến NHIỀU clients (tiết kiệm CPU!)

    Args:
        annotated: True để stream annotated frames (với boxes), False để stream raw

    Yields:
        JPEG frames in multipart format
    """
    import time

    while True:
        if camera_manager is None:
            # Return blank frame if camera not ready
            blank = np.zeros((config.RESOLUTION_HEIGHT, config.RESOLUTION_WIDTH, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', blank, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_bytes = buffer.tobytes()
        else:
            # Check cache (30 FPS = 33ms per frame)
            now = time.time()
            cache_key = "annotated" if annotated else "raw"

            # Neu cache moi hon 30ms → dung lai (broadcast)
            if _mjpeg_cache[cache_key]["data"] and (now - _mjpeg_cache[cache_key]["timestamp"]) < 0.033:
                frame_bytes = _mjpeg_cache[cache_key]["data"]
            else:
                # Encode frame moi
                if annotated:
                    frame = camera_manager.get_annotated_frame()
                else:
                    frame = camera_manager.get_raw_frame()

                if frame is None or frame.size == 0:
                    # Return blank frame if no frame available
                    blank = np.zeros((config.RESOLUTION_HEIGHT, config.RESOLUTION_WIDTH, 3), dtype=np.uint8)
                    frame = blank

                # Encode frame as JPEG (chi 1 lan!)
                # Quality 85 = good balance between size and quality
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                # Luu vao cache de broadcast
                _mjpeg_cache[cache_key]["data"] = frame_bytes
                _mjpeg_cache[cache_key]["timestamp"] = now

        # Yield frame in multipart format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # Sleep de giu ~30 FPS (khong spam qua nhanh)
        time.sleep(0.033)  # ~30 FPS


@app.get("/api/stream/raw")
async def stream_raw():
    """
    MJPEG stream endpoint - raw camera feed (no annotations)
    Perfect for PyQt6 desktop app - simple, stable, low latency

    Usage in PyQt6:
        cv2.VideoCapture("http://edge-ip:8000/api/stream/raw")
    """
    return StreamingResponse(
        generate_mjpeg_frames(annotated=False),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/stream/annotated")
async def stream_annotated():
    """
    MJPEG stream endpoint - annotated feed (with detection boxes)
    Perfect for PyQt6 desktop app - simple, stable, low latency

    Usage in PyQt6:
        cv2.VideoCapture("http://edge-ip:8000/api/stream/annotated")
    """
    return StreamingResponse(
        generate_mjpeg_frames(annotated=True),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/offer")
async def webrtc_offer(request: Request):
    """WebRTC offer endpoint"""
    global camera_manager

    pc = None
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
                await safe_close_pc(pc)

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
        import traceback
        traceback.print_exc()
        # Cleanup peer connection neu co loi
        await safe_close_pc(pc)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cameras/{camera_id}/offer")
async def webrtc_offer_with_id(camera_id: int, request: Request, annotated: bool = Query(False)):
    """WebRTC offer endpoint với camera_id (tương thích với frontend)"""
    try:
        # Edge chi co 1 camera, nen bo qua camera_id va goi endpoint chinh
        if annotated:
            return await webrtc_offer_annotated(request)
        else:
            return await webrtc_offer(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cameras/{camera_id}/offer-annotated")
async def webrtc_offer_annotated_with_id(camera_id: int, request: Request):
    """WebRTC offer endpoint (annotated) với camera_id (tương thích với frontend)"""
    try:
        # Edge chi co 1 camera, nen bo qua camera_id va goi endpoint chinh
        return await webrtc_offer_annotated(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/offer-annotated")
async def webrtc_offer_annotated(request: Request):
    """WebRTC offer endpoint cho ANNOTATED video (có boxes vẽ sẵn từ backend)"""
    global camera_manager

    pc = None
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
                await safe_close_pc(pc)

        # SU DUNG AnnotatedVideoTrack thay vi CameraVideoTrack
        annotated_track = AnnotatedVideoTrack(camera_manager)
        pc.addTrack(annotated_track)

        await pc.setRemoteDescription(offer)
        # Tao SDP answer
        # NOTE: Khong chinh sua SDP de tranh bug aiortc khi ca hai dau deu la aiortc
        # (ValueError: None is not in list trong and_direction).
        # Neu can control bitrate, nen lam bang cach khac an toan hon.
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Cleanup peer connection neu co loi
        await safe_close_pc(pc)
        return JSONResponse({"error": str(e)}, status_code=500)

# WebSocket Route
@app.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    """WebSocket endpoint cho detections"""
    await websocket_manager.connect(websocket)

    try:
        # Keep alive loop voi ping every 10s
        while True:
            try:
                # Timeout 10s de send ping
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)

                # Handle commands
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send ping de keep connection alive
                try:
                    await websocket.send_text("ping")
                except:
                    break  # Connection lost

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        websocket_manager.disconnect(websocket)


# Parking Management API

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
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/stats")
async def get_stats():
    """Thống kê"""
    global parking_manager

    try:
        raw_stats = parking_manager.get_stats()

        # Chuan hoa format giong backend central de frontend dung chung hook useStats
        # raw_stats tu edge Database.get_stats() hien tai co dang:
        # {
        # "total_all_time": ...,
        # "today_total": ...,
        # "today_in": ...,
        # "today_out": ...,
        # "today_fee": ...,
        # "vehicles_inside": ...
        # }
        entries_today = raw_stats.get("today_in", 0)
        exits_today = raw_stats.get("today_out", 0)
        vehicles_in_parking = raw_stats.get("vehicles_inside", 0)
        revenue_today = raw_stats.get("today_fee", 0)

        return JSONResponse({
            "success": True,
            "entries_today": entries_today,
            "exits_today": exits_today,
            "vehicles_in_parking": vehicles_in_parking,
            "revenue_today": revenue_today,
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


@app.get("/api/config")
async def get_config():
    """Lấy config hiện tại"""
    global config_manager
    try:
        config_data = config_manager.get_config()
        return JSONResponse({
            "success": True,
            "config": config_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/edge/init-sync")
async def init_sync_with_central(request: Request):
    """
    Khởi tạo sync với Central server
    Được gọi từ Central khi thêm camera mới

    Body: {
        "central_url": "http://192.168.0.144:8000",
        "camera_id": 1
    }
    """
    global config_manager, central_sync

    try:
        data = await request.json()
        central_url = data.get("central_url")
        camera_id = data.get("camera_id")

        if not central_url:
            return JSONResponse({
                "success": False,
                "error": "central_url is required"
            }, status_code=400)

        # Update CENTRAL_SERVER_URL trong config
        update_success = config_manager.update_config({
            "central": {
                "server_url": central_url,
                "sync_enabled": True
            },
            "camera": {
                "id": camera_id
            } if camera_id else {}
        })

        if not update_success:
            return JSONResponse({
                "success": False,
                "error": "Failed to update config"
            }, status_code=500)

        # Reload config
        import importlib
        importlib.reload(config)

        # Restart central_sync service neu da co
        if central_sync:
            central_sync.stop()

        # Khoi tao central_sync service moi
        from central_sync import CentralSyncService
        loop = asyncio.get_running_loop()
        central_sync = CentralSyncService(
            central_url=config.CENTRAL_SERVER_URL,
            camera_id=config.CAMERA_ID,
            camera_name=config.CAMERA_NAME,
            camera_type=config.CAMERA_TYPE,
            parking_manager=parking_manager,
            event_loop=loop,
            history_broadcaster=broadcast_history_update
        )
        central_sync.start()

        print(f"[Edge] Sync với Central enabled: {central_url}")

        return JSONResponse({
            "success": True,
            "message": f"Sync with Central enabled: {central_url}",
            "camera_id": config.CAMERA_ID,
            "camera_name": config.CAMERA_NAME
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/config")
async def update_config(request: Request):
    """Cập nhật config"""
    global config_manager, central_sync

    try:
        new_config = await request.json()
        success = config_manager.update_config(new_config)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to update configuration"
            }, status_code=500)

        # Reload config module
        import importlib
        importlib.reload(config)

        # Cap nhat central_sync neu camera_type thay doi
        if central_sync and "camera" in new_config and "type" in new_config["camera"]:
            central_sync.camera_type = config.CAMERA_TYPE
        
        # SYNC CONFIG TO CENTRAL
        # Neu co central server URL, gui config den central
        if config.CENTRAL_SERVER_URL:
            try:
                import httpx
                # Lay IP thuc te cua edge
                edge_ip = config_manager._get_local_ip()
                if config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
                    edge_ip = config.SERVER_HOST
                
                # Chuan bi config de sync
                sync_config = {
                    "edge_cameras": {
                        "1": {
                            "name": config.CAMERA_NAME,
                            "ip": edge_ip,
                            "camera_type": config.CAMERA_TYPE
                        }
                    }
                }
                
                # Gui den central
                central_url = config.CENTRAL_SERVER_URL.rstrip("/")
                sync_endpoint = f"{central_url}/api/edge/sync-config"
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(sync_endpoint, json=sync_config)
                    if response.status_code == 200:
                        print(f"[Config Sync] Đã sync config đến central: {central_url}")
                    else:
                        print(f"[Config Sync] Lỗi sync đến central: HTTP {response.status_code}")
            except Exception as e:
                print(f"[Config Sync] Không thể sync config đến central: {e}")
        
        return JSONResponse({
            "success": True,
            "message": "Configuration updated successfully",
            "config": config_manager.get_config()
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/plate-image/{filename}")
async def get_plate_image(filename: str):
    """
    Serve plate image từ file system

    Frontend có thể access: http://edge-ip:5000/api/plate-image/29A12345_1732867234.jpg
    """
    # Security: Chi cho phep filename, khong cho phep path traversal
    filename = os.path.basename(filename)

    # Build full path
    filepath = os.path.join("data", "plates", filename)

    # Check file exists
    if os.path.exists(filepath) and os.path.isfile(filepath):
        return FileResponse(filepath, media_type="image/jpeg")
    else:
        return JSONResponse({
            "error": "Image not found",
            "filename": filename
        }, status_code=404)


# Frontend API (Compatible with Central)

@app.get("/api/parking/history")
async def get_parking_history(
    limit: int = 100,
    offset: int = 0,
    today_only: bool = False,
    status: str = None,
    search: str = None,
    in_parking_only: bool = False,
    entries_only: bool = False
):
    """
    Get parking history (compatible với Central API)

    Args:
        limit: Số records
        offset: Skip N records
        today_only: Chỉ lấy hôm nay
        status: Filter theo status (IN | OUT)
        search: Search theo plate_id hoặc plate_view
        in_parking_only: Chỉ lấy xe đang trong bãi (status='IN' và exit_time IS NULL)
        entries_only: Lấy tất cả các lần vào (không filter thêm)
    """
    global parking_manager

    try:
        history = parking_manager.db.get_history(
            limit=limit,
            offset=offset,
            today_only=today_only,
            status=status,
            search=search,
            in_parking_only=in_parking_only,
            entries_only=entries_only
        )
        stats = parking_manager.db.get_stats()

        return JSONResponse({
            "success": True,
            "count": len(history),
            "stats": stats,
            "history": history
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/parking/history/{history_id}")
async def update_history_entry(history_id: int, request: Request):
    """Update biển số trong history entry (compatible với Central API)"""
    global parking_manager

    try:
        data = await request.json()
        new_plate_id = data.get("plate_id")
        new_plate_view = data.get("plate_view")

        if not new_plate_id or not new_plate_view:
            return JSONResponse({
                "success": False,
                "error": "plate_id và plate_view là bắt buộc"
            }, status_code=400)

        success = parking_manager.db.update_history_entry(
            history_id=history_id,
            new_plate_id=new_plate_id,
            new_plate_view=new_plate_view
        )

        if success:
            # Lấy event_id để sync chính xác sang central (dựa trên event_id chung)
            event_info = parking_manager.db.get_entry_event_info(history_id) if parking_manager else None
            event_id = event_info.get("event_id") if event_info else None

            # Broadcast update cho frontend
            try:
                await broadcast_history_update({"type": "updated", "history_id": history_id})
            except Exception as e:
                print(f"Failed to broadcast history update (updated): {e}")

            # Sync to Central (nếu có)
            if central_sync:
                update_event_data = {
                    "type": "UPDATE",
                    "history_id": history_id,
                    "event_id": event_id,
                    "plate_text": new_plate_id,
                    "plate_view": new_plate_view
                }
                central_sync.send_event("UPDATE", update_event_data)

            return JSONResponse({"success": True})
        else:
            return JSONResponse({
                "success": False,
                "error": "Không tìm thấy entry hoặc lỗi khi cập nhật"
            }, status_code=404)

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.delete("/api/parking/history/{history_id}")
async def delete_history_entry(history_id: int):
    """Delete history entry (compatible với Central API)"""
    global parking_manager

    try:
        success = parking_manager.db.delete_history_entry(history_id)

        if success:
            # Lấy event_id để central map đúng bản ghi
            event_info = parking_manager.db.get_entry_event_info(history_id) if parking_manager else None
            event_id = event_info.get("event_id") if event_info else None
            plate_id = event_info.get("plate_id") if event_info else None
            plate_view = event_info.get("plate_view") if event_info else None

            # Broadcast delete cho frontend
            try:
                await broadcast_history_update({"type": "deleted", "history_id": history_id})
            except Exception as e:
                print(f"Failed to broadcast history update (deleted): {e}")

            # Sync to Central (nếu có)
            if central_sync:
                delete_event_data = {
                    "type": "DELETE",
                    "history_id": history_id,
                    "event_id": event_id,
                    "plate_text": plate_id,
                    "plate_view": plate_view
                }
                central_sync.send_event("DELETE", delete_event_data)

            return JSONResponse({"success": True})
        else:
            return JSONResponse({
                "success": False,
                "error": "Không tìm thấy entry hoặc lỗi khi xóa"
            }, status_code=404)

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/parking/history/changes")
async def get_history_changes(
    limit: int = 100,
    offset: int = 0,
):
    """Get lịch sử thay đổi (giống central)"""
    global parking_manager

    try:
        changes = parking_manager.db.get_history_changes(limit=limit, offset=offset)
        return JSONResponse({
            "success": True,
            "count": len(changes),
            "changes": changes,
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/cameras")
async def get_cameras():
    """
    Get camera list (Edge chỉ có 1 camera)
    Compatible với Central API
    """
    global camera_manager, config_manager

    try:
        # Edge chi co 1 camera
        is_running = camera_manager and camera_manager.running if camera_manager else False

        # Lay IP thuc te cua may edge tu config_manager
        edge_ip = config_manager._get_local_ip()
        # Neu SERVER_HOST la mot IP cu the (khong phai 0.0.0.0), dung no
        if config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
            edge_ip = config.SERVER_HOST

        # Build base URL cho edge camera
        base_url = f"http://{edge_ip}:{config.SERVER_PORT}"
        ws_url = f"ws://{edge_ip}:{config.SERVER_PORT}/ws/detections"

        # Build stream_proxy info
        stream_proxy = {
            "available": True,
            "default_mode": "annotated",  # Edge hỗ trợ annotated
            "supports_annotated": True
        }

        # Build control_proxy info
        control_proxy = {
            "available": True,
            "base_url": base_url,
            "info_url": f"{base_url}/api/camera/info",
            "ws_url": ws_url
        }

        camera_data = {
            "id": 1,
            "name": getattr(config, "CAMERA_NAME", "Camera 1"),
            "ip": edge_ip,  # IP thực tế của máy edge
            "camera_type": getattr(config, "CAMERA_TYPE", "ENTRY"),
            "status": "online" if is_running else "offline",
            "type": getattr(config, "CAMERA_TYPE", "ENTRY"),
            "last_heartbeat": None,
            "events_sent": 0,
            "events_failed": 0,
            "stream_proxy": stream_proxy,
            "control_proxy": control_proxy
        }

        return JSONResponse({
            "success": True,
            "total": 1,
            "online": 1 if is_running else 0,
            "offline": 0 if is_running else 1,
            "cameras": [camera_data]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# WebSocket & Realtime Updates (Compatible with Central)

# Global WebSocket clients
history_websocket_clients: Set[WebSocket] = set()
camera_websocket_clients: Set[WebSocket] = set()


async def broadcast_history_update(event_data: dict):
    """
    Broadcast history update tới tất cả WebSocket clients (giống logic central)
    event_data có thể chứa:
      - event_type: ENTRY/EXIT/updated/deleted
      - history_id, plate_id, plate_view, fee, ...
    """
    if not history_websocket_clients:
        return

    import json as _json

    message = _json.dumps({
        "type": "history_update",
        "data": event_data,
    })

    disconnected = set()
    for client in list(history_websocket_clients):
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    for client in disconnected:
        history_websocket_clients.discard(client)


@app.websocket("/ws/history")
async def websocket_history_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time history updates"""
    await websocket.accept()
    history_websocket_clients.add(websocket)

    try:
        # Keep connection alive and listen for close
        while True:
            # Wait for messages (or ping/pong)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        history_websocket_clients.discard(websocket)


@app.websocket("/ws/cameras")
async def websocket_camera_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time camera status updates"""
    global camera_manager, config_manager

    await websocket.accept()
    camera_websocket_clients.add(websocket)

    # Send initial camera status immediately
    try:
        is_running = camera_manager and camera_manager.running if camera_manager else False
        
        # Lay IP thuc te cua may edge tu config_manager
        edge_ip = config_manager._get_local_ip()
        # Neu SERVER_HOST la mot IP cu the (khong phai 0.0.0.0), dung no
        if config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
            edge_ip = config.SERVER_HOST
        
        camera_data = {
            "id": 1,
            "name": getattr(config, "CAMERA_NAME", "Camera 1"),
            "ip": edge_ip,  # IP thực tế của máy edge
            "camera_type": getattr(config, "CAMERA_TYPE", "ENTRY"),
            "status": "online" if is_running else "offline",
        }

        initial_message = json.dumps({
            "type": "cameras_update",
            "data": {
                "cameras": [camera_data],
                "total": 1,
                "online": 1 if is_running else 0,
                "offline": 0 if is_running else 1
            }
        })
        await websocket.send_text(initial_message)

        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        camera_websocket_clients.discard(websocket)


# Staff & Subscription Management

@app.get("/api/staff")
async def get_staff():
    """Get danh sách người trực từ file JSON hoặc API"""
    import os
    
    try:
        # Neu co STAFF_API_URL thi goi API, neu khong thi doc tu file JSON
        staff_api_url = getattr(config, "STAFF_API_URL", "")
        staff_json_file = getattr(config, "STAFF_JSON_FILE", "data/staff.json")
        
        if staff_api_url and staff_api_url.strip():
            # Goi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(staff_api_url)
                if response.status_code == 200:
                    staff_data = response.json()
                    staff_list = staff_data if isinstance(staff_data, list) else staff_data.get("staff", [])
                    
                    # Luu vao file JSON de dung lam cache/fallback
                    json_path = os.path.join(os.path.dirname(__file__), staff_json_file)
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(staff_list, f, ensure_ascii=False, indent=2)
                    
                    return JSONResponse({
                        "success": True,
                        "staff": staff_list,
                        "source": "api"
                    })
                else:
                    # Neu API loi, fallback ve file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Doc tu file JSON (fake data)
            json_path = os.path.join(os.path.dirname(__file__), staff_json_file)
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    staff_data = json.load(f)
                return JSONResponse({
                    "success": True,
                    "staff": staff_data,
                    "source": "file"
                })
            else:
                return JSONResponse({
                    "success": False,
                    "error": f"File {staff_json_file} not found"
                }, status_code=404)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/staff")
async def update_staff(request: Request):
    """Update danh sách người trực trong file JSON"""
    import os
    
    try:
        data = await request.json()
        staff_list = data.get("staff", [])
        
        # Validate staff list
        if not isinstance(staff_list, list):
            return JSONResponse({
                "success": False,
                "error": "Staff must be a list"
            }, status_code=400)
        
        # Lay duong dan file JSON
        staff_json_file = getattr(config, "STAFF_JSON_FILE", "data/staff.json")
        json_path = os.path.join(os.path.dirname(__file__), staff_json_file)
        
        # Tao thu muc neu chua co
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vao file JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(staff_list, f, ensure_ascii=False, indent=2)
        
        return JSONResponse({
            "success": True,
            "message": f"Đã cập nhật {len(staff_list)} người trực"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/subscriptions")
async def get_subscriptions():
    """Get danh sách thuê bao từ file JSON hoặc API"""
    import os
    
    try:
        # Neu co SUBSCRIPTION_API_URL thi goi API, neu khong thi doc tu file JSON
        subscription_api_url = getattr(config, "SUBSCRIPTION_API_URL", "")
        subscription_json_file = getattr(config, "SUBSCRIPTION_JSON_FILE", "data/subscriptions.json")
        
        if subscription_api_url and subscription_api_url.strip():
            # Goi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(subscription_api_url)
                if response.status_code == 200:
                    subscription_data = response.json()
                    subscription_list = subscription_data if isinstance(subscription_data, list) else subscription_data.get("subscriptions", [])
                    
                    # Luu vao file JSON de dung lam cache/fallback
                    json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(subscription_list, f, ensure_ascii=False, indent=2)
                    
                    # Clear cache trong parking_manager de reload subscriptions
                    global parking_manager
                    if parking_manager:
                        parking_manager._subscription_cache = None
                        parking_manager._subscription_cache_time = None
                    
                    return JSONResponse({
                        "success": True,
                        "subscriptions": subscription_list,
                        "source": "api"
                    })
                else:
                    # Neu API loi, fallback ve file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Doc tu file JSON (fake data)
            json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    subscription_data = json.load(f)
                return JSONResponse({
                    "success": True,
                    "subscriptions": subscription_data,
                    "source": "file"
                })
            else:
                return JSONResponse({
                    "success": False,
                    "error": f"File {subscription_json_file} not found"
                }, status_code=404)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/subscriptions")
async def update_subscriptions(request: Request):
    """Update danh sách thuê bao trong file JSON"""
    import os
    
    try:
        data = await request.json()
        subscription_list = data.get("subscriptions", [])
        
        # Validate subscription list
        if not isinstance(subscription_list, list):
            return JSONResponse({
                "success": False,
                "error": "Subscriptions must be a list"
            }, status_code=400)
        
        # Lay duong dan file JSON
        subscription_json_file = getattr(config, "SUBSCRIPTION_JSON_FILE", "data/subscriptions.json")
        json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
        
        # Tao thu muc neu chua co
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vao file JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(subscription_list, f, ensure_ascii=False, indent=2)
        
        # Clear cache trong parking_manager de reload subscriptions
        global parking_manager
        if parking_manager:
            parking_manager._subscription_cache = None
            parking_manager._subscription_cache_time = None
        
        return JSONResponse({
            "success": True,
            "message": f"Đã cập nhật {len(subscription_list)} thuê bao"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/parking/fees")
async def get_parking_fees():
    """Get cấu hình phí gửi xe từ file JSON hoặc API"""
    import os
    
    try:
        # Neu co PARKING_API_URL thi goi API, neu khong thi doc tu file JSON
        parking_api_url = getattr(config, "PARKING_API_URL", "")
        parking_json_file = getattr(config, "PARKING_JSON_FILE", "data/parking_fees.json")
        
        if parking_api_url and parking_api_url.strip():
            # Goi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(parking_api_url)
                if response.status_code == 200:
                    fees_data = response.json()
                    fees_dict = fees_data if isinstance(fees_data, dict) else fees_data.get("fees", {})
                    
                    # Luu vao file JSON de dung lam cache/fallback
                    json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(fees_dict, f, ensure_ascii=False, indent=2)
                    
                    return JSONResponse({
                        "success": True,
                        "fees": fees_dict,
                        "source": "api"
                    })
                else:
                    # Neu API loi, fallback ve file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Doc tu file JSON (fake data)
            json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    fees_data = json.load(f)
                return JSONResponse({
                    "success": True,
                    "fees": fees_data,
                    "source": "file"
                })
            else:
                # Tra ve gia tri mac dinh tu config
                return JSONResponse({
                    "success": True,
                    "fees": {
                        "fee_base": getattr(config, "FEE_BASE", 0.5),
                        "fee_per_hour": getattr(config, "FEE_PER_HOUR", 25000)
                    },
                    "source": "default"
                })
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/parking/fees")
async def update_parking_fees(request: Request):
    """Update cấu hình phí gửi xe trong file JSON"""
    import os
    
    try:
        data = await request.json()
        fees_dict = data.get("fees", {})
        
        # Validate fees dict
        if not isinstance(fees_dict, dict):
            return JSONResponse({
                "success": False,
                "error": "Fees must be a dict"
            }, status_code=400)
        
        # Lay duong dan file JSON
        parking_json_file = getattr(config, "PARKING_JSON_FILE", "data/parking_fees.json")
        json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
        
        # Tao thu muc neu chua co
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vao file JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(fees_dict, f, ensure_ascii=False, indent=2)
        
        return JSONResponse({
            "success": True,
            "message": "Đã cập nhật cấu hình phí gửi xe"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/parking/manual-entry")
async def manual_entry(request: Request):
    """
    Manual entry - Nhập thủ công biển số từ frontend

    Body: {
        "plate_text": "30A12345",
        "camera_type": "ENTRY" | "EXIT" | "PARKING_LOT"
    }
    """
    global parking_manager, central_sync

    if not parking_manager:
        return JSONResponse({
            "success": False,
            "error": "Parking manager not initialized"
        }, status_code=500)

    try:
        data = await request.json()
        plate_text = data.get("plate_text")
        camera_type = data.get("camera_type", "ENTRY")

        if not plate_text:
            return JSONResponse({
                "success": False,
                "error": "plate_text is required"
            }, status_code=400)

        # Generate event_id TRƯỚC khi lưu DB (theo đúng kiến trúc Edge-primary)
        ms = int(time.time() * 1000)
        clean_plate = plate_text.strip().upper().replace(" ", "")
        event_id = f"edge-{config.CAMERA_ID}_{ms}_{clean_plate}"

        # Process entry using parking_manager
        result = parking_manager.process_entry(
            plate_text=plate_text,
            camera_id=config.CAMERA_ID,
            camera_type=camera_type,
            camera_name=config.CAMERA_NAME,
            confidence=1.0,  # Manual entry = high confidence
            source="manual",
            event_id=event_id  # Truyền event_id để lưu vào DB
        )

        if result.get("success"):
            # Determine event type for broadcast/sync (support PARKING_LOT)
            action = result.get("action")
            if camera_type == "PARKING_LOT":
                if action == "AUTO_ENTRY":
                    event_type = "ENTRY"
                elif action == "LOCATION_UPDATE":
                    event_type = "LOCATION_UPDATE"
                else:
                    event_type = "LOCATION_UPDATE"
            else:
                event_type = camera_type

            # Broadcast to frontend WebSocket clients for real-time update
            clean_result = {k: v for k, v in result.items() if not isinstance(v, bytes)}
            asyncio.create_task(broadcast_history_update({
                "event_type": event_type,
                "event_id": event_id,  # Include event_id
                "camera_id": config.CAMERA_ID,
                "camera_name": config.CAMERA_NAME,
                "camera_type": camera_type,
                **clean_result
            }))

            # Sync to Central if available (với event_id đã tạo)
            if central_sync:
                sync_data = {
                    "event_id": event_id,  # Dùng event_id đã tạo (QUAN TRỌNG!)
                    "plate_text": plate_text,
                    "plate_id": result.get("plate_id"),
                    "confidence": 1.0,
                    "source": "manual",
                    "entry_id": result.get("entry_id"),
                }

                # Add specific fields based on event type
                if event_type == "ENTRY":
                    sync_data["entry_time"] = result.get("entry_time")
                    if result.get("is_anomaly") is not None:
                        sync_data["is_anomaly"] = result.get("is_anomaly")
                    if result.get("location"):
                        sync_data["location"] = result.get("location")
                    if result.get("location_time"):
                        sync_data["location_time"] = result.get("location_time")
                elif event_type == "EXIT":
                    sync_data["entry_time"] = result.get("entry_time")
                    sync_data["duration"] = result.get("duration")
                    sync_data["fee"] = result.get("fee", 0)
                elif event_type == "LOCATION_UPDATE":
                    sync_data["location"] = result.get("location", config.CAMERA_NAME)
                    sync_data["location_time"] = result.get("location_time")
                    if result.get("is_anomaly") is not None:
                        sync_data["is_anomaly"] = result.get("is_anomaly")

                # Send to Central với CÙNG event_id đã lưu vào Edge DB
                central_sync.send_event(event_type, sync_data)

            return JSONResponse({
                "success": True,
                **result
            })
        else:
            return JSONResponse({
                "success": False,
                **result
            }, status_code=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# Run Server
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )