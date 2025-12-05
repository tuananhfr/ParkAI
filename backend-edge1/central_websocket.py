"""
Central WebSocket Client - Nhận real-time updates từ Central
"""
import websockets
import json
import asyncio
import threading
from typing import Callable, Optional


class CentralWebSocketClient:
    """
    WebSocket client to receive updates from Central
    - Auto-reconnect khi disconnect
    - Keep-alive ping/pong
    - Thread-safe callback
    """

    def __init__(
        self,
        central_ws_url: str,
        edge_id: str,
        on_message_callback: Optional[Callable] = None
    ):
        self.central_ws_url = central_ws_url
        self.edge_id = edge_id
        self.on_message_callback = on_message_callback
        self.ws = None
        self.running = False
        self.thread = None
        self.is_connected = False

    def start(self):
        """Start WebSocket client in background thread"""
        if self.running:
            print(" WebSocket client already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        print(f"WebSocket client started for {self.edge_id}")

    def stop(self):
        """Stop WebSocket client"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print(f"WebSocket client stopped for {self.edge_id}")

    def _run_async_loop(self):
        """Run asyncio loop in thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        """Connect and listen to Central WebSocket with auto-reconnect"""
        retry_delay = 5  # seconds

        while self.running:
            try:
                print(f"🔌 Connecting to Central WebSocket: {self.central_ws_url}")

                async with websockets.connect(
                    self.central_ws_url,
                    ping_interval=30,  # Auto ping every 30s
                    ping_timeout=10
                ) as ws:
                    self.ws = ws
                    self.is_connected = True
                    print(f"Connected to Central WebSocket")

                    # Listen messages
                    async for message in ws:
                        if not self.running:
                            break

                        # Handle message
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                self.is_connected = False
                print(f"WebSocket connection closed: {e}")
                print(f"⏳ Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)

            except Exception as e:
                self.is_connected = False
                print(f"WebSocket error: {e}")
                print(f"⏳ Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)

        # Cleanup
        self.is_connected = False
        self.ws = None

    async def _handle_message(self, message: str):
        """Handle message from Central"""
        if message == "pong":
            return  # Ignore pong

        try:
            data = json.loads(message)

            # Log
            msg_type = data.get('type', 'unknown')
            print(f"📥 [{self.edge_id}] Received: {msg_type}")

            # Callback
            if self.on_message_callback:
                # Run callback in thread pool để không block asyncio loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.on_message_callback, data)

        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
        except Exception as e:
            print(f"Error handling message: {e}")

    def get_status(self) -> dict:
        """Get WebSocket status"""
        return {
            "running": self.running,
            "connected": self.is_connected,
            "url": self.central_ws_url,
            "edge_id": self.edge_id
        }
