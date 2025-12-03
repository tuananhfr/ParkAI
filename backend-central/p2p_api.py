"""
P2P API Endpoints - Cho frontend quản lý P2P config
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/p2p", tags=["P2P"])


class CentralConfig(BaseModel):
    """Config cho central"""
    id: str
    ip: str
    p2p_port: int
    api_port: int


class PeerConfig(BaseModel):
    """Config cho peer central"""
    id: str
    ip: str
    p2p_port: int


class P2PConfigUpdate(BaseModel):
    """Update P2P config"""
    this_central: CentralConfig
    peer_centrals: List[PeerConfig]


# Global P2P manager instance (sẽ được inject từ app.py)
_p2p_manager = None


def set_p2p_manager(manager):
    """Set P2P manager instance"""
    global _p2p_manager
    _p2p_manager = manager


@router.get("/config")
async def get_p2p_config():
    """
    Get P2P configuration

    Returns:
        {
            "success": true,
            "config": {
                "this_central": {...},
                "peer_centrals": [...]
            }
        }
    """
    if not _p2p_manager:
        raise HTTPException(status_code=500, detail="P2P manager not initialized")

    try:
        config = _p2p_manager.config.to_dict()
        return JSONResponse({
            "success": True,
            "config": config
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.put("/config")
async def update_p2p_config(config_update: P2PConfigUpdate):
    """
    Update P2P configuration

    Body:
        {
            "this_central": {
                "id": "central-1",
                "ip": "192.168.1.101",
                "p2p_port": 9000,
                "api_port": 8000
            },
            "peer_centrals": [
                {
                    "id": "central-2",
                    "ip": "192.168.1.102",
                    "p2p_port": 9000
                }
            ]
        }
    """
    if not _p2p_manager:
        raise HTTPException(status_code=500, detail="P2P manager not initialized")

    try:
        # Convert Pydantic models to dict
        config_dict = {
            "this_central": config_update.this_central.dict(),
            "peer_centrals": [peer.dict() for peer in config_update.peer_centrals]
        }

        # Save config
        success = _p2p_manager.config.save_config(config_dict)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to save config"
            }, status_code=500)

        # TODO: Restart P2P connections with new config
        # _p2p_manager.reload_config()

        return JSONResponse({
            "success": True,
            "message": "P2P configuration updated successfully. Please restart the server to apply changes."
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/status")
async def get_p2p_status():
    """
    Get P2P status

    Returns:
        {
            "success": true,
            "this_central": "central-1",
            "running": true,
            "standalone_mode": false,
            "total_peers": 3,
            "connected_peers": 2,
            "messages_sent": 150,
            "messages_received": 148,
            "peers": [
                {
                    "peer_id": "central-2",
                    "peer_ip": "192.168.1.102",
                    "peer_port": 9000,
                    "connected": true,
                    "last_ping_time": "2025-12-02T10:30:00"
                }
            ]
        }
    """
    if not _p2p_manager:
        raise HTTPException(status_code=500, detail="P2P manager not initialized")

    try:
        stats = _p2p_manager.get_stats()
        return JSONResponse({
            "success": True,
            **stats
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/test-connection")
async def test_p2p_connection(peer_id: str):
    """
    Test connection to a specific peer

    Query params:
        peer_id: ID của peer cần test
    """
    if not _p2p_manager:
        raise HTTPException(status_code=500, detail="P2P manager not initialized")

    try:
        from .p2p.protocol import create_heartbeat_message

        # Send heartbeat to specific peer
        heartbeat = create_heartbeat_message(
            source_central=_p2p_manager.config.get_this_central_id()
        )

        success = await _p2p_manager.send_to_peer(peer_id, heartbeat)

        if success:
            return JSONResponse({
                "success": True,
                "message": f"Successfully sent test message to {peer_id}"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": f"Failed to send message to {peer_id}. Peer may be offline."
            }, status_code=400)

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
