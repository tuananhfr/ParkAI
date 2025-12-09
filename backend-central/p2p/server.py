"""
P2P WebSocket Server - Nhận connections từ peer centrals
"""
import asyncio
import websockets
import json
from typing import Set, Callable
from datetime import datetime

from .protocol import P2PMessage, validate_message


class P2PServer:
    """WebSocket server để nhận connections từ peer centrals"""

    def __init__(self, host: str, port: int, on_message: Callable):
        self.host = host
        self.port = port
        self.on_message = on_message  # Callback khi nhan message tu peer
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.running = False

    async def start(self):
        """Start WebSocket server"""
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port
            )
            self.running = True
            print(f"P2P Server started on ws://{self.host}:{self.port}")

        except Exception as e:
            print(f"Failed to start P2P server: {e}")
            raise

    async def stop(self):
        """Stop WebSocket server"""
        self.running = False

        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        print("P2P Server stopped")

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle incoming client connection"""
        peer_address = websocket.remote_address
        print(f"P2P peer connected: {peer_address}")

        self.clients.add(websocket)

        try:
            async for message in websocket:
                await self._process_message(message, websocket)

        except websockets.exceptions.ConnectionClosed:
            print(f"P2P peer disconnected: {peer_address}")

        except Exception as e:
            print(f"Error handling P2P client {peer_address}: {e}")

        finally:
            self.clients.discard(websocket)

    async def _process_message(self, message: str, websocket: websockets.WebSocketServerProtocol):
        """Process incoming message from peer"""
        try:
            # Parse JSON
            data = json.loads(message)

            # Validate message
            is_valid, error = validate_message(data)
            if not is_valid:
                print(f"Invalid P2P message: {error}")
                await self._send_error(websocket, error)
                return

            # Convert to P2PMessage
            p2p_msg = P2PMessage.from_dict(data)

            # Call callback
            if self.on_message:
                await self.on_message(p2p_msg)

        except json.JSONDecodeError as e:
            print(f"Invalid JSON from peer: {e}")
            await self._send_error(websocket, "Invalid JSON")

        except Exception as e:
            print(f"Error processing P2P message: {e}")
            import traceback
            traceback.print_exc()

    async def _send_error(self, websocket: websockets.WebSocketServerProtocol, error: str):
        """Send error message to peer"""
        try:
            error_msg = json.dumps({
                "type": "ERROR",
                "error": error,
                "timestamp": int(datetime.now().timestamp() * 1000)
            })
            await websocket.send(error_msg)

        except Exception as e:
            print(f"Error sending error message: {e}")

    async def broadcast(self, message: P2PMessage):
        """Broadcast message to all connected peers"""
        if not self.clients:
            return

        json_msg = message.to_json()
        disconnected = set()

        for client in self.clients:
            try:
                await client.send(json_msg)

            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)

            except Exception as e:
                print(f"Error broadcasting to peer: {e}")
                disconnected.add(client)

        # Remove disconnected clients
        for client in disconnected:
            self.clients.discard(client)
