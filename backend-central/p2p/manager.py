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
        self.running = False

        # Callbacks
        self.on_vehicle_entry_pending: Optional[Callable] = None
        self.on_vehicle_entry_confirmed: Optional[Callable] = None
        self.on_vehicle_exit: Optional[Callable] = None
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
            print("ℹ️ Running in standalone mode (no P2P peers configured)")
            return

        # Start server
        await self._start_server()

        # Start clients to connect to peers
        await self._start_clients()

        # Start heartbeat loop
        asyncio.create_task(self._heartbeat_loop())

        print(f"P2P Manager started (ID: {self.config.get_this_central_id()})")

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

        for peer in peers:
            peer_id = peer["id"]
            peer_ip = peer["ip"]
            peer_port = peer["p2p_port"]

            client = P2PClient(
                peer_id=peer_id,
                peer_ip=peer_ip,
                peer_port=peer_port,
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
        print(f"🔌 Peer {peer_id} disconnected")

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

                # Send heartbeat to all peers
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

        # Send to connected clients
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
        client = self.clients.get(peer_id)
        if not client:
            print(f"Peer {peer_id} not found")
            return False

        return await client.send(message)

    def get_peer_status(self) -> List[Dict]:
        """Get status of all peers"""
        peers_status = []

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

    def reload_config(self):
        """Reload config and restart connections"""
        print("🔄 Reloading P2P config...")
        # TODO: Implement config reload
        pass
