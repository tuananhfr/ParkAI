"""
P2P API Extensions - Additional endpoints for Phase 3
"""
from fastapi import HTTPException
from fastapi.responses import JSONResponse


# Global database reference (injected from app.py)
_database = None


def set_database(database):
    """Set database instance"""
    global _database
    _database = database


def get_sync_state_endpoint():
    """
    Get sync state với tất cả peers

    Returns:
        {
            "success": true,
            "sync_state": [
                {
                    "peer_central_id": "central-2",
                    "last_sync_timestamp": 1733140800000,
                    "last_sync_time": "2025-12-02 10:30:00",
                    "updated_at": "2025-12-02 10:30:05"
                }
            ]
        }
    """
    if not _database:
        # Return empty sync state if database not initialized yet
        return JSONResponse({
            "success": True,
            "sync_state": []
        })

    try:
        sync_state = _database.get_sync_state()

        return JSONResponse({
            "success": True,
            "sync_state": sync_state
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
