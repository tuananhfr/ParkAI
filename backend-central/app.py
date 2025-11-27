"""
Central Backend Server - Tổng hợp data từ tất cả Edge cameras
"""
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import httpx

import config
from database import CentralDatabase
from parking_state import ParkingStateManager
from camera_registry import CameraRegistry

# ==================== FastAPI App ====================
app = FastAPI(title="Central Parking Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Global Instances ====================
database = None
parking_state = None
camera_registry = None


def _get_edge_camera_config(camera_id: int) -> Dict[str, Any] | None:
    return config.EDGE_CAMERAS.get(camera_id) or config.EDGE_CAMERAS.get(str(camera_id))


def _sanitize_base_url(url: str) -> str:
    return (url or "").rstrip("/")


def _build_stream_proxy_info(camera_id: int) -> Dict[str, Any]:
    cfg = _get_edge_camera_config(camera_id)
    if not cfg or not cfg.get("base_url"):
        return {
            "available": False,
            "reason": "Chưa cấu hình EDGE_CAMERAS cho camera này"
        }

    return {
        "available": True,
        "default_mode": cfg.get("default_mode", "annotated"),
        "supports_annotated": cfg.get("supports_annotated", True)
    }


def _compose_edge_endpoint(base_url: str, path: str | None) -> str | None:
    if not base_url or not path:
        return None
    path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{path}"


def _build_control_proxy_info(camera_id: int) -> Dict[str, Any]:
    cfg = _get_edge_camera_config(camera_id)
    base_url = cfg.get("base_url") if cfg else None
    if not cfg or not base_url:
        return {
            "available": False,
            "reason": "Chưa cấu hình base_url cho camera này"
        }

    base = _sanitize_base_url(base_url)
    info_url = _compose_edge_endpoint(base, cfg.get("info_path", "/api/camera/info"))
    open_barrier_url = _compose_edge_endpoint(
        base, cfg.get("open_barrier_path", "/api/open-barrier")
    )

    return {
        "available": True,
        "base_url": base,
        "info_url": info_url,
        "open_barrier_url": open_barrier_url,
        "ws_url": cfg.get("ws_url"),
    }


def _enrich_camera_status(status: Dict[str, Any]) -> Dict[str, Any]:
    cameras = []
    for camera in status.get("cameras", []):
        camera_id = camera.get("id")
        enriched = dict(camera)
        if camera_id is not None:
            enriched["stream_proxy"] = _build_stream_proxy_info(camera_id)
            enriched["control_proxy"] = _build_control_proxy_info(camera_id)
        cameras.append(enriched)

    return {**status, "cameras": cameras}


async def _proxy_webrtc_offer(camera_id: int, payload: Dict[str, Any], annotated: bool):
    cfg = _get_edge_camera_config(camera_id)
    if not cfg or not cfg.get("base_url"):
        raise HTTPException(status_code=404, detail="edge_camera_not_configured")

    endpoint = f"{_sanitize_base_url(cfg['base_url'])}/{'offer-annotated' if annotated else 'offer'}"
    timeout = cfg.get("timeout", 10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload)
    except httpx.RequestError as err:
        print(f"❌ Edge proxy error (camera {camera_id}): {err}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "edge_unreachable",
                "message": str(err),
                "endpoint": endpoint,
            },
        ) from err

    try:
        data = response.json()
    except ValueError as err:
        raise HTTPException(
            status_code=502,
            detail="invalid_response_from_edge"
        ) from err

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data
# ==================== Startup & Shutdown ====================
@app.on_event("startup")
async def startup():
    global database, parking_state, camera_registry

    try:
        print("🚀 Starting Central Server...")

        # Initialize database
        print("💾 Initializing database...")
        database = CentralDatabase(db_file=config.DB_FILE)
        print(f"✅ Database ready: {config.DB_FILE}")

        # Initialize parking state manager
        print("🅿️  Initializing parking state manager...")
        parking_state = ParkingStateManager(database)
        print("✅ Parking state manager ready")

        # Initialize camera registry
        print("📹 Initializing camera registry...")
        camera_registry = CameraRegistry(
            database,
            heartbeat_timeout=config.CAMERA_HEARTBEAT_TIMEOUT
        )
        camera_registry.start()
        print("✅ Camera registry ready")

        print(f"✅ Central Server started on {config.SERVER_HOST}:{config.SERVER_PORT}")

    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown():
    global camera_registry

    if camera_registry:
        camera_registry.stop()

    print("👋 Central Server stopped")


# ==================== Edge API (nhận events từ Edge cameras) ====================

@app.post("/api/edge/event")
async def receive_edge_event(request: Request):
    """
    Nhận event từ Edge camera

    Body: {
        "type": "ENTRY" | "EXIT",
        "camera_id": 1,
        "camera_name": "Cổng vào A",
        "camera_type": "ENTRY",
        "timestamp": 1234567890,
        "data": {
            "plate_text": "30G56789",
            "confidence": 0.92,
            "source": "auto"
        }
    }
    """
    global parking_state

    try:
        event = await request.json()

        event_type = event.get('type')
        camera_id = event.get('camera_id')
        camera_name = event.get('camera_name')
        camera_type = event.get('camera_type')
        data = event.get('data', {})

        # Process event
        result = parking_state.process_edge_event(
            event_type=event_type,
            camera_id=camera_id,
            camera_name=camera_name,
            camera_type=camera_type,
            data=data
        )

        if result['success']:
            print(f"✅ Event processed: {event_type} from Camera {camera_id} - {result['message']}")
            return JSONResponse({"success": True, **result})
        else:
            print(f"⚠️  Event failed: {event_type} from Camera {camera_id} - {result['error']}")
            return JSONResponse(result, status_code=400)

    except Exception as e:
        print(f"❌ Error processing event: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/edge/heartbeat")
async def receive_heartbeat(request: Request):
    """
    Nhận heartbeat từ Edge camera

    Body: {
        "camera_id": 1,
        "camera_name": "Cổng vào A",
        "camera_type": "ENTRY",
        "status": "online",
        "events_sent": 123,
        "events_failed": 5,
        "timestamp": 1234567890
    }
    """
    global camera_registry

    try:
        data = await request.json()

        camera_id = data.get('camera_id')
        camera_name = data.get('camera_name')
        camera_type = data.get('camera_type')
        events_sent = data.get('events_sent', 0)
        events_failed = data.get('events_failed', 0)

        # Update heartbeat
        camera_registry.update_heartbeat(
            camera_id=camera_id,
            name=camera_name,
            camera_type=camera_type,
            events_sent=events_sent,
            events_failed=events_failed
        )

        return JSONResponse({"success": True})

    except Exception as e:
        print(f"❌ Heartbeat error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ==================== Frontend API (cho Dashboard) ====================

@app.get("/")
async def index():
    """API info"""
    return {
        "service": "Central Parking Management Server",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/status")
async def status():
    """Get system status"""
    global camera_registry, parking_state

    camera_status = _enrich_camera_status(camera_registry.get_camera_status())
    parking_stats = database.get_stats()

    return {
        "success": True,
        "cameras": camera_status,
        "parking": parking_stats
    }


@app.get("/api/cameras")
async def get_cameras():
    """Get all cameras"""
    global camera_registry

    status = _enrich_camera_status(camera_registry.get_camera_status())

    return JSONResponse({
        "success": True,
        **status
    })


@app.get("/api/parking/state")
async def get_parking_state():
    """Get current parking state (vehicles IN parking)"""
    global parking_state

    state = parking_state.get_parking_state()

    return JSONResponse({
        "success": True,
        **state
    })


@app.get("/api/parking/history")
async def get_parking_history(limit: int = 100, today_only: bool = False, status: str = None):
    """Get vehicle history"""
    global database

    history = database.get_history(limit=limit, today_only=today_only, status=status)
    stats = database.get_stats()

    return JSONResponse({
        "success": True,
        "count": len(history),
        "stats": stats,
        "history": history
    })


@app.get("/api/stats")
async def get_stats():
    """Get statistics"""
    global database

    stats = database.get_stats()

    return JSONResponse({
        "success": True,
        **stats
    })


@app.post("/api/cameras/{camera_id}/offer")
async def proxy_camera_offer(camera_id: int, request: Request, annotated: bool = False):
    """Proxy WebRTC offer tới Edge để frontend chỉ kết nối qua central"""
    payload = await request.json()
    data = await _proxy_webrtc_offer(camera_id, payload, annotated)
    return JSONResponse(data)


@app.post("/api/cameras/{camera_id}/offer-annotated")
async def proxy_camera_offer_annotated(camera_id: int, request: Request):
    """Proxy WebRTC offer (annotated video)"""
    payload = await request.json()
    data = await _proxy_webrtc_offer(camera_id, payload, annotated=True)
    return JSONResponse(data)


# ==================== Run Server ====================
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )
