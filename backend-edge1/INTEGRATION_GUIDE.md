# 🔧 EDGE APP INTEGRATION GUIDE

## Tích hợp Offline Mode vào Edge App

### 1. Import các modules mới

```python
# backend-edge1/app.py
from offline_manager import OfflineManager
from fallback_handler import FallbackHandler
from vehicle_cache import VehicleCache
from central_websocket import CentralWebSocketClient
```

### 2. Initialize global instances (trong startup)

```python
# Global instances
offline_manager = None
fallback_handler = None
vehicle_cache = None
central_ws_client = None

@app.on_event("startup")
async def startup():
    global offline_manager, fallback_handler, vehicle_cache, central_ws_client

    # ... existing code ...

    # Initialize vehicle cache
    print("💾 Initializing vehicle cache...")
    vehicle_cache = VehicleCache(db_file=config.VEHICLE_CACHE_DB)

    # Initialize offline manager
    print("⚡ Initializing offline manager...")
    offline_manager = OfflineManager(
        central_url=config.CENTRAL_SERVER_URL,
        db_file=config.OFFLINE_QUEUE_DB
    )

    # Initialize fallback handler
    print("🔄 Initializing fallback handler...")
    fallback_handler = FallbackHandler(config)

    # Initialize WebSocket client nếu Central sync enabled
    if config.CENTRAL_SYNC_ENABLED:
        print("🔌 Initializing Central WebSocket client...")

        def on_ws_message(data):
            """Callback khi nhận message từ Central"""
            try:
                msg_type = data.get('type')

                if msg_type == 'vehicle_update':
                    # Update local cache
                    vehicle_cache.update_from_websocket(
                        event_type=data.get('event'),
                        plate_id=data.get('plate_id'),
                        gate=data.get('gate'),
                        entry_time=data.get('entry_time'),
                        exit_time=data.get('exit_time'),
                        fee=data.get('fee', 0),
                        duration=data.get('duration', ''),
                        camera_name=data.get('camera_name')
                    )
            except Exception as e:
                print(f"❌ Error processing WS message: {e}")

        central_ws_client = CentralWebSocketClient(
            central_ws_url=config.CENTRAL_WS_URL,
            edge_id=f"edge{config.CAMERA_ID}",
            on_message_callback=on_ws_message
        )
        central_ws_client.start()
```

### 3. Update API /api/open-barrier

```python
@app.post("/api/open-barrier")
async def open_barrier(request: Request):
    global parking_manager, barrier_controller, offline_manager, fallback_handler, vehicle_cache

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

        # 1. Validate format (local)
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

        plate_id = result.get('plate_id')

        # 2. Check cache (cho cổng RA)
        if config.CAMERA_TYPE == "EXIT":
            vehicle = vehicle_cache.check_vehicle_in_parking(plate_id)

            if not vehicle:
                # Xe KHÔNG CÓ trong cache → FALLBACK
                allow, fee, message = fallback_handler.handle_vehicle_not_found(
                    plate_id, config.CAMERA_TYPE
                )

                if not allow:
                    return JSONResponse({
                        "success": False,
                        "error": message,
                        "offline_mode": not offline_manager.is_online
                    }, status_code=400)

                # Update result với fallback fee
                result['fee'] = fee
                result['warning'] = message
            else:
                # Có trong cache → Tính phí bình thường
                from datetime import datetime
                entry_time = datetime.fromisoformat(vehicle['entry_time'])
                exit_time = datetime.now()

                # Tính duration và fee
                result['entry_time'] = vehicle['entry_time']
                result['entry_gate'] = vehicle['entry_gate']
                result['duration'] = parking_manager.calculate_duration(entry_time, exit_time)
                result['fee'] = parking_manager.calculate_fee(entry_time, exit_time)

                # Update local cache
                vehicle_cache.update_local_exit(
                    plate_id=plate_id,
                    gate=config.GATE,
                    exit_time=exit_time.isoformat(),
                    fee=result['fee'],
                    duration=result['duration'],
                    camera_name=config.CAMERA_NAME
                )
        else:
            # ENTRY camera → Add to local cache
            from datetime import datetime
            vehicle_cache.add_local_entry(
                plate_id=plate_id,
                gate=config.GATE,
                entry_time=datetime.now().isoformat(),
                camera_name=config.CAMERA_NAME
            )

        # 3. Mở cửa NGAY (không chờ sync)
        if barrier_controller and config.BARRIER_ENABLED:
            barrier_controller.open_barrier()

        # 4. Sync to Central (async, không block)
        if offline_manager and config.CENTRAL_SYNC_ENABLED:
            success, error = await offline_manager.send_event(
                event_type=config.CAMERA_TYPE,
                event_data={
                    "plate_id": plate_id,
                    "plate_text": plate_text,
                    "gate": config.GATE,
                    "camera_id": config.CAMERA_ID,
                    "camera_name": config.CAMERA_NAME,
                    "entry_time": result.get('entry_time'),
                    "exit_time": result.get('exit_time'),
                    "fee": result.get('fee', 0),
                    "duration": result.get('duration', ''),
                    "confidence": confidence,
                    "source": source
                }
            )
        else:
            success = False
            error = "Central sync disabled"

        # 5. Response
        return JSONResponse({
            **result,
            "barrier_opened": config.BARRIER_ENABLED,
            "synced": success,
            "offline_mode": not offline_manager.is_online if offline_manager else True,
            "sync_error": error if not success else None,
            "camera_info": {
                "id": config.CAMERA_ID,
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE,
                "gate": config.GATE
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
```

### 4. Thêm API monitoring

```python
@app.get("/api/offline/status")
async def offline_status():
    """Get offline mode status"""
    if not offline_manager:
        return JSONResponse({
            "success": False,
            "error": "Offline manager not initialized"
        }, status_code=500)

    queue_stats = offline_manager.get_queue_stats()
    cache_stats = vehicle_cache.get_cache_stats() if vehicle_cache else {}
    ws_status = central_ws_client.get_status() if central_ws_client else {}
    fallback_info = fallback_handler.get_strategy_info() if fallback_handler else {}

    return JSONResponse({
        "success": True,
        "offline_queue": queue_stats,
        "vehicle_cache": cache_stats,
        "websocket": ws_status,
        "fallback_strategy": fallback_info
    })

@app.get("/api/cache/vehicles")
async def get_cached_vehicles():
    """Get vehicles in cache"""
    if not vehicle_cache:
        return JSONResponse({
            "success": False,
            "error": "Vehicle cache not initialized"
        }, status_code=500)

    vehicles_in = vehicle_cache.get_all_in_parking()

    return JSONResponse({
        "success": True,
        "count": len(vehicles_in),
        "vehicles": vehicles_in
    })
```

### 5. Cleanup on shutdown

```python
@app.on_event("shutdown")
async def shutdown():
    # ... existing code ...

    # Stop WebSocket client
    if central_ws_client:
        central_ws_client.stop()

    # Stop offline manager
    if offline_manager:
        offline_manager.stop() if hasattr(offline_manager, 'stop') else None

    print("✅ Edge app shutdown complete")
```

## ✅ HOÀN TẤT!

Sau khi tích hợp:
- Edge hoạt động độc lập khi Central down
- Events được queue và retry tự động
- Cache được sync real-time qua WebSocket
- Fallback strategy cho xe không có trong cache
