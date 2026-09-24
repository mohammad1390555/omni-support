import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # logging.getLogger("WebSocketManager")

class WebSocketManager:
    
        # All connected agents/admins
        self.agent_connections: Set[WebSocket] = set()
        # Customer connections grouped by conversation_id
        self.conversation_connections: Dict[str, Set[WebSocket]] = {}

    async def connect_agent(self, websocket: WebSocket):
        await websocket.accept()
        self.agent_connections.add(websocket)
        logger.info(f"Agent connected. Total active agents: {len(self.agent_connections)}")

    def disconnect_agent(self, websocket: WebSocket):
        self.agent_connections.discard(websocket)
        logger.info(f"Agent disconnected. Total active agents: {len(self.agent_connections)}")

    async def connect_customer(self, conversation_id: str, websocket: WebSocket):
        await websocket.accept()
        if conversation_id not in self.conversation_connections:
            self.conversation_connections[conversation_id] = set()
        self.conversation_connections[conversation_id].add(websocket)
        logger.info(f"Customer connected to conv {conversation_id}. Total listeners: {len(self.conversation_connections[conversation_id])}")

    def disconnect_customer(self, conversation_id: str, websocket: WebSocket):
        if conversation_id in self.conversation_connections:
            self.conversation_connections[conversation_id].discard(websocket)
            if not self.conversation_connections[conversation_id]:
                del self.conversation_connections[conversation_id]
        logger.info(f"Customer disconnected from conv {conversation_id}")

    async def broadcast_to_agents(self, event_type: str, data: Any):
        """Broadcasts an event to all connected admin/agent tabs."""
        message = json.dumps({"event": event_type, "data": data}, default=str)
        dead = []
        for ws in self.agent_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.agent_connections.discard(ws)

    async def send_to_conversation(self, conversation_id: str, event_type: str, data: Any):
        """Sends an event both to the specific customer and broadcasts to agents."""
        message = json.dumps({"event": event_type, "conversation_id": conversation_id, "data": data}, default=str)
        
        # Send to customer sockets
        if conversation_id in self.conversation_connections:
            dead = []
            for ws in self.conversation_connections[conversation_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.conversation_connections[conversation_id].discard(ws)

        # Also push to agents so agent's live view updates instantly
        await self.broadcast_to_agents(event_type, data)

ws_manager = WebSocketManager()
