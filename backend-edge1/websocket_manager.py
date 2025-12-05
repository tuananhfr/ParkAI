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
        self.barrier_status_subscribers = []  # List of callbacks for barrier status changes
    
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

        # Schedule coroutine in event loop from another thread
        asyncio.run_coroutine_threadsafe(
            self._send_to_all(message),
            self.loop
        )

    def broadcast_barrier_status(self, status):
        """
        Broadcast barrier status change tới tất cả clients
        CHỈ GỬI KHI STATUS THAY ĐỔI (không polling!)

        Args:
            status: dict với is_open, enabled
        """
        if not self.active_connections:
            return

        if self.loop is None:
            return

        message = {
            'type': 'barrier_status',
            'data': status
        }

        # Schedule coroutine in event loop from another thread
        asyncio.run_coroutine_threadsafe(
            self._send_to_all(message),
            self.loop
        )
        
        # Notify subscribers (callbacks) về barrier status change
        for subscriber_callback in self.barrier_status_subscribers:
            try:
                # Run callback in thread pool để không block
                asyncio.run_coroutine_threadsafe(
                    self.loop.run_in_executor(None, subscriber_callback, status),
                    self.loop
                )
            except Exception as e:
                print(f"Error calling barrier status subscriber: {e}")
    
    def subscribe_to_barrier_status(self, callback):
        """Subscribe để nhận barrier status changes"""
        if callback not in self.barrier_status_subscribers:
            self.barrier_status_subscribers.append(callback)
    
    def unsubscribe_from_barrier_status(self, callback):
        """Unsubscribe khỏi barrier status changes"""
        if callback in self.barrier_status_subscribers:
            self.barrier_status_subscribers.remove(callback)
    
    async def _send_to_all(self, message):
        """Send message tới tất cả connections"""
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Remove disconnected
        for conn in disconnected:
            self.disconnect(conn)