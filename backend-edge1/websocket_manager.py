"""
WebSocket Manager - Quản lý WebSocket connections
"""
from fastapi import WebSocket
from typing import List
import json
import asyncio
import threading


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
    
    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    def broadcast_detections(self, detections):
        """
        Broadcast detections tới tất cả clients
        Called from sync thread - use asyncio.run_coroutine_threadsafe

        Args:
            detections: list of detection dicts
        """
        if not self.active_connections:
            return

        if self.loop is None:
            return

        message = {
            'type': 'detections',
            'data': detections
        }

        # OPTIMIZATION: Serialize CHỈ 1 LẦN thay vì mỗi client 1 lần
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
            json_text: Already serialized JSON string (tránh serialize nhiều lần)
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
            await connection.send_text(json_text)  # Gửi text thay vì send_json
        except Exception:
            # Connection failed - remove it
            self.disconnect(connection)

    def broadcast_barrier_status(self, status):
        """
        Broadcast barrier status change tới tất cả clients

        Args:
            status: dict with {"is_open": bool, "enabled": bool}
        """
        if not self.active_connections:
            return

        if self.loop is None:
            return

        message = {
            'type': 'barrier_status',
            'data': status
        }

        # Serialize once
        json_text = json.dumps(message)

        # Schedule coroutine in event loop from another thread
        asyncio.run_coroutine_threadsafe(
            self._send_to_all(json_text),
            self.loop
        )