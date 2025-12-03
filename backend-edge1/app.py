"""
Main FastAPI Application
"""
from typing import Set
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import uvicorn
import asyncio
import json
import numpy as np
import os
from pathlib import Path

import config
import json
import httpx
from camera_manager import CameraManager
from detection_service import DetectionService
from ocr_service import OCRService
from websocket_manager import WebSocketManager
from parking_manager import ParkingManager
from barrier_controller import BarrierController
from central_sync import CentralSyncService
from config_manager import ConfigManager

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
    
    # Ignore InvalidStateError từ STUN transaction retries
    if exception and isinstance(exception, asyncio.InvalidStateError):
        if 'Transaction.__retry' in message or 'stun' in message.lower() or 'Transaction.__retry' in source_traceback:
            return  # Suppress lỗi này
    
    # In các lỗi khác như bình thường
    default_handler = loop.get_exception_handler()
    if default_handler and default_handler != _suppress_stun_errors:
        default_handler(loop, context)
    else:
        # Fallback: in ra console nếu không có handler mặc định
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
        # Đợi một chút để STUN transactions có thời gian dừng
        await asyncio.sleep(0.1)
        await pc.close()
    except Exception:
        # Ignore tất cả errors khi cleanup - có thể là STUN transaction đã bị cancel
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
    # Suppress STUN transaction InvalidStateError warnings
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_suppress_stun_errors)
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
            ocr_service = OCRService()
            if not ocr_service.is_ready():
                status = ocr_service.get_status()
        else:
            ocr_service = None
        
        # Initialize parking manager
        parking_manager = ParkingManager(db_file=config.DB_FILE)

        # Initialize barrier controller
        barrier_controller = BarrierController(
            enabled=config.BARRIER_ENABLED,
            gpio_pin=config.BARRIER_GPIO_PIN,
            auto_close_time=config.BARRIER_AUTO_CLOSE_TIME,
            websocket_manager=websocket_manager  # Push status changes qua WebSocket
        )

        # Initialize central sync service
        # Theo thiết kế: nếu có CENTRAL_SERVER_URL thì tự bật sync (không bắt user tick thêm flag)
        if config.CENTRAL_SERVER_URL:
            central_sync = CentralSyncService(
                central_url=config.CENTRAL_SERVER_URL,
                camera_id=config.CAMERA_ID,
                camera_name=config.CAMERA_NAME,
                camera_type=config.CAMERA_TYPE
            )
            central_sync.start()
        else:
            central_sync = None

        # Initialize detection service (với central_sync, barrier_controller, parking_manager)
        detection_service = DetectionService(
            camera_manager,
            websocket_manager,
            ocr_service,
            central_sync,  # ← Pass central_sync để gửi ảnh lên Central
            barrier_controller,  # ← Pass barrier_controller để mở/đóng barrier
            parking_manager  # ← Pass parking_manager để process entry tự động
        )
        detection_service.start()

    except Exception as e:
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

    # Cleanup tất cả peer connections
    coros = [safe_close_pc(pc) for pc in list(pcs)]
    await asyncio.gather(*coros, return_exceptions=True)
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

        # ===== BITRATE CONTROL: Modify SDP để set max bitrate =====
        # Thêm bitrate constraints cho video để giảm độ mờ
        sdp_lines = answer.sdp.split("\r\n")
        modified_sdp = []

        for line in sdp_lines:
            modified_sdp.append(line)
            # Thêm bitrate cho video track (sau dòng m=video)
            if line.startswith("m=video"):
                modified_sdp.append("b=AS:2500")      # 2.5 Mbps (Application Specific)
                modified_sdp.append("b=TIAS:2500000") # 2.5 Mbps (Transport Independent)

        # Create modified answer với bitrate constraints
        answer = RTCSessionDescription(
            sdp="\r\n".join(modified_sdp),
            type="answer"
        )

        await pc.setLocalDescription(answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Cleanup peer connection nếu có lỗi
        await safe_close_pc(pc)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cameras/{camera_id}/offer")
async def webrtc_offer_with_id(camera_id: int, request: Request, annotated: bool = Query(False)):
    """WebRTC offer endpoint với camera_id (tương thích với frontend)"""
    try:
        # Edge chỉ có 1 camera, nên bỏ qua camera_id và gọi endpoint chính
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
        # Edge chỉ có 1 camera, nên bỏ qua camera_id và gọi endpoint chính
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

        # SỬ DỤNG AnnotatedVideoTrack thay vì CameraVideoTrack
        annotated_track = AnnotatedVideoTrack(camera_manager)
        pc.addTrack(annotated_track)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()

        # ===== BITRATE CONTROL: Modify SDP để set max bitrate =====
        sdp_lines = answer.sdp.split("\r\n")
        modified_sdp = []

        for line in sdp_lines:
            modified_sdp.append(line)
            if line.startswith("m=video"):
                modified_sdp.append("b=AS:2500")      # 2.5 Mbps
                modified_sdp.append("b=TIAS:2500000") # 2.5 Mbps

        answer = RTCSessionDescription(
            sdp="\r\n".join(modified_sdp),
            type="answer"
        )

        await pc.setLocalDescription(answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Cleanup peer connection nếu có lỗi
        await safe_close_pc(pc)
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
        websocket_manager.disconnect(websocket)


# ==================== Parking Management API ====================

@app.post("/api/open-barrier")
async def open_barrier(request: Request):
    """
    User nhấn nút mở cửa - CHỈ MỞ BARRIER, KHÔNG LƯU DB

    Body: {
        "plate_text": "30G56789",
        "confidence": 0.92,
        "source": "auto" | "manual"
    }
    """
    global barrier_controller

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

        # ========== VALIDATE BIỂN SỐ TRƯỚC KHI MỞ BARRIER ==========
        # Validate format
        plate_id, display_text = parking_manager.validate_plate(plate_text)
        if not plate_id:
            return JSONResponse({
                "success": False,
                "error": f"Biển số không hợp lệ: {plate_text}"
            }, status_code=400)
        
        # Check trong DB theo logic cổng VÀO/RA
        existing = parking_manager.db.find_entry_in(plate_id)

        # ===== PREPARE VEHICLE INFO =====
        vehicle_info = None

        if config.CAMERA_TYPE == "ENTRY":
            # Cổng VÀO: Xe chưa có trong gara → valid
            if existing:
                return JSONResponse({
                    "success": False,
                    "error": f"Xe {display_text} đã VÀO lúc {existing['entry_time']} tại {existing['entry_camera_name']}"
                }, status_code=400)
        elif config.CAMERA_TYPE == "EXIT":
            # Cổng RA: Xe đã có trong gara → valid
            if not existing:
                return JSONResponse({
                    "success": False,
                    "error": f"Xe {display_text} không có trong gara!"
                }, status_code=400)

            # ===== TÍNH TOÁN THÔNG TIN CHO CỔNG RA =====
            from datetime import datetime

            # Check subscription
            subscription_info = parking_manager.check_subscription(plate_id)
            is_subscriber = subscription_info.get('is_subscriber', False)

            # Tính duration
            entry_time_str = existing['entry_time']
            exit_time = datetime.now()
            duration = parking_manager.calculate_duration(entry_time_str, exit_time)

            # Tính fee (0 nếu thuê bao)
            if is_subscriber:
                fee = 0
                customer_type = subscription_info.get('type', 'subscription')
            else:
                fee = parking_manager.calculate_fee(entry_time_str, exit_time)
                customer_type = "regular"

            # Prepare vehicle info
            vehicle_info = {
                "plate": display_text,
                "entry_time": entry_time_str,
                "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration,
                "fee": fee,
                "customer_type": customer_type,
                "is_subscriber": is_subscriber
            }

        # ========== FLOW ĐƠN GIẢN: CHỈ MỞ BARRIER ==========
        # Lưu thông tin tạm thời để lưu DB khi đóng barrier
        pending_entry = {
            "plate_text": plate_text,
            "confidence": confidence,
            "source": source
        }

        if barrier_controller:
            barrier_controller.open_barrier(auto_close_delay=None, pending_entry=pending_entry)

        response_data = {
            "success": True,
            "message": f"Barrier đã mở cho xe {plate_text}",
            "barrier_opened": True,
            "camera_info": {
                "id": config.CAMERA_ID,
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE
            }
        }

        # Thêm vehicle info nếu có (cổng RA)
        if vehicle_info:
            response_data["vehicle_info"] = vehicle_info

        return JSONResponse(response_data)

    except Exception as e:
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

        # Chuẩn hóa format giống backend central để frontend dùng chung hook useStats
        # raw_stats từ edge Database.get_stats() hiện tại có dạng:
        # {
        #   "total_all_time": ...,
        #   "today_total": ...,
        #   "today_in": ...,
        #   "today_out": ...,
        #   "today_fee": ...,
        #   "vehicles_inside": ...
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

        # Restart central_sync service nếu đã có
        if central_sync:
            central_sync.stop()

        # Khởi tạo central_sync service mới
        from central_sync import CentralSyncService
        central_sync = CentralSyncService(
            central_url=config.CENTRAL_SERVER_URL,
            camera_id=config.CAMERA_ID,
            camera_name=config.CAMERA_NAME,
            camera_type=config.CAMERA_TYPE
        )
        central_sync.start()

        print(f"✅ [Edge] Sync với Central enabled: {central_url}")

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

        # Cập nhật central_sync nếu camera_type thay đổi
        if central_sync and "camera" in new_config and "type" in new_config["camera"]:
            central_sync.camera_type = config.CAMERA_TYPE
        
        # ===== SYNC CONFIG TO CENTRAL =====
        # Nếu có central server URL, gửi config đến central
        if config.CENTRAL_SERVER_URL:
            try:
                import httpx
                # Lấy IP thực tế của edge
                edge_ip = config_manager._get_local_ip()
                if config.SERVER_HOST not in ["0.0.0.0", "localhost", "127.0.0.1"]:
                    edge_ip = config.SERVER_HOST
                
                # Chuẩn bị config để sync
                sync_config = {
                    "edge_cameras": {
                        "1": {
                            "name": config.CAMERA_NAME,
                            "ip": edge_ip,
                            "camera_type": config.CAMERA_TYPE
                        }
                    }
                }
                
                # Gửi đến central
                central_url = config.CENTRAL_SERVER_URL.rstrip("/")
                sync_endpoint = f"{central_url}/api/edge/sync-config"
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(sync_endpoint, json=sync_config)
                    if response.status_code == 200:
                        print(f"✅ [Config Sync] Đã sync config đến central: {central_url}")
                    else:
                        print(f"⚠️ [Config Sync] Lỗi sync đến central: HTTP {response.status_code}")
            except Exception as e:
                print(f"⚠️ [Config Sync] Không thể sync config đến central: {e}")
        
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


@app.post("/api/close-barrier")
async def close_barrier(request: Request):
    """
    Đóng barrier từ frontend - ĐÓNG BARRIER VÀ LƯU DB
    
    Flow: Lưu DB SAU KHI barrier đóng (entry_time = thời điểm đóng)
    """
    global barrier_controller, parking_manager, central_sync

    if not barrier_controller:
        return JSONResponse({
            "success": False,
            "error": "Barrier controller not initialized"
        }, status_code=500)

    # Cho phép hoạt động ở simulation mode (BARRIER_ENABLED = False vẫn hoạt động được)
    # barrier_controller đã có simulation mode sẵn

    try:
        # Đóng barrier và lấy pending entry (nếu có)
        pending_entry = barrier_controller.close_barrier()
        
        # Nếu có pending entry → Lưu DB với entry_time = thời điểm barrier đóng
        if pending_entry:
            result = parking_manager.process_entry(
                plate_text=pending_entry["plate_text"],
                camera_id=config.CAMERA_ID,
                camera_type=config.CAMERA_TYPE,
                camera_name=config.CAMERA_NAME,
                confidence=pending_entry["confidence"],
                source=pending_entry["source"]
            )
            
            if result.get('success'):
                # Broadcast history update cho frontend (giống central)
                try:
                    event_type = "ENTRY" if config.CAMERA_TYPE == "ENTRY" else "EXIT"
                    clean_result = {
                        k: v
                        for k, v in result.items()
                        if k not in ("plate_image",) and not isinstance(v, bytes)
                    }
                    await broadcast_history_update({
                        "event_type": event_type,
                        "camera_id": config.CAMERA_ID,
                        "camera_name": config.CAMERA_NAME,
                        "camera_type": config.CAMERA_TYPE,
                        **clean_result,
                    })
                except Exception as e:
                    print(f"⚠️ Failed to broadcast history update: {e}")

                # Sync to Central (nếu có) - GỬI ĐẦY ĐỦ THÔNG TIN
                if central_sync:
                    event_type = "ENTRY" if config.CAMERA_TYPE == "ENTRY" else "EXIT"

                    # Chuẩn bị data để sync
                    sync_data = {
                        "plate_text": pending_entry["plate_text"],
                        "confidence": pending_entry["confidence"],
                        "source": pending_entry["source"],
                        "entry_id": result.get('entry_id'),  # ID từ edge DB
                    }

                    # Thêm thông tin cho ENTRY
                    if event_type == "ENTRY":
                        # Entry time sẽ được central tạo mới (thời điểm nhận event)
                        pass

                    # Thêm thông tin cho EXIT
                    elif event_type == "EXIT":
                        if result.get('entry_time'):
                            sync_data['entry_time'] = result.get('entry_time')
                        if result.get('duration'):
                            sync_data['duration'] = result.get('duration')
                        if result.get('fee') is not None:
                            sync_data['fee'] = result.get('fee')

                    central_sync.send_event(event_type, sync_data)

                return JSONResponse({
                    "success": True,
                    "message": "Barrier đã đóng và đã lưu DB",
                    "entry_saved": True,
                    "entry_id": result.get('entry_id'),
                    **barrier_controller.get_status()
                })
            else:
                return JSONResponse({
                    "success": True,
                    "message": "Barrier đã đóng nhưng không thể lưu DB",
                    "entry_saved": False,
                    "entry_error": result.get('error'),
                    **barrier_controller.get_status()
                })
        
        # Không có pending entry → Chỉ đóng barrier (có thể là đóng thủ công không có xe)
        return JSONResponse({
            "success": True,
            "message": "Barrier đã đóng",
            "entry_saved": False,
            **barrier_controller.get_status()
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
    # Security: Chỉ cho phép filename, không cho phép path traversal
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


# ==================== Frontend API (Compatible with Central) ====================

@app.get("/api/parking/history")
async def get_parking_history(
    limit: int = 100,
    offset: int = 0,
    today_only: bool = False,
    status: str = None,
    search: str = None
):
    """
    Get parking history (compatible với Central API)

    Args:
        limit: Số records
        offset: Skip N records
        today_only: Chỉ lấy hôm nay
        status: Filter theo status (IN | OUT)
        search: Search theo plate_id hoặc plate_view
    """
    global parking_manager

    try:
        history = parking_manager.db.get_history(
            limit=limit,
            offset=offset,
            today_only=today_only,
            status=status,
            search=search
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
            # Broadcast update cho frontend
            try:
                await broadcast_history_update({"type": "updated", "history_id": history_id})
            except Exception as e:
                print(f"⚠️ Failed to broadcast history update (updated): {e}")

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
            # Broadcast delete cho frontend
            try:
                await broadcast_history_update({"type": "deleted", "history_id": history_id})
            except Exception as e:
                print(f"⚠️ Failed to broadcast history update (deleted): {e}")

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
        # Edge chỉ có 1 camera
        is_running = camera_manager and camera_manager.running if camera_manager else False

        # Lấy IP thực tế của máy edge từ config_manager
        edge_ip = config_manager._get_local_ip()
        # Nếu SERVER_HOST là một IP cụ thể (không phải 0.0.0.0), dùng nó
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
            "open_barrier_url": f"{base_url}/api/open-barrier",
            "barrier_status_url": f"{base_url}/api/barrier/status",
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


# ==================== WebSocket & Realtime Updates (Compatible with Central) ====================

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
        
        # Lấy IP thực tế của máy edge từ config_manager
        edge_ip = config_manager._get_local_ip()
        # Nếu SERVER_HOST là một IP cụ thể (không phải 0.0.0.0), dùng nó
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


# ==================== Staff & Subscription Management ====================

@app.get("/api/staff")
async def get_staff():
    """Get danh sách người trực từ file JSON hoặc API"""
    import os
    
    try:
        # Nếu có STAFF_API_URL thì gọi API, nếu không thì đọc từ file JSON
        staff_api_url = getattr(config, "STAFF_API_URL", "")
        staff_json_file = getattr(config, "STAFF_JSON_FILE", "data/staff.json")
        
        if staff_api_url and staff_api_url.strip():
            # Gọi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(staff_api_url)
                if response.status_code == 200:
                    staff_data = response.json()
                    staff_list = staff_data if isinstance(staff_data, list) else staff_data.get("staff", [])
                    
                    # Lưu vào file JSON để dùng làm cache/fallback
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
                    # Nếu API lỗi, fallback về file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Đọc từ file JSON (fake data)
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
        
        # Lấy đường dẫn file JSON
        staff_json_file = getattr(config, "STAFF_JSON_FILE", "data/staff.json")
        json_path = os.path.join(os.path.dirname(__file__), staff_json_file)
        
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vào file JSON
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
        # Nếu có SUBSCRIPTION_API_URL thì gọi API, nếu không thì đọc từ file JSON
        subscription_api_url = getattr(config, "SUBSCRIPTION_API_URL", "")
        subscription_json_file = getattr(config, "SUBSCRIPTION_JSON_FILE", "data/subscriptions.json")
        
        if subscription_api_url and subscription_api_url.strip():
            # Gọi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(subscription_api_url)
                if response.status_code == 200:
                    subscription_data = response.json()
                    subscription_list = subscription_data if isinstance(subscription_data, list) else subscription_data.get("subscriptions", [])
                    
                    # Lưu vào file JSON để dùng làm cache/fallback
                    json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
                    os.makedirs(os.path.dirname(json_path), exist_ok=True)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(subscription_list, f, ensure_ascii=False, indent=2)
                    
                    # Clear cache trong parking_manager để reload subscriptions
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
                    # Nếu API lỗi, fallback về file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Đọc từ file JSON (fake data)
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
        
        # Lấy đường dẫn file JSON
        subscription_json_file = getattr(config, "SUBSCRIPTION_JSON_FILE", "data/subscriptions.json")
        json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
        
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vào file JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(subscription_list, f, ensure_ascii=False, indent=2)
        
        # Clear cache trong parking_manager để reload subscriptions
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
        # Nếu có PARKING_API_URL thì gọi API, nếu không thì đọc từ file JSON
        parking_api_url = getattr(config, "PARKING_API_URL", "")
        parking_json_file = getattr(config, "PARKING_JSON_FILE", "data/parking_fees.json")
        
        if parking_api_url and parking_api_url.strip():
            # Gọi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(parking_api_url)
                if response.status_code == 200:
                    fees_data = response.json()
                    fees_dict = fees_data if isinstance(fees_data, dict) else fees_data.get("fees", {})
                    
                    # Lưu vào file JSON để dùng làm cache/fallback
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
                    # Nếu API lỗi, fallback về file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Đọc từ file JSON (fake data)
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
                # Trả về giá trị mặc định từ config
                return JSONResponse({
                    "success": True,
                    "fees": {
                        "fee_base": getattr(config, "FEE_BASE", 0.5),
                        "fee_per_hour": getattr(config, "FEE_PER_HOUR", 25000),
                        "fee_overnight": getattr(config, "FEE_OVERNIGHT", 0),
                        "fee_daily_max": getattr(config, "FEE_DAILY_MAX", 0)
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
        
        # Lấy đường dẫn file JSON
        parking_json_file = getattr(config, "PARKING_JSON_FILE", "data/parking_fees.json")
        json_path = os.path.join(os.path.dirname(__file__), parking_json_file)
        
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vào file JSON
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


# ==================== Run Server ====================
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )