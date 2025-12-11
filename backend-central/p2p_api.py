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
    api_port: int


class PeerConfig(BaseModel):
    """Config cho peer central"""
    id: str
    ip: str


class P2PConfigUpdate(BaseModel):
    """Update P2P config"""
    this_central: CentralConfig
    peer_centrals: List[PeerConfig]


class AddPeerRequest(BaseModel):
    """Request to add a peer (only IP needed)"""
    ip: str
    api_port: Optional[int] = 8000


class RegisterPeerRequest(BaseModel):
    """Request to register a peer"""
    id: str
    ip: str
    api_port: int


# Global P2P manager instance (se duoc inject tu app.py)
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
        # Return empty config if P2P manager not initialized yet
        return JSONResponse({
            "success": True,
            "config": {
                "this_central": {"id": "", "ip": "", "api_port": 8000},
                "peer_centrals": []
            }
        })

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
    Update P2P configuration with bi-directional registration

    Body:
        {
            "this_central": {
                "id": "central-1",
                "ip": "192.168.1.101",
                "api_port": 8000
            },
            "peer_centrals": [
                {
                    "id": "central-2",
                    "ip": "192.168.1.102"
                }
            ]
        }
    """
    if not _p2p_manager:
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo"
        }, status_code=503)

    try:
        import requests

        # Get current config to find new peers
        old_config = _p2p_manager.config.to_dict()
        old_peer_ids = [peer.get("id") for peer in old_config.get("peer_centrals", [])]

        # Convert Pydantic models to dict
        config_dict = {
            "this_central": config_update.this_central.dict(),
            "peer_centrals": [peer.dict() for peer in config_update.peer_centrals]
        }

        this_central = config_dict["this_central"]
        new_peers = config_dict["peer_centrals"]

        # Find newly added peers
        registration_results = []
        for peer in new_peers:
            if peer.get("id") not in old_peer_ids:
                # New peer - register this central with the peer
                try:
                    peer_api_url = f"http://{peer['ip']}:{peer.get('api_port', 8000)}"
                    register_url = f"{peer_api_url}/api/p2p/register-peer"

                    # Send registration request
                    response = requests.post(
                        register_url,
                        json={
                            "id": this_central["id"],
                            "ip": this_central["ip"],
                            "api_port": this_central["api_port"]
                        },
                        timeout=5
                    )

                    if response.status_code == 200:
                        data = response.json()
                        registration_results.append({
                            "peer_id": peer["id"],
                            "success": data.get("success", False),
                            "message": data.get("message", "")
                        })
                    else:
                        registration_results.append({
                            "peer_id": peer["id"],
                            "success": False,
                            "message": f"HTTP {response.status_code}"
                        })

                except Exception as e:
                    registration_results.append({
                        "peer_id": peer["id"],
                        "success": False,
                        "message": f"Failed to register: {str(e)}"
                    })

        # Save config
        success = _p2p_manager.config.save_config(config_dict)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to save config"
            }, status_code=500)

        # Build response message
        message = "P2P configuration updated successfully."
        if registration_results:
            successful_registrations = [r for r in registration_results if r["success"]]
            failed_registrations = [r for r in registration_results if not r["success"]]

            if successful_registrations:
                message += f" Registered with {len(successful_registrations)} peer(s)."
            if failed_registrations:
                failed_peers = ", ".join([r["peer_id"] for r in failed_registrations])
                message += f" Failed to register with: {failed_peers}."

        return JSONResponse({
            "success": True,
            "message": message,
            "registration_results": registration_results
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
        # Return default status if P2P manager not initialized yet
        return JSONResponse({
            "success": True,
            "this_central": "",
            "running": False,
            "standalone_mode": True,
            "total_peers": 0,
            "connected_peers": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "peers": []
        })

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
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo"
        }, status_code=503)

    try:
        from p2p.protocol import create_heartbeat_message

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


@router.post("/add-peer")
async def add_peer(request: AddPeerRequest):
    """
    Add a peer with bi-directional registration (only IP needed)

    Body:
        {
            "ip": "192.168.1.102",
            "api_port": 8000  // optional, default 8000
        }

    Returns:
        {
            "success": true,
            "message": "Peer added and registered successfully",
            "peer": {
                "id": "central-2",
                "ip": "192.168.1.102"
            }
        }
    """
    if not _p2p_manager:
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo"
        }, status_code=503)

    try:
        import requests

        # Step 1: Fetch peer info from peer's /api/p2p/info endpoint
        peer_api_url = f"http://{request.ip}:{request.api_port}"
        info_url = f"{peer_api_url}/api/p2p/info"

        try:
            info_response = requests.get(info_url, timeout=5)
            if info_response.status_code != 200:
                return JSONResponse({
                    "success": False,
                    "error": f"Failed to fetch peer info: HTTP {info_response.status_code}"
                }, status_code=400)

            peer_info = info_response.json()
            if not peer_info.get("success"):
                return JSONResponse({
                    "success": False,
                    "error": "Peer info endpoint returned error"
                }, status_code=400)

            peer_data = peer_info.get("info", {})
            peer_id = peer_data.get("id")
            if not peer_id:
                return JSONResponse({
                    "success": False,
                    "error": "Peer did not provide an ID"
                }, status_code=400)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": f"Cannot connect to peer: {str(e)}"
            }, status_code=400)

        # Step 2: Add peer to local config
        config = _p2p_manager.config.to_dict()
        peer_centrals = config.get("peer_centrals", [])

        # Check if already exists
        peer_exists = any(peer.get("id") == peer_id for peer in peer_centrals)
        if peer_exists:
            return JSONResponse({
                "success": False,
                "error": f"Peer '{peer_id}' already exists in config"
            }, status_code=400)

        # Add new peer
        new_peer = {
            "id": peer_id,
            "ip": request.ip
        }
        peer_centrals.append(new_peer)
        config["peer_centrals"] = peer_centrals

        # Save config
        save_success = _p2p_manager.config.save_config(config)
        if not save_success:
            return JSONResponse({
                "success": False,
                "error": "Failed to save config"
            }, status_code=500)

        # Step 3: Register this central with the peer
        this_central = config.get("this_central", {})
        register_url = f"{peer_api_url}/api/p2p/register-peer"

        registration_success = False
        registration_message = ""

        try:
            register_response = requests.post(
                register_url,
                json={
                    "id": this_central["id"],
                    "ip": this_central["ip"],
                    "api_port": this_central["api_port"]
                },
                timeout=5
            )

            if register_response.status_code == 200:
                register_data = register_response.json()
                registration_success = register_data.get("success", False)
                registration_message = register_data.get("message", "")
            else:
                registration_message = f"HTTP {register_response.status_code}"

        except Exception as e:
            registration_message = f"Failed to register: {str(e)}"

        # Build response
        message = f"Peer '{peer_id}' added successfully."
        if registration_success:
            message += f" Bi-directional registration completed."
        else:
            message += f" Warning: Failed to register with peer ({registration_message})"

        return JSONResponse({
            "success": True,
            "message": message,
            "peer": new_peer,
            "registration_success": registration_success
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.get("/info")
async def get_central_info():
    """
    Get this central's info (for other centrals to query)

    Returns:
        {
            "success": true,
            "info": {
                "id": "central-1",
                "ip": "192.168.1.101",
                "api_port": 8000
            }
        }
    """
    if not _p2p_manager:
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo",
            "info": {"id": "", "ip": "", "api_port": 8000}
        }, status_code=503)

    try:
        config = _p2p_manager.config.to_dict()
        this_central = config.get("this_central", {})

        return JSONResponse({
            "success": True,
            "info": {
                "id": this_central.get("id", ""),
                "ip": this_central.get("ip", ""),
                "api_port": this_central.get("api_port", 8000)
            }
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/register-peer")
async def register_peer(request: RegisterPeerRequest):
    """
    Register a peer central (called by the peer itself)

    Body:
        {
            "id": "central-1",
            "ip": "192.168.1.101",
            "api_port": 8000
        }

    Returns:
        {
            "success": true,
            "message": "Peer registered successfully"
        }
    """
    if not _p2p_manager:
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo"
        }, status_code=503)

    try:
        # Get current config
        config = _p2p_manager.config.to_dict()
        peer_centrals = config.get("peer_centrals", [])

        # Check if peer already exists
        peer_exists = any(peer.get("id") == request.id for peer in peer_centrals)

        if peer_exists:
            # Update existing peer
            peer_centrals = [
                {
                    "id": request.id,
                    "ip": request.ip
                } if peer.get("id") == request.id else peer
                for peer in peer_centrals
            ]
        else:
            # Add new peer
            peer_centrals.append({
                "id": request.id,
                "ip": request.ip
            })

        # Save updated config
        config["peer_centrals"] = peer_centrals
        success = _p2p_manager.config.save_config(config)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to save peer config"
            }, status_code=500)

        # Reload P2P connections to pick up new peer
        import asyncio
        asyncio.create_task(_p2p_manager.reload_config())

        return JSONResponse({
            "success": True,
            "message": f"Peer '{request.id}' registered successfully",
            "action": "updated" if peer_exists else "added"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@router.post("/unregister-peer")
async def unregister_peer(peer_id: str):
    """
    Unregister a peer central (called by the peer when it removes us)

    Query params:
        peer_id: ID of the peer to remove

    Returns:
        {
            "success": true,
            "message": "Peer unregistered successfully"
        }
    """
    if not _p2p_manager:
        return JSONResponse({
            "success": False,
            "error": "P2P manager chưa được khởi tạo"
        }, status_code=503)

    try:
        # Get current config
        config = _p2p_manager.config.to_dict()
        peer_centrals = config.get("peer_centrals", [])

        # Check if peer exists
        peer_exists = any(peer.get("id") == peer_id for peer in peer_centrals)

        if not peer_exists:
            return JSONResponse({
                "success": False,
                "error": f"Peer '{peer_id}' not found"
            }, status_code=404)

        # Remove peer
        peer_centrals = [peer for peer in peer_centrals if peer.get("id") != peer_id]

        # Save updated config
        config["peer_centrals"] = peer_centrals
        success = _p2p_manager.config.save_config(config)

        if not success:
            return JSONResponse({
                "success": False,
                "error": "Failed to save config"
            }, status_code=500)

        # Reload P2P connections to disconnect from removed peer
        import asyncio
        asyncio.create_task(_p2p_manager.reload_config())

        return JSONResponse({
            "success": True,
            "message": f"Peer '{peer_id}' unregistered successfully"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
