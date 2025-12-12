"""
P2P Manager - Orchestrate server + clients + event handling
"""
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime

from .config_loader import P2PConfig
from .server import P2PServer
from .client import P2PClient
from .protocol import P2PMessage, MessageType, create_heartbeat_message


class P2PManager:
    """Main P2P orchestrator"""

    def __init__(self, config_file: str = "config/p2p_config.json"):
        self.config = P2PConfig(config_file)
        self.server: Optional[P2PServer] = None
        self.clients: Dict[str, P2PClient] = {}
        self.websocket_connections: Dict[str, any] = {}  # WebSocket connections from FastAPI
        self.running = False

        # Callbacks
        self.on_vehicle_entry_pending: Optional[Callable] = None
        self.on_vehicle_entry_confirmed: Optional[Callable] = None
        self.on_vehicle_exit: Optional[Callable] = None
        self.on_location_update: Optional[Callable] = None
        self.on_parking_lot_config: Optional[Callable] = None
        self.on_history_update: Optional[Callable] = None
        self.on_history_delete: Optional[Callable] = None
        self.on_sync_request: Optional[Callable] = None
        self.on_sync_response: Optional[Callable] = None
        self.on_peer_connected: Optional[Callable] = None
        self.on_peer_disconnected: Optional[Callable] = None

        # Stats
        self.messages_sent = 0
        self.messages_received = 0

    async def start(self):
        """Start P2P manager"""
        if self.running:
            print("P2P Manager already running")
            return

        self.running = True

        # Check if standalone mode
        if self.config.is_standalone():
            print("Running in standalone mode (no P2P peers configured)")
            return

        # NOTE: P2P server is now handled by FastAPI WebSocket endpoint at /ws/p2p
        # No need to start separate P2P server on port 9000
        print("[P2P] Using FastAPI WebSocket endpoint (/ws/p2p) instead of separate server")

        # Start clients to connect to peers (they will connect to ws://ip:8000/ws/p2p)
        await self._start_clients()

        # Start heartbeat loop
        asyncio.create_task(self._heartbeat_loop())

        print(f"P2P Manager started (ID: {self.config.get_this_central_id()})")
        print(f"P2P WebSocket endpoint: ws://<this-server>:8000/ws/p2p")

    async def stop(self):
        """Stop P2P manager"""
        self.running = False

        # Stop server
        if self.server:
            await self.server.stop()

        # Stop all clients
        for client in self.clients.values():
            await client.stop()

        print("P2P Manager stopped")

    async def _start_server(self):
        """Start P2P server"""
        host = self.config.get_this_central_ip()
        port = self.config.get_this_central_p2p_port()

        self.server = P2PServer(
            host=host,
            port=port,
            on_message=self._handle_message
        )

        await self.server.start()

    async def _start_clients(self):
        """Start P2P clients to connect to peers"""
        peers = self.config.get_peer_centrals()
        this_central_id = self.config.get_this_central_id()

        for peer in peers:
            peer_id = peer["id"]
            peer_ip = peer["ip"]
            # Use API port (8000) for WebSocket connection, not p2p_port
            peer_port = peer.get("api_port", 8000)

            client = P2PClient(
                peer_id=peer_id,
                peer_ip=peer_ip,
                peer_port=peer_port,
                this_central_id=this_central_id,
                on_message=self._handle_message,
                on_connected=self._on_peer_connected,
                on_disconnected=self._on_peer_disconnected
            )

            self.clients[peer_id] = client
            await client.start()

    async def _handle_message(self, message: P2PMessage, peer_id: Optional[str] = None):
        """Handle incoming P2P message"""
        self.messages_received += 1

        try:
            # Route message to appropriate handler
            if message.type == MessageType.VEHICLE_ENTRY_PENDING:
                if self.on_vehicle_entry_pending:
                    await self.on_vehicle_entry_pending(message)

            elif message.type == MessageType.VEHICLE_ENTRY_CONFIRMED:
                if self.on_vehicle_entry_confirmed:
                    await self.on_vehicle_entry_confirmed(message)

            elif message.type == MessageType.VEHICLE_EXIT:
                if self.on_vehicle_exit:
                    await self.on_vehicle_exit(message)

            elif message.type == MessageType.HEARTBEAT:
                # Just log heartbeat
                pass

            elif message.type == MessageType.SYNC_REQUEST:
                # Handle sync request
                if self.on_sync_request:
                    await self.on_sync_request(message, peer_id or message.source_central)

            elif message.type == MessageType.SYNC_RESPONSE:
                # Handle sync response
                if self.on_sync_response:
                    await self.on_sync_response(message, peer_id or message.source_central)

            elif message.type == MessageType.HISTORY_UPDATE:
                # Handle history update from P2P peer
                if self.on_history_update:
                    await self.on_history_update(message)

            elif message.type == MessageType.HISTORY_DELETE:
                # Handle history delete from P2P peer
                if self.on_history_delete:
                    await self.on_history_delete(message)

            elif message.type == MessageType.LOCATION_UPDATE:
                # Handle location update from P2P peer
                if self.on_location_update:
                    await self.on_location_update(message)

            elif message.type == MessageType.PARKING_LOT_CONFIG:
                # Handle parking lot config from P2P peer
                if self.on_parking_lot_config:
                    await self.on_parking_lot_config(message)

            else:
                print(f"Unknown message type: {message.type}")

        except Exception as e:
            print(f"Error handling P2P message: {e}")
            import traceback
            traceback.print_exc()

    async def _on_peer_connected(self, peer_id: str):
        """Callback when peer connected"""
        print(f"Peer {peer_id} connected")

        if self.on_peer_connected:
            try:
                await self.on_peer_connected(peer_id)
            except Exception as e:
                print(f"Error in on_peer_connected callback: {e}")

    async def _on_peer_disconnected(self, peer_id: str):
        """Callback when peer disconnected"""
        print(f"Peer {peer_id} disconnected")

        if self.on_peer_disconnected:
            try:
                await self.on_peer_disconnected(peer_id)
            except Exception as e:
                print(f"Error in on_peer_disconnected callback: {e}")

    async def _heartbeat_loop(self):
        """Send heartbeat to peers every 30s"""
        while self.running:
            try:
                await asyncio.sleep(30)

                if not self.running:
                    break

                # Send heartbeat to all WebSocket connected peers
                if self.websocket_connections:
                    heartbeat_msg = create_heartbeat_message(
                        source_central=self.config.get_this_central_id()
                    )
                    await self.broadcast(heartbeat_msg)

            except Exception as e:
                print(f"Error in heartbeat loop: {e}")

    async def broadcast(self, message: P2PMessage):
        """Broadcast message to all peers"""
        if self.config.is_standalone():
            return  # No peers to broadcast

        self.messages_sent += 1

        # Send through WebSocket connections (FastAPI endpoint)
        for peer_id in list(self.websocket_connections.keys()):
            try:
                await self.send_websocket_message(peer_id, message)
            except Exception as e:
                print(f"Error broadcasting via WebSocket to {peer_id}: {e}")

        # Send to connected clients (backup/legacy)
        for client in self.clients.values():
            try:
                if client.is_connected():
                    await client.send(message)
            except Exception as e:
                print(f"Error broadcasting to {client.peer_id}: {e}")

        # Broadcast to server's connected clients (peers that connected to us)
        if self.server:
            try:
                await self.server.broadcast(message)
            except Exception as e:
                print(f"Error broadcasting from server: {e}")

    async def send_to_peer(self, peer_id: str, message: P2PMessage) -> bool:
        """Send message to specific peer"""
        # Try WebSocket connection first (incoming connections)
        if peer_id in self.websocket_connections:
            try:
                return await self.send_websocket_message(peer_id, message)
            except Exception as e:
                print(f"Error sending via WebSocket to {peer_id}: {e}")

        # Fallback to client connection (outgoing connections)
        client = self.clients.get(peer_id)
        if client and client.is_connected():
            return await client.send(message)

        print(f"Peer {peer_id} not connected")
        return False

    def get_peer_status(self) -> List[Dict]:
        """Get status of all peers"""
        peers_status = []

        # Get status from WebSocket connections
        for peer_id in self.websocket_connections.keys():
            peers_status.append({
                "peer_id": peer_id,
                "peer_ip": "N/A",  # Will be filled from config
                "peer_port": 8000,
                "status": "connected",
                "last_ping_time": datetime.now().isoformat()
            })

        # Get status from legacy clients (if any)
        for client in self.clients.values():
            peers_status.append(client.get_status())

        return peers_status

    def get_stats(self) -> Dict:
        """Get P2P stats"""
        connected_peers = sum(1 for c in self.clients.values() if c.is_connected())
        total_peers = len(self.clients)

        return {
            "this_central": self.config.get_this_central_id(),
            "running": self.running,
            "standalone_mode": self.config.is_standalone(),
            "total_peers": total_peers,
            "connected_peers": connected_peers,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "peers": self.get_peer_status()
        }

    async def reload_config(self):
        """Reload config and restart connections"""
        print("Reloading P2P config...")

        # Reload config from file
        self.config._load_config()

        # If now in standalone mode, stop all clients
        if self.config.is_standalone():
            print("Config changed to standalone mode, stopping clients...")
            for client in self.clients.values():
                await client.stop()
            self.clients.clear()
            return

        # Get new peer list
        new_peers = self.config.get_peer_centrals()
        new_peer_ids = set(peer["id"] for peer in new_peers)
        current_peer_ids = set(self.clients.keys())

        # Stop clients for removed peers
        removed_peers = current_peer_ids - new_peer_ids
        for peer_id in removed_peers:
            print(f"Stopping connection to removed peer: {peer_id}")
            await self.clients[peer_id].stop()
            del self.clients[peer_id]

        # Start clients for new peers
        added_peers = new_peer_ids - current_peer_ids
        this_central_id = self.config.get_this_central_id()

        for peer in new_peers:
            peer_id = peer["id"]
            if peer_id in added_peers:
                print(f"Starting connection to new peer: {peer_id}")
                peer_ip = peer["ip"]
                peer_port = peer.get("api_port", 8000)

                client = P2PClient(
                    peer_id=peer_id,
                    peer_ip=peer_ip,
                    peer_port=peer_port,
                    this_central_id=this_central_id,
                    on_message=self._handle_message,
                    on_connected=self._on_peer_connected,
                    on_disconnected=self._on_peer_disconnected
                )

                self.clients[peer_id] = client
                await client.start()

        print(f"P2P config reloaded: {len(self.clients)} clients")

    # WebSocket connection management (for FastAPI /ws/p2p endpoint)
    def register_websocket_connection(self, peer_id: str, websocket):
        """Register a WebSocket connection from FastAPI endpoint"""
        self.websocket_connections[peer_id] = websocket
        print(f"[P2P Manager] Registered WebSocket connection for peer: {peer_id}")

        # Trigger on_peer_connected callback
        if self.on_peer_connected:
            asyncio.create_task(self.on_peer_connected(peer_id))

    def unregister_websocket_connection(self, peer_id: str):
        """Unregister a WebSocket connection"""
        if peer_id in self.websocket_connections:
            del self.websocket_connections[peer_id]
            print(f"[P2P Manager] Unregistered WebSocket connection for peer: {peer_id}")

            # Trigger on_peer_disconnected callback
            if self.on_peer_disconnected:
                asyncio.create_task(self.on_peer_disconnected(peer_id))

    async def handle_websocket_message(self, peer_id: str, message_data: dict):
        """Handle incoming WebSocket message from FastAPI endpoint"""
        try:
            # Convert dict to P2PMessage
            message = P2PMessage(
                msg_type=MessageType(message_data.get("type")),
                source_central=message_data.get("source_central"),
                timestamp=message_data.get("timestamp"),
                event_id=message_data.get("event_id"),
                data=message_data.get("data")
            )

            # Process message using existing handler
            await self._handle_message(message, peer_id)

        except Exception as e:
            print(f"[P2P Manager] Error handling WebSocket message: {e}")
            import traceback
            traceback.print_exc()

    async def send_websocket_message(self, peer_id: str, message: P2PMessage) -> bool:
        """Send message through WebSocket connection"""
        if peer_id not in self.websocket_connections:
            return False

        websocket = self.websocket_connections[peer_id]
        try:
            await websocket.send_json(message.to_dict())
            return True
        except Exception as e:
            print(f"[P2P Manager] Error sending WebSocket message to {peer_id}: {e}")
            return False
