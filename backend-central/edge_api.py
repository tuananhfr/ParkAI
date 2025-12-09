"""
Edge API Endpoints - API cho Edge servers (cameras)

Edge servers gọi các API này để:
- Gửi detection events
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


# Global dependencies (se duoc inject tu app.py)
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
