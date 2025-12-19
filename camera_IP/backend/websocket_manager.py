"""
WebSocket Manager - Quản lý WebSocket connections cho license plate detection
"""
from fastapi import WebSocket
from typing import List
import json
import asyncio


class WebSocketManager:
    """Quản lý WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop = None  # Store event loop reference

    def set_event_loop(self, loop):
        """Set event loop from FastAPI"""
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        """Accept connection mới"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Total connections: {len(self.active_connections)}")

    def broadcast_detections(self, message):
        """
        Broadcast message tới tất cả clients
        Called from sync thread - use asyncio.run_coroutine_threadsafe

        Args:
            message: dict message to broadcast (already formatted with camera_id, frame, detections, etc.)
        """
        if not self.active_connections:
            return

        if self.loop is None:
            return

        # Serialize CHỈ 1 LẦN thay vì mỗi client 1 lần
        json_text = json.dumps(message)

        # Schedule coroutine in event loop from another thread
        asyncio.run_coroutine_threadsafe(
            self._send_to_all(json_text),
            self.loop
        )

    async def _send_to_all(self, json_text):
        """
        Send message tới tất cả connections ĐỒNG THỜI (concurrent)

        Args:
            json_text: Already serialized JSON string
        """
        if not self.active_connections:
            return

        # Tạo tasks để gửi song song
        tasks = [
            self._send_to_one(connection, json_text)
            for connection in self.active_connections.copy()  # Copy để tránh modify during iteration
        ]

        # Gửi song song, không đợi nhau
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_one(self, connection, json_text):
        """
        Send message tới 1 connection, tự động remove nếu fail

        Args:
            json_text: Already serialized JSON string
        """
        try:
            await connection.send_text(json_text)
        except Exception:
            # Connection failed - remove it
            self.disconnect(connection)
