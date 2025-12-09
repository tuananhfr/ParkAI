"""
P2P WebSocket Client - Connect đến peer centrals
"""
import asyncio
import websockets
import json
from typing import Callable, Optional
from datetime import datetime

from .protocol import P2PMessage, validate_message


class P2PClient:
    """WebSocket client để connect đến 1 peer central"""

    def __init__(
        self,
        peer_id: str,
        peer_ip: str,
        peer_port: int,
        this_central_id: str,
        on_message: Callable,
        on_connected: Optional[Callable] = None,
        on_disconnected: Optional[Callable] = None
    ):
        self.peer_id = peer_id
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.this_central_id = this_central_id
        self.on_message = on_message
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected

        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.connected = False
        self.reconnect_delay = 10  # seconds
        self.last_ping_time = None

    @property
    def uri(self) -> str:
        """WebSocket URI - connect to FastAPI WebSocket endpoint"""
        return f"ws://{self.peer_ip}:{self.peer_port}/ws/p2p"

    async def start(self):
        """Start client and maintain connection"""
        self.running = True
        asyncio.create_task(self._connection_loop())

    async def stop(self):
        """Stop client"""
        self.running = False

        if self.websocket:
            await self.websocket.close()

        self.connected = False
        print(f"P2P Client to {self.peer_id} stopped")

    async def _connection_loop(self):
        """Maintain connection with auto-reconnect"""
        while self.running:
            try:
                await self._connect()

            except Exception as e:
                print(f"P2P Client {self.peer_id} error: {e}")

            if self.running:
                print(f"Reconnecting to {self.peer_id} in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)

    async def _connect(self):
        """Connect to peer and listen for messages"""
        try:
            print(f"Connecting to P2P peer {self.peer_id} ({self.uri})...")

            async with websockets.connect(
                self.uri,
                ping_interval=30,
                ping_timeout=10
            ) as websocket:
                self.websocket = websocket

                # Send identification message first
                identification = {
                    "peer_id": self.this_central_id
                }
                await websocket.send(json.dumps(identification))
                print(f"Sent identification to {self.peer_id}: {self.this_central_id}")

                self.connected = True
                print(f"Connected to P2P peer {self.peer_id}")

                # Call connected callback
                if self.on_connected:
                    await self.on_connected(self.peer_id)

                # Listen for messages
                async for message in websocket:
                    await self._process_message(message)

        except websockets.exceptions.ConnectionClosed:
            print(f"Disconnected from P2P peer {self.peer_id}")

        except Exception as e:
            print(f"Error connecting to {self.peer_id}: {e}")

        finally:
            self.connected = False
            self.websocket = None

            # Call disconnected callback
            if self.on_disconnected:
                await self.on_disconnected(self.peer_id)

    async def _process_message(self, message: str):
        """Process incoming message from peer"""
        try:
            # Parse JSON
            data = json.loads(message)

            # Skip error messages
            if data.get("type") == "ERROR":
                print(f"Error from peer {self.peer_id}: {data.get('error')}")
                return

            # Validate message
            is_valid, error = validate_message(data)
            if not is_valid:
                print(f"Invalid message from {self.peer_id}: {error}")
                return

            # Convert to P2PMessage
            p2p_msg = P2PMessage.from_dict(data)

            # Update last ping time for heartbeat
            if p2p_msg.type == "HEARTBEAT":
                self.last_ping_time = datetime.now()

            # Call callback
            if self.on_message:
                await self.on_message(p2p_msg, self.peer_id)

        except json.JSONDecodeError as e:
            print(f"Invalid JSON from {self.peer_id}: {e}")

        except Exception as e:
            print(f"Error processing message from {self.peer_id}: {e}")
            import traceback
            traceback.print_exc()

    async def send(self, message: P2PMessage) -> bool:
        """Send message to peer"""
        if not self.connected or not self.websocket:
            return False

        try:
            json_msg = message.to_json()
            await self.websocket.send(json_msg)
            return True

        except websockets.exceptions.ConnectionClosed:
            print(f"Cannot send to {self.peer_id}: Connection closed")
            self.connected = False
            return False

        except Exception as e:
            print(f"Error sending to {self.peer_id}: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to peer"""
        return self.connected

    def get_status(self) -> dict:
        """Get client status"""
        return {
            "peer_id": self.peer_id,
            "peer_ip": self.peer_ip,
            "peer_port": self.peer_port,
            "connected": self.connected,
            "last_ping_time": self.last_ping_time.isoformat() if self.last_ping_time else None
        }
