"""
Central Backend Server - Tổng hợp data từ tất cả Edge cameras
"""
from typing import Any, Dict, Set
import socket

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
import uvicorn
import httpx
import json
import asyncio

import config
from database import CentralDatabase
from parking_state import ParkingStateManager
from camera_registry import CameraRegistry
from config_manager import ConfigManager

# P2P Imports
from p2p.manager import P2PManager
from p2p.event_handler import P2PEventHandler
from p2p.parking_integration import P2PParkingBroadcaster
from p2p.sync_manager import P2PSyncManager
from p2p.database_extensions import patch_database_for_p2p
import p2p_api
import p2p_api_extensions
import edge_api

# FastAPI App
app = FastAPI(title="Central Parking Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instances
database = None
parking_state = None
camera_registry = None
config_manager = ConfigManager()

# P2P Instances
p2p_manager = None
p2p_event_handler = None
p2p_broadcaster = None
p2p_sync_manager = None

# WebSocket connections for real-time history updates
history_websocket_clients: Set[WebSocket] = set()

# WebSocket connections for real-time camera updates
camera_websocket_clients: Set[WebSocket] = set()

# WebSocket connections for Edge backends (edge_id -> WebSocket)
edge_websocket_connections: Dict[str, WebSocket] = {}


def get_local_ip() -> str:
    """
    Auto-detect local IP address
    Returns: Local IP address (e.g., "192.168.1.100")
    """
    try:
        # Create a socket connection to external DNS to find local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f" Could not auto-detect IP: {e}")
        return "127.0.0.1"  # Fallback to localhost


async def broadcast_history_update(event_data: dict):
    """Broadcast history update to all connected WebSocket clients (Frontend)"""
    if not history_websocket_clients:
        return

    message = json.dumps({
        "type": "history_update",
        "data": event_data
    })

    # Send to all clients, remove disconnected ones
    disconnected = set()
    for client in history_websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    # Remove disconnected clients
    for client in disconnected:
        history_websocket_clients.discard(client)


async def sync_event_to_edges_and_frontend(event_data: dict):
    """
    Broadcast event to both Edge backends and Frontend WebSocket clients
    Called whenever Central receives/creates new data that needs to be synced
    """
    # Broadcast to frontend WebSocket clients
    await broadcast_history_update(event_data)

    # Broadcast to Edge backends for DB sync
    if event_data.get("event_id"):
        # Convert to Edge-compatible format
        edge_event = {
            "type": event_data.get("event_type", "ENTRY"),
            "event_id": event_data["event_id"],
            "camera_id": event_data.get("camera_id"),
            "camera_name": event_data.get("camera_name", "Central"),
            "camera_type": event_data.get("camera_type", "ENTRY"),
            "data": {
                "plate_text": event_data.get("plate_id", ""),
                "plate_view": event_data.get("plate_view", ""),
                "confidence": event_data.get("confidence", 0.0),
                "source": event_data.get("source", "central")
            }
        }

        # Add entry time or exit info
        if event_data.get("entry_time"):
            edge_event["entry_time"] = event_data["entry_time"]
        if event_data.get("exit_time"):
            edge_event["exit_time"] = event_data["exit_time"]
            edge_event["fee"] = event_data.get("fee", 0)
            edge_event["duration"] = event_data.get("duration", "")

        await broadcast_to_edges(edge_event)


def _clean_camera_data(cameras):
    """Clean camera data để đảm bảo JSON serializable"""
    cleaned = []
    for cam in cameras:
        cleaned_cam = {}
        for key, value in cam.items():
            # Bo qua cac field khong can thiet hoac khong serializable
            if key in ["last_heartbeat"] and value:
                # Convert datetime string thanh ISO format neu can
                cleaned_cam[key] = str(value) if value else None
            elif isinstance(value, (str, int, float, bool, type(None))):
                cleaned_cam[key] = value
            elif isinstance(value, dict):
                cleaned_cam[key] = {k: v for k, v in value.items() if isinstance(v, (str, int, float, bool, type(None), dict))}
            elif isinstance(value, list):
                cleaned_cam[key] = [item for item in value if isinstance(item, (str, int, float, bool, type(None), dict))]
        cleaned.append(cleaned_cam)
    return cleaned


async def broadcast_camera_update():
    """Broadcast camera list update to all connected WebSocket clients"""
    if not camera_websocket_clients:
        return

    try:
        global camera_registry
        if not camera_registry:
            return
            
        status = _enrich_camera_status(camera_registry.get_camera_status())
        
        # Clean camera data de dam bao JSON serializable
        cameras = _clean_camera_data(status.get("cameras", []))

        message = json.dumps({
            "type": "cameras_update",
            "data": {
                "cameras": cameras,
                "total": status.get("total", 0),
                "online": status.get("online", 0),
                "offline": status.get("offline", 0)
            }
        })

        # Send to all clients, remove disconnected ones
        disconnected = set()
        for client in list(camera_websocket_clients):  # Copy list to avoid modification during iteration
            try:
                await client.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.add(client)

        # Remove disconnected clients
        for client in disconnected:
            camera_websocket_clients.discard(client)
    except Exception as e:
        import traceback
        print(f"Error in broadcast_camera_update: {e}")
        traceback.print_exc()


def _get_edge_camera_config(camera_id: int) -> Dict[str, Any] | None:
    """Get edge camera config - luôn lấy từ module mới nhất"""
    import config as config_module
    return config_module.EDGE_CAMERAS.get(camera_id) or config_module.EDGE_CAMERAS.get(str(camera_id))


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

    return {
        "available": True,
        "base_url": base,
        "info_url": info_url,
        "ws_url": cfg.get("ws_url"),
    }


def _enrich_camera_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich camera status với config và thêm cameras từ config chưa có trong database"""
    # Tao dict cameras tu database de de lookup
    db_cameras = {c.get("id"): c for c in status.get("cameras", [])}
    
    # Lay tat ca camera IDs tu config
    import config as config_module
    all_camera_ids = set(config_module.EDGE_CAMERAS.keys())
    
    # Merge: cameras tu database + cameras tu config (chua co trong database)
    cameras = []
    processed_ids = set()
    
    # Xu ly cameras tu database truoc
    for camera in status.get("cameras", []):
        camera_id = camera.get("id")
        if camera_id is None:
            continue
            
        enriched = dict(camera)
        processed_ids.add(camera_id)
        
        stream_proxy = _build_stream_proxy_info(camera_id)
        control_proxy = _build_control_proxy_info(camera_id)
        enriched["stream_proxy"] = stream_proxy
        enriched["control_proxy"] = control_proxy
        
        # Merge ten camera tu EDGE_CAMERAS config (override ten tu database)
        edge_config = _get_edge_camera_config(camera_id)
        if edge_config and edge_config.get("name"):
            enriched["name"] = edge_config["name"]
        if edge_config and edge_config.get("camera_type"):
            enriched["type"] = edge_config["camera_type"]
        
        # Neu camera khong co config hoac base_url khong hop le → danh dau offline ngay
        if not edge_config or not edge_config.get("base_url") or not edge_config.get("base_url").strip():
            enriched["status"] = "offline"
            enriched["config_missing"] = True
        elif not stream_proxy.get("available") or not control_proxy.get("available"):
            # Neu stream hoac control proxy khong available → IP sai hoac khong cau hinh
            enriched["status"] = "offline"
            enriched["config_invalid"] = True
        else:
            # Neu camera co config nhung khong nhan heartbeat gan day (60s) → danh dau offline
            from datetime import datetime, timedelta, timezone
            if camera.get("last_heartbeat"):
                try:
                    last_heartbeat = datetime.strptime(camera["last_heartbeat"], "%Y-%m-%d %H:%M:%S")
                    # Database luu UTC, nen dung utcnow() thay vi now()
                    time_since_heartbeat = (datetime.utcnow() - last_heartbeat).total_seconds()
                    # Neu khong nhan heartbeat trong 60 giay → danh dau offline
                    if time_since_heartbeat > 60:
                        enriched["status"] = "offline"
                        enriched["connection_lost"] = True
                    else:
                        # Nhan heartbeat gan day → online
                        enriched["status"] = "online"
                except Exception:
                    pass
        
        cameras.append(enriched)
    
    # Them cameras tu config chua co trong database (hien thi offline)
    for camera_id in all_camera_ids:
        # Normalize camera_id (co the la int hoac str tu config keys)
        camera_id_int = int(camera_id) if isinstance(camera_id, str) else camera_id
        
        # Kiem tra xem camera da duoc xu ly chua (co trong database)
        if camera_id_int in processed_ids or camera_id in processed_ids:
            continue  # Da xu ly roi
        
        edge_config = _get_edge_camera_config(camera_id_int)
        if not edge_config:
            continue
        
        # Tao camera entry mac dinh tu config
        enriched = {
            "id": camera_id_int,
            "name": edge_config.get("name", f"Camera {camera_id_int}"),
            "type": edge_config.get("camera_type", "ENTRY"),
            "status": "offline",  # Mặc định offline vì chưa có heartbeat
            "last_heartbeat": None,
            "events_sent": 0,
            "events_failed": 0,
            "location": None,
            "config_only": True,  # Flag để biết camera chỉ có trong config
        }
        
        # Build proxy info
        stream_proxy = _build_stream_proxy_info(camera_id_int)
        control_proxy = _build_control_proxy_info(camera_id_int)
        enriched["stream_proxy"] = stream_proxy
        enriched["control_proxy"] = control_proxy
        
        # Neu IP khong hop le hoac khong co config → danh dau offline
        if not edge_config.get("base_url") or not edge_config.get("base_url").strip():
            enriched["config_missing"] = True
        elif not stream_proxy.get("available") or not control_proxy.get("available"):
            enriched["config_invalid"] = True
        
        cameras.append(enriched)
    
    # Sap xep theo camera ID
    cameras.sort(key=lambda x: x.get("id", 0))
    
    # Recalculate stats
    total = len(cameras)
    online = sum(1 for c in cameras if c.get("status") == "online")
    offline = sum(1 for c in cameras if c.get("status") == "offline")
    
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "cameras": cameras
    }


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
# Startup & Shutdown
async def camera_broadcast_loop():
    """Background task để check và broadcast camera updates khi có thay đổi"""
    last_status = None
    while True:
        try:
            await asyncio.sleep(2)  # Check moi 2 giay de phan ung nhanh hon
            
            global camera_registry
            if not camera_registry:
                continue
                
            current_status = _enrich_camera_status(camera_registry.get_camera_status())
            cameras = current_status.get("cameras", [])
            
            # So sanh voi status truoc de chi broadcast khi co thay doi
            if last_status is None:
                last_status = cameras
                # Khong broadcast lan dau, chi set last_status
                continue
            
            # Check xem co thay doi khong
            status_changed = False
            if len(cameras) != len(last_status):
                status_changed = True
            else:
                for i, cam in enumerate(cameras):
                    last_cam = last_status[i] if i < len(last_status) else None
                    if not last_cam or cam.get("id") != last_cam.get("id") or cam.get("status") != last_cam.get("status"):
                        status_changed = True
                        break
            
            if status_changed:
                last_status = cameras
                await broadcast_camera_update()
                
        except Exception as e:
            import traceback
            print(f"Camera broadcast loop error: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    global database, parking_state, camera_registry
    global p2p_manager, p2p_event_handler, p2p_broadcaster, p2p_sync_manager

    try:
        # Initialize database
        database = CentralDatabase(db_file=config.DB_FILE)

        # Patch database with P2P methods
        patch_database_for_p2p(database)

        # Initialize parking state manager
        parking_state = ParkingStateManager(database)

        # Initialize camera registry
        camera_registry = CameraRegistry(
            database,
            heartbeat_timeout=config.CAMERA_HEARTBEAT_TIMEOUT
        )
        camera_registry.start()

        # Tat broadcast loop dinh ky - chi broadcast khi co thay doi tu heartbeat
        # asyncio.create_task(camera_broadcast_loop())

        # Initialize P2P System
        print("Initializing P2P system...")

        # Auto-detect and update Central IP if needed
        local_ip = get_local_ip()
        print(f"Auto-detected local IP: {local_ip}")

        # Update P2P config if IP is "auto" or "127.0.0.1"
        import os
        p2p_config_path = os.path.join("config", "p2p_config.json")
        if os.path.exists(p2p_config_path):
            with open(p2p_config_path, "r", encoding="utf-8") as f:
                p2p_config = json.load(f)

            current_ip = p2p_config.get("this_central", {}).get("ip", "")
            if current_ip in ["auto", "127.0.0.1", ""]:
                p2p_config["this_central"]["ip"] = local_ip
                with open(p2p_config_path, "w", encoding="utf-8") as f:
                    json.dump(p2p_config, f, indent=2, ensure_ascii=False)
                print(f"Updated P2P config IP: {current_ip} → {local_ip}")

        # Initialize P2P Manager
        p2p_manager = P2PManager()

        # Initialize P2P Event Handler
        p2p_event_handler = P2PEventHandler(
            database=database,
            this_central_id=p2p_manager.config.get_this_central_id(),
            on_history_update=broadcast_history_update,
            on_edge_broadcast=broadcast_to_edges,
        )

        # Initialize P2P Broadcaster
        p2p_broadcaster = P2PParkingBroadcaster(
            p2p_manager=p2p_manager,
            central_id=p2p_manager.config.get_this_central_id()
        )

        # Initialize P2P Sync Manager
        p2p_sync_manager = P2PSyncManager(
            database=database,
            p2p_manager=p2p_manager,
            central_id=p2p_manager.config.get_this_central_id()
        )

        # Set P2P event callbacks
        p2p_manager.on_vehicle_entry_pending = p2p_event_handler.handle_vehicle_entry_pending
        p2p_manager.on_vehicle_entry_confirmed = p2p_event_handler.handle_vehicle_entry_confirmed
        p2p_manager.on_vehicle_exit = p2p_event_handler.handle_vehicle_exit
        p2p_manager.on_history_update = p2p_event_handler.handle_history_update
        p2p_manager.on_history_delete = p2p_event_handler.handle_history_delete

        # Set P2P sync callbacks
        p2p_manager.on_sync_request = p2p_sync_manager.handle_sync_request
        p2p_manager.on_sync_response = p2p_sync_manager.handle_sync_response

        # Set peer connection callbacks
        p2p_manager.on_peer_connected = p2p_sync_manager.on_peer_connected
        p2p_manager.on_peer_disconnected = p2p_sync_manager.on_peer_disconnected

        # Start P2P Manager
        await p2p_manager.start()

        # Inject dependencies into API modules
        p2p_api.set_p2p_manager(p2p_manager)
        edge_api.set_dependencies(database, parking_state, p2p_broadcaster)
        p2p_api_extensions.set_database(database)

        print("P2P system initialized successfully")

    except Exception as e:
        import traceback
        print("Error during startup:")
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown():
    global camera_registry, p2p_manager

    if camera_registry:
        camera_registry.stop()

    # Stop P2P Manager
    if p2p_manager:
        print("Stopping P2P system...")
        await p2p_manager.stop()
        print("P2P system stopped")



# Edge API (nhan events tu Edge cameras)

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

        # Use provided event_id if any; else generate
        event_id = event.get("event_id")
        if not event_id and event_type in ["ENTRY", "DETECTION"]:
            if p2p_broadcaster:
                event_id = p2p_broadcaster.generate_event_id(
                    data.get("plate_text", "UNKNOWN").replace(" ", "")
                )

        # Dedupe: nếu đã có event_id này thì trả thành công luôn
        if event_id and database and database.event_exists(event_id):
            return JSONResponse({"success": True, "deduped": True, "event_id": event_id})
        # Process event
        result = parking_state.process_edge_event(
            event_type=event_type,
            camera_id=camera_id,
            camera_name=camera_name,
            camera_type=camera_type,
            data=data,
            event_id=event_id,
        )

        if result['success']:
            # Clean result de dam bao JSON serializable (loai bo bytes, BLOB objects)
            clean_result = {}
            for k, v in result.items():
                # Skip bytes/BLOB va None
                if isinstance(v, bytes) or (k == 'plate_image' and v is not None):
                    continue
                clean_result[k] = v

            # Broadcast to P2P peers if available
            if p2p_broadcaster and result.get('action'):
                try:
                    if result['action'] == 'ENTRY' and result.get('history_id'):
                        asyncio.create_task(p2p_broadcaster.broadcast_entry_pending(
                            event_id=result.get('event_id') or event_id,
                            plate_id=result['plate_id'],
                            plate_view=result['plate_view'],
                            edge_id=camera_id,
                            camera_type=camera_type,
                            direction='ENTRY',
                            entry_time=result['entry_time']
                        ))

                    elif result['action'] == 'EXIT' and result.get('history_id'):
                        asyncio.create_task(p2p_broadcaster.broadcast_exit(
                            event_id=result.get('event_id'),
                            exit_edge=camera_id,
                            exit_time=result.get('exit_time', ''),
                            fee=result.get('fee', 0),
                            duration=result.get('duration', '')
                        ))
                except Exception as e:
                    print(f"Error broadcasting P2P event: {e}")

            # Broadcast to WebSocket clients (frontend) AND Edge backends for real-time update
            asyncio.create_task(sync_event_to_edges_and_frontend({
                "event_type": event_type,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "camera_type": camera_type,
                **clean_result
            }))

            return JSONResponse({"success": True, **clean_result})
        else:
            error_msg = result.get('error', 'Unknown error')
            # Van log event vao database ngay ca khi failed de debug
            # Clean result de dam bao JSON serializable
            clean_result = {}
            for k, v in result.items():
                if isinstance(v, bytes) or (k == 'plate_image' and v is not None):
                    continue
                clean_result[k] = v
            return JSONResponse(clean_result, status_code=400)

    except Exception as e:
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

        # Broadcast camera update to WebSocket clients (ngay khi co heartbeat)
        try:
            asyncio.create_task(broadcast_camera_update())
        except Exception as broadcast_err:
            # Log but don't fail the heartbeat
            print(f"Failed to broadcast camera update: {broadcast_err}")

        return JSONResponse({"success": True})

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# Frontend API (cho Dashboard)

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
async def get_parking_history(
    limit: int = 100,
    offset: int = 0,
    today_only: bool = False,
    status: str = None,
    search: str = None,
    in_parking_only: bool = False,
    entries_only: bool = False
):
    """Get vehicle history with optional search by plate number"""
    global database

    history = database.get_history(
        limit=limit,
        offset=offset,
        today_only=today_only,
        status=status,
        search=search,
        in_parking_only=in_parking_only,
        entries_only=entries_only
    )
    stats = database.get_stats()

    return JSONResponse({
        "success": True,
        "count": len(history),
        "stats": stats,
        "history": history
    })


@app.put("/api/parking/history/{history_id}")
async def update_history_entry(history_id: int, request: Request):
    """Update biển số trong history entry"""
    global database

    try:
        data = await request.json()
        new_plate_id = data.get("plate_id")
        new_plate_view = data.get("plate_view")

        if not new_plate_id or not new_plate_view:
            return JSONResponse({
                "success": False,
                "error": "plate_id và plate_view là bắt buộc"
            }, status_code=400)

        success = database.update_history_entry(
            history_id=history_id,
            new_plate_id=new_plate_id,
            new_plate_view=new_plate_view
        )

        if success:
            # Broadcast to frontend WebSocket
            await broadcast_history_update({"type": "updated", "history_id": history_id})

            # Broadcast to Edges (đồng bộ DB)
            # TODO: Cần lấy thông tin đầy đủ của record để gửi cho Edge
            # Hiện tại chỉ gửi notification, Edge cần implement logic nhận update
            update_event = {
                "type": "UPDATE",
                "history_id": history_id,
                "data": {
                    "plate_text": new_plate_id,
                    "plate_view": new_plate_view
                }
            }
            await broadcast_to_edges(update_event)

            # Broadcast to P2P peers (other Centrals)
            if p2p_broadcaster:
                try:
                    asyncio.create_task(p2p_broadcaster.broadcast_history_update(
                        history_id=history_id,
                        plate_text=new_plate_id,
                        plate_view=new_plate_view
                    ))
                except Exception as e:
                    print(f"Error broadcasting P2P history update: {e}")

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
    """Delete history entry"""
    global database

    try:
        success = database.delete_history_entry(history_id)

        if success:
            # Broadcast to frontend WebSocket
            await broadcast_history_update({"type": "deleted", "history_id": history_id})

            # Broadcast to Edges (đồng bộ DB)
            delete_event = {
                "type": "DELETE",
                "history_id": history_id
            }
            await broadcast_to_edges(delete_event)

            # Broadcast to P2P peers (other Centrals)
            if p2p_broadcaster:
                try:
                    asyncio.create_task(p2p_broadcaster.broadcast_history_delete(
                        history_id=history_id
                    ))
                except Exception as e:
                    print(f"Error broadcasting P2P history delete: {e}")

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
    history_id: int = None
):
    """Get lịch sử thay đổi"""
    global database

    changes = database.get_history_changes(
        limit=limit,
        offset=offset,
        history_id=history_id
    )

    return JSONResponse({
        "success": True,
        "count": len(changes),
        "changes": changes
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


@app.get("/api/staff")
async def get_staff():
    """Get danh sách người trực từ file JSON hoặc API"""
    import config as config_module
    import os
    
    try:
        # Neu co STAFF_API_URL thi goi API, neu khong thi doc tu file JSON
        staff_api_url = config_module.STAFF_API_URL
        staff_json_file = config_module.STAFF_JSON_FILE
        
        if staff_api_url and staff_api_url.strip():
            # Goi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(staff_api_url)
                if response.status_code == 200:
                    staff_data = response.json()
                    return JSONResponse({
                        "success": True,
                        "staff": staff_data if isinstance(staff_data, list) else staff_data.get("staff", []),
                        "source": "api"
                    })
                else:
                    # Neu API loi, fallback ve file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Doc tu file JSON
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
    import config as config_module
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
        staff_json_file = config_module.STAFF_JSON_FILE
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
    import config as config_module
    import os
    
    try:
        # Neu co SUBSCRIPTION_API_URL thi goi API, neu khong thi doc tu file JSON
        subscription_api_url = config_module.SUBSCRIPTION_API_URL
        subscription_json_file = config_module.SUBSCRIPTION_JSON_FILE
        
        if subscription_api_url and subscription_api_url.strip():
            # Goi API external
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(subscription_api_url)
                if response.status_code == 200:
                    subscription_data = response.json()
                    return JSONResponse({
                        "success": True,
                        "subscriptions": subscription_data if isinstance(subscription_data, list) else subscription_data.get("subscriptions", []),
                        "source": "api"
                    })
                else:
                    # Neu API loi, fallback ve file JSON
                    raise Exception(f"API returned status {response.status_code}")
        else:
            # Doc tu file JSON
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
    import config as config_module
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
        subscription_json_file = config_module.SUBSCRIPTION_JSON_FILE
        json_path = os.path.join(os.path.dirname(__file__), subscription_json_file)
        
        # Tao thu muc neu chua co
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        
        # Ghi vao file JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(subscription_list, f, ensure_ascii=False, indent=2)
        
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
    import config as config_module
    import os
    
    try:
        # Neu co PARKING_API_URL thi goi API, neu khong thi doc tu file JSON
        parking_api_url = config_module.PARKING_API_URL
        parking_json_file = config_module.PARKING_JSON_FILE
        
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
                        "fee_base": getattr(config_module, "FEE_BASE", 0.5),
                        "fee_per_hour": getattr(config_module, "FEE_PER_HOUR", 25000)
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
    import config as config_module
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
        parking_json_file = config_module.PARKING_JSON_FILE
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


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    global config_manager

    try:
        cfg = config_manager.get_config()
        return JSONResponse({
            "success": True,
            "config": cfg
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration"""
    global config_manager

    try:
        new_config = await request.json()
        success = config_manager.update_config(new_config)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to update configuration"
            }, status_code=500)

        # Reload config module de ap dung thay doi ngay lap tuc
        import importlib
        import sys
        # Remove module from cache va reload
        if 'config' in sys.modules:
            del sys.modules['config']
        import config  # Re-import sau khi xoa cache
        importlib.reload(config)
        
        # Debug: Kiem tra so luong cameras sau khi reload
        print(f"[Config Update] Cameras sau khi reload: {list(config.EDGE_CAMERAS.keys())}")
        
        # Sync config to edge backends via /api/config
        sync_results = []
        if "edge_cameras" in new_config:
            import httpx
            # Lay IP cua Central server
            central_ip = get_local_ip()
            central_url = f"http://{central_ip}:{config.SERVER_PORT}"

            for cam_id, cam_config in new_config["edge_cameras"].items():
                ip = cam_config.get("ip")
                camera_type = cam_config.get("camera_type", "ENTRY")
                camera_name = cam_config.get("name", "")

                if ip:
                    try:
                        # 1. Sync camera config (type, name)
                        config_url = f"http://{ip}:5000/api/config"
                        sync_payload = {
                            "camera": {
                                "type": camera_type
                            }
                        }
                        if camera_name:
                            sync_payload["camera"]["name"] = camera_name

                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.post(config_url, json=sync_payload)

                            if response.status_code == 200:
                                # 2. Khoi tao sync voi Central (bat heartbeat)
                                init_url = f"http://{ip}:5000/api/edge/init-sync"
                                init_payload = {
                                    "central_url": central_url,
                                    "camera_id": int(cam_id) if isinstance(cam_id, str) else cam_id
                                }

                                init_response = await client.post(init_url, json=init_payload)

                                if init_response.status_code == 200:
                                    sync_results.append({
                                        "camera_id": cam_id,
                                        "success": True,
                                        "message": "Camera synced and heartbeat enabled"
                                    })
                                else:
                                    sync_results.append({
                                        "camera_id": cam_id,
                                        "success": False,
                                        "error": f"Init sync failed: HTTP {init_response.status_code}"
                                    })
                            else:
                                sync_results.append({
                                    "camera_id": cam_id,
                                    "success": False,
                                    "error": f"Config sync failed: HTTP {response.status_code}"
                                })
                    except Exception as e:
                        sync_results.append({
                            "camera_id": cam_id,
                            "success": False,
                            "error": str(e)
                        })

        # Broadcast camera update de frontend nhan camera moi ngay lap tuc
        # Su dung await de dam bao broadcast duoc gui di
        print("[Config Update] Broadcasting camera update...")
        await broadcast_camera_update()
        print("[Config Update] Broadcast completed")

        return JSONResponse({
            "success": True,
            "message": "Configuration updated successfully",
            "sync_results": sync_results
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# Edge Config Sync

@app.post("/api/edge/sync-config")
async def sync_edge_config(request: Request):
    """
    Nhận config từ edge backend và tự động thêm/cập nhật camera edge vào central
    Được gọi khi edge update config (tên camera, camera_type, hoặc thêm central server IP)
    """
    global config_manager
    
    try:
        edge_config = await request.json()
        
        # Lay thong tin edge_cameras tu request
        if "edge_cameras" not in edge_config:
            return JSONResponse({
                "success": False,
                "error": "Missing edge_cameras in request"
            }, status_code=400)
        
        edge_cameras = edge_config["edge_cameras"]
        
        # Lay config hien tai
        current_config = config_manager.get_config()
        current_edge_cameras = current_config.get("edge_cameras", {})
        
        # Cap nhat hoac them camera edge
        updated = False
        for cam_id, cam_config in edge_cameras.items():
            cam_id_int = int(cam_id) if isinstance(cam_id, str) else cam_id
            edge_ip = cam_config.get("ip")
            edge_name = cam_config.get("name", f"Camera {cam_id_int}")
            edge_type = cam_config.get("camera_type", "ENTRY")
            
            if not edge_ip:
                continue
            
            # Kiem tra xem camera da ton tai chua
            camera_exists = cam_id_int in current_edge_cameras or str(cam_id_int) in current_edge_cameras
            
            if not camera_exists:
                # Them camera moi vao config
                print(f"[Edge Sync] Thêm camera edge mới: {cam_id_int} ({edge_name}) từ {edge_ip}")
            else:
                # Cap nhat camera hien co
                current_cam = current_edge_cameras.get(cam_id_int) or current_edge_cameras.get(str(cam_id_int))
                if current_cam:
                    if current_cam.get("name") != edge_name or current_cam.get("camera_type") != edge_type:
                        print(f"[Edge Sync] Cập nhật camera edge: {cam_id_int} ({edge_name})")
            
            # Cap nhat config
            current_edge_cameras[cam_id_int] = {
                "name": edge_name,
                "ip": edge_ip,
                "camera_type": edge_type
            }
            updated = True
        
        if updated:
            # Luu config moi
            update_config_data = {
                "edge_cameras": current_edge_cameras
            }
            success = config_manager.update_config(update_config_data)
            
            if success:
                # Reload config
                import importlib
                import sys
                if 'config' in sys.modules:
                    del sys.modules['config']
                import config
                importlib.reload(config)
                
                # Broadcast camera update
                await broadcast_camera_update()
                
                return JSONResponse({
                    "success": True,
                    "message": "Edge camera config synced successfully"
                })
            else:
                return JSONResponse({
                    "success": False,
                    "error": "Failed to update config"
                }, status_code=500)
        else:
            return JSONResponse({
                "success": True,
                "message": "No changes needed"
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# P2P API Routes

# Include P2P API router
app.include_router(p2p_api.router)

# Include Edge API router
app.include_router(edge_api.router)


@app.get("/api/p2p/sync-state")
async def get_p2p_sync_state():
    """Get P2P sync state"""
    return p2p_api_extensions.get_sync_state_endpoint()


# WebRTC Proxy

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


# MJPEG Stream Proxy (for Desktop App)

@app.get("/api/stream/raw")
async def proxy_mjpeg_stream_raw(camera_id: int = Query(default=1)):
    """
    Proxy MJPEG stream từ Edge camera (raw feed)

    Args:
        camera_id: ID của camera cần stream (default=1)

    Returns:
        MJPEG stream từ Edge camera
    """
    # Get camera with enriched data (including control_proxy)
    status = _enrich_camera_status(camera_registry.get_camera_status())
    cameras = status.get("cameras", [])
    camera = next((c for c in cameras if c['id'] == camera_id), None)

    if not camera:
        return JSONResponse({"error": "Camera not found"}, status_code=404)

    # Get Edge URL from control_proxy
    control_proxy = camera.get("control_proxy")
    if not control_proxy or not control_proxy.get("available"):
        return JSONResponse({"error": "Camera control proxy not available"}, status_code=500)

    edge_url = control_proxy.get("base_url")
    if not edge_url:
        return JSONResponse({"error": "Edge URL not configured in control_proxy"}, status_code=500)

    # Build Edge stream URL
    if not edge_url.startswith("http"):
        edge_url = f"http://{edge_url}"

    stream_url = f"{edge_url}/api/stream/raw"

    # Proxy stream tu Edge
    async def stream_generator():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", stream_url) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/stream/annotated")
async def proxy_mjpeg_stream_annotated(camera_id: int = Query(default=1)):
    """
    Proxy MJPEG stream từ Edge camera (annotated feed với boxes)

    Args:
        camera_id: ID của camera cần stream (default=1)

    Returns:
        MJPEG stream từ Edge camera
    """
    # Get camera with enriched data (including control_proxy)
    status = _enrich_camera_status(camera_registry.get_camera_status())
    cameras = status.get("cameras", [])
    camera = next((c for c in cameras if c['id'] == camera_id), None)

    if not camera:
        return JSONResponse({"error": "Camera not found"}, status_code=404)

    # Get Edge URL from control_proxy
    control_proxy = camera.get("control_proxy")
    if not control_proxy or not control_proxy.get("available"):
        return JSONResponse({"error": "Camera control proxy not available"}, status_code=500)

    edge_url = control_proxy.get("base_url")
    if not edge_url:
        return JSONResponse({"error": "Edge URL not configured in control_proxy"}, status_code=500)

    # Build Edge stream URL
    if not edge_url.startswith("http"):
        edge_url = f"http://{edge_url}"

    stream_url = f"{edge_url}/api/stream/annotated"

    # Proxy stream tu Edge
    async def stream_generator():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", stream_url) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


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
    await websocket.accept()
    camera_websocket_clients.add(websocket)

    # Send initial camera list immediately
    try:
        global camera_registry
        if camera_registry:
            status = _enrich_camera_status(camera_registry.get_camera_status())
            cameras = _clean_camera_data(status.get("cameras", []))
            initial_message = json.dumps({
                "type": "cameras_update",
                "data": {
                    "cameras": cameras,
                    "total": status.get("total", 0),
                    "online": status.get("online", 0),
                    "offline": status.get("offline", 0)
                }
            })
            await websocket.send_text(initial_message)
    except Exception as e:
        import traceback
        print(f"Error sending initial camera list: {e}")
        traceback.print_exc()

    try:
        # Keep connection alive with ping/pong
        while True:
            try:
                # Wait for messages with timeout de co the send ping
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "pong":
                    pass  # Just acknowledge
                    
            except asyncio.TimeoutError:
                # Send ping de keep connection alive (moi 30 giay)
                try:
                    await websocket.send_text("ping")
                except Exception as e:
                    print(f"Error sending ping: {e}")
                    break  # Connection lost
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        print(f"WebSocket error: {e}")
        traceback.print_exc()
    finally:
        camera_websocket_clients.discard(websocket)


@app.websocket("/ws/p2p")
async def websocket_p2p_connection(websocket: WebSocket):
    """
    WebSocket endpoint for P2P communication between central servers
    Runs on same port as HTTP API (8000) instead of separate port (9000)
    """
    await websocket.accept()

    peer_id = None
    try:
        # Wait for identification message from peer
        data = await websocket.receive_json()
        peer_id = data.get("peer_id")

        if not peer_id:
            await websocket.close(code=1008, reason="No peer_id provided")
            return

        print(f"[P2P WebSocket] Peer '{peer_id}' connected")

        # Register this WebSocket connection with P2P manager
        if p2p_manager:
            p2p_manager.register_websocket_connection(peer_id, websocket)

        # Keep connection alive and handle incoming messages
        while True:
            try:
                message = await websocket.receive_json()

                # Forward message to P2P manager for processing
                if p2p_manager:
                    await p2p_manager.handle_websocket_message(peer_id, message)

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"[P2P WebSocket] Error processing message from {peer_id}: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        print(f"[P2P WebSocket] Connection error: {e}")
        traceback.print_exc()
    finally:
        if peer_id and p2p_manager:
            p2p_manager.unregister_websocket_connection(peer_id)
        print(f"[P2P WebSocket] Peer '{peer_id}' disconnected")


@app.websocket("/ws/edge")
async def websocket_edge_connection(websocket: WebSocket):
    """
    WebSocket endpoint for Edge backend communication
    Edge backends connect here to send/receive events in real-time

    Flow:
    1. Edge connects and sends identification message with edge_id (camera_id)
    2. Edge sends events (ENTRY/EXIT/UPDATE/DELETE) to Central
    3. Central broadcasts events from other nodes to this Edge
    """
    await websocket.accept()

    edge_id = None
    try:
        # Wait for identification message from edge
        data = await websocket.receive_json()
        edge_id = data.get("edge_id")  # This is camera_id

        if not edge_id:
            await websocket.close(code=1008, reason="No edge_id provided")
            return

        print(f"[Edge WebSocket] Edge '{edge_id}' connected")

        # Register this WebSocket connection
        edge_websocket_connections[str(edge_id)] = websocket

        # Send acknowledgement
        await websocket.send_json({
            "type": "connected",
            "message": f"Edge '{edge_id}' registered successfully"
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                message = await websocket.receive_json()

                # Handle different message types
                msg_type = message.get("type")

                if msg_type == "ping":
                    # Respond to ping
                    await websocket.send_json({"type": "pong"})

                elif msg_type in ["ENTRY", "EXIT", "DETECTION", "UPDATE", "DELETE"]:
                    # Event from Edge - process it
                    await handle_edge_websocket_event(edge_id, message)

                else:
                    print(f"[Edge WebSocket] Unknown message type from {edge_id}: {msg_type}")

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"[Edge WebSocket] Error processing message from {edge_id}: {e}")
                import traceback
                traceback.print_exc()
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        print(f"[Edge WebSocket] Connection error: {e}")
        traceback.print_exc()
    finally:
        if edge_id:
            edge_websocket_connections.pop(str(edge_id), None)
        print(f"[Edge WebSocket] Edge '{edge_id}' disconnected")


async def handle_edge_websocket_event(edge_id: str, event: dict):
    """
    Handle event received from Edge via WebSocket

    Flow:
    1. Process event and save to Central DB
    2. Broadcast to P2P peers (other Centrals)
    3. Do NOT broadcast back to Edge (it already has the event)
    """
    global parking_state, database, p2p_broadcaster

    try:
        event_type = event.get('type')
        camera_id = event.get('camera_id', edge_id)
        camera_name = event.get('camera_name', f"Camera {camera_id}")
        camera_type = event.get('camera_type', 'ENTRY')
        data = event.get('data', {})
        event_id = event.get('event_id')

        print(f"[Edge WebSocket] Received {event_type} event from edge {edge_id}: {event_id}")

        # Handle admin operations (UPDATE/DELETE) separately
        if event_type == "UPDATE":
            # Admin updated record on Edge
            history_id = data.get("history_id")  # history_id ở trong data!
            new_plate_text = data.get("plate_text", "")
            new_plate_view = data.get("plate_view", "")

            if database.update_history_entry(history_id, new_plate_text, new_plate_view):
                print(f"[Edge WebSocket] Updated record {history_id} from edge {edge_id}")
                # Broadcast to frontend
                await broadcast_history_update({"type": "updated", "history_id": history_id})
                # Broadcast to other Edges (exclude sender)
                update_event = {
                    "type": "UPDATE",
                    "history_id": history_id,
                    "data": {
                        "plate_text": new_plate_text,
                        "plate_view": new_plate_view
                    }
                }
                await broadcast_to_edges(update_event)
                # Broadcast to P2P peers (other Centrals)
                if p2p_broadcaster:
                    try:
                        asyncio.create_task(p2p_broadcaster.broadcast_history_update(
                            history_id=history_id,
                            plate_text=new_plate_text,
                            plate_view=new_plate_view
                        ))
                    except Exception as e:
                        print(f"[Edge WebSocket] Error broadcasting P2P update: {e}")
            return

        elif event_type == "DELETE":
            # Admin deleted record on Edge
            history_id = data.get("history_id")  # history_id ở trong data!

            if database.delete_history_entry(history_id):
                print(f"[Edge WebSocket] Deleted record {history_id} from edge {edge_id}")
                # Broadcast to frontend
                await broadcast_history_update({"type": "deleted", "history_id": history_id})
                # Broadcast to other Edges (exclude sender)
                delete_event = {
                    "type": "DELETE",
                    "history_id": history_id
                }
                await broadcast_to_edges(delete_event)
                # Broadcast to P2P peers (other Centrals)
                if p2p_broadcaster:
                    try:
                        asyncio.create_task(p2p_broadcaster.broadcast_history_delete(
                            history_id=history_id
                        ))
                    except Exception as e:
                        print(f"[Edge WebSocket] Error broadcasting P2P delete: {e}")
            return

        # Dedupe: if event already exists, skip (for ENTRY/EXIT events)
        if event_id and database and database.event_exists(event_id):
            print(f"[Edge WebSocket] Event {event_id} already exists, skipping (dedupe)")
            return

        # Process parking event using existing parking_state logic
        result = parking_state.process_edge_event(
            event_type=event_type,
            camera_id=camera_id,
            camera_name=camera_name,
            camera_type=camera_type,
            data=data,
            event_id=event_id,
        )

        if result['success']:
            print(f"[Edge WebSocket] Event processed successfully: {event_id}")

            # Broadcast to P2P peers (other Centrals)
            if p2p_broadcaster and result.get('action'):
                try:
                    if result['action'] == 'ENTRY' and result.get('history_id'):
                        asyncio.create_task(p2p_broadcaster.broadcast_entry_pending(
                            event_id=result.get('event_id') or event_id,
                            plate_id=result['plate_id'],
                            plate_view=result['plate_view'],
                            edge_id=camera_id,
                            camera_type=camera_type,
                            direction='ENTRY',
                            entry_time=result['entry_time']
                        ))
                    elif result['action'] == 'EXIT' and result.get('history_id'):
                        asyncio.create_task(p2p_broadcaster.broadcast_exit(
                            event_id=result.get('event_id'),
                            exit_edge=camera_id,
                            exit_time=result.get('exit_time', ''),
                            fee=result.get('fee', 0),
                            duration=result.get('duration', '')
                        ))
                except Exception as e:
                    print(f"[Edge WebSocket] Error broadcasting P2P event: {e}")

            # Broadcast to WebSocket clients (frontend) for real-time update
            clean_result = {k: v for k, v in result.items() if not isinstance(v, bytes) and not (k == 'plate_image' and v is not None)}
            asyncio.create_task(broadcast_history_update({
                "event_type": event_type,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "camera_type": camera_type,
                **clean_result
            }))
        else:
            print(f"[Edge WebSocket] Event processing failed: {result.get('error')}")

    except Exception as e:
        print(f"[Edge WebSocket] Error handling edge event: {e}")
        import traceback
        traceback.print_exc()


async def broadcast_to_edges(event: dict):
    """
    Broadcast event to all connected Edge backends

    Called when Central receives event from P2P peer that needs to be synced to Edges
    """
    if not edge_websocket_connections:
        return

    print(f"[Edge Broadcast] Broadcasting event to {len(edge_websocket_connections)} edge(s)")

    disconnected = []
    for edge_id, websocket in edge_websocket_connections.items():
        try:
            await websocket.send_json(event)
            print(f"[Edge Broadcast] Sent to edge {edge_id}")
        except Exception as e:
            print(f"[Edge Broadcast] Failed to send to edge {edge_id}: {e}")
            disconnected.append(edge_id)

    # Remove disconnected edges
    for edge_id in disconnected:
        edge_websocket_connections.pop(edge_id, None)


# Run Server
if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )
