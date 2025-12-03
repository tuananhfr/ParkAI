"""
Edge API Endpoints - API cho Edge servers (cameras)

Edge servers gọi các API này để:
- Gửi detection events
- Nhận lệnh mở/đóng barrier
- Heartbeat
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/edge", tags=["Edge"])


class DetectionEvent(BaseModel):
    """Detection event từ edge"""
    edge_id: str
    plate_id: str
    plate_view: str
    camera_type: str  # "car" | "moto"
    direction: str    # "ENTRY" | "EXIT"
    confidence: float
    timestamp: Optional[int] = None


class BarrierCommand(BaseModel):
    """Lệnh mở/đóng barrier"""
    edge_id: str
    plate_id: str
    action: str  # "open" | "close"


# Global dependencies (sẽ được inject từ app.py)
_database = None
_parking_state = None
_p2p_broadcaster = None


def set_dependencies(database, parking_state, p2p_broadcaster):
    """Inject dependencies"""
    global _database, _parking_state, _p2p_broadcaster
    _database = database
    _parking_state = parking_state
    _p2p_broadcaster = p2p_broadcaster


@router.post("/detection")
async def handle_detection(event: DetectionEvent):
    """
    Edge gửi detection event

    Flow:
    1. Edge detect plate → gửi lên central
    2. Central validate
    3. Return vehicle info (already inside? subscriber?)
    4. Frontend hiển thị
    5. User click "Open Barrier" → call /barrier/open
    """
    if not _database or not _parking_state:
        raise HTTPException(status_code=500, detail="Dependencies not initialized")

    try:
        # Validate detection
        plate_id = event.plate_id.upper().replace(" ", "").replace("-", "").replace(".", "")

        if len(plate_id) < 6:
            return JSONResponse({
                "success": False,
                "error": "Invalid plate number (too short)"
            }, status_code=400)

        # Check vehicle status
        vehicle_info = {
            "plate_id": plate_id,
            "plate_view": event.plate_view,
            "direction": event.direction,
            "camera_type": event.camera_type
        }

        if event.direction == "ENTRY":
            # Check if already inside
            existing = _database.find_vehicle_in_parking(plate_id)
            vehicle_info["already_inside"] = existing is not None

            if existing:
                vehicle_info["entry_time"] = existing.get("entry_time")
                vehicle_info["entry_from"] = existing.get("source_central", "unknown")

        elif event.direction == "EXIT":
            # Check if has entry
            existing = _database.find_vehicle_in_parking(plate_id)
            vehicle_info["has_entry"] = existing is not None

            if existing:
                vehicle_info["entry_time"] = existing.get("entry_time")

                # Calculate fee preview
                from datetime import datetime
                entry_time_str = existing.get("entry_time")
                exit_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                duration, fee = _parking_state._calculate_fee(entry_time_str, exit_time_str)
                vehicle_info["duration"] = duration
                vehicle_info["fee"] = fee
            else:
                vehicle_info["error"] = "No entry record found"

        return JSONResponse({
            "success": True,
            "allowed": True,
            "vehicle_info": vehicle_info
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/barrier/open")
async def open_barrier(command: BarrierCommand):
    """
    Central gửi lệnh mở barrier

    Flow:
    1. User click "Open Barrier" từ frontend
    2. Frontend gọi central API
    3. Central validate
    4. Central INSERT DB với status=PENDING
    5. Central broadcast P2P
    6. Central trả về success → frontend mở barrier
    """
    if not _database or not _p2p_broadcaster:
        raise HTTPException(status_code=500, detail="Dependencies not initialized")

    try:
        edge_id = command.edge_id
        plate_id = command.plate_id.upper().replace(" ", "").replace("-", "").replace(".", "")

        # Generate event_id
        event_id = _p2p_broadcaster.generate_event_id(plate_id)

        # Determine direction from edge_id or require in request
        # For now, assume edge_id contains direction info or derive from existing logic
        # Simplified: Check if vehicle already inside
        existing = _database.find_vehicle_in_parking(plate_id)

        if existing:
            # Vehicle inside → this is EXIT
            direction = "EXIT"

            # Calculate fee
            from datetime import datetime
            entry_time_str = existing.get("entry_time")
            exit_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            duration, fee = _parking_state._calculate_fee(entry_time_str, exit_time_str)

            # Update exit
            _database.update_vehicle_exit_p2p(
                event_id=existing.get("event_id"),
                exit_time=exit_time_str,
                camera_id=None,
                camera_name=f"{_p2p_broadcaster.central_id}/{edge_id}",
                confidence=0.0,
                source="edge_manual",
                duration=duration,
                fee=fee
            )

            # Broadcast EXIT
            await _p2p_broadcaster.broadcast_exit(
                event_id=existing.get("event_id"),
                exit_edge=edge_id,
                exit_time=exit_time_str,
                fee=fee,
                duration=duration
            )

            return JSONResponse({
                "success": True,
                "action": "EXIT",
                "event_id": existing.get("event_id"),
                "fee": fee,
                "duration": duration
            })

        else:
            # Vehicle not inside → this is ENTRY
            direction = "ENTRY"
            entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert entry
            history_id = _database.add_vehicle_entry_p2p(
                event_id=event_id,
                source_central=_p2p_broadcaster.central_id,
                edge_id=edge_id,
                plate_id=plate_id,
                plate_view=plate_id,  # TODO: Get proper plate_view from detection
                entry_time=entry_time,
                camera_id=None,
                camera_name=f"{_p2p_broadcaster.central_id}/{edge_id}",
                confidence=0.0,
                source="edge_manual"
            )

            # Broadcast ENTRY_PENDING
            await _p2p_broadcaster.broadcast_entry_pending(
                event_id=event_id,
                plate_id=plate_id,
                plate_view=plate_id,
                edge_id=edge_id,
                camera_type="unknown",
                direction=direction,
                entry_time=entry_time
            )

            return JSONResponse({
                "success": True,
                "action": "ENTRY",
                "event_id": event_id,
                "history_id": history_id
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/barrier/close")
async def close_barrier(command: BarrierCommand):
    """
    Barrier đã đóng - confirm entry

    Flow:
    1. User close barrier từ frontend
    2. Frontend gọi edge API
    3. Edge gọi central API này
    4. Central broadcast ENTRY_CONFIRMED
    """
    if not _p2p_broadcaster:
        raise HTTPException(status_code=500, detail="Dependencies not initialized")

    try:
        # Get event_id from request (frontend should pass this)
        # For now, just log
        confirmed_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # TODO: Broadcast ENTRY_CONFIRMED if needed
        # await _p2p_broadcaster.broadcast_entry_confirmed(event_id, confirmed_time)

        return JSONResponse({
            "success": True,
            "message": "Barrier closed"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
