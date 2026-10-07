import json
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, session_id: int, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: int, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast_to_session(self, session_id: int, message: dict):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_text(json.dumps(message))

ws_manager = ConnectionManager()

@router.websocket("/live/{session_id}")
async def websocket_live_inspection(websocket: WebSocket, session_id: int):
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Heartbeat ping/pong or client trigger
            await websocket.send_text(json.dumps({"status": "received", "data": data}))
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)