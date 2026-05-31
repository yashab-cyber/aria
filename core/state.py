import asyncio
from typing import Set
from fastapi import WebSocket

class StateManager:
    def __init__(self):
        self._current_state = "idle"
        self._listeners: Set[WebSocket] = set()

    @property
    def current_state(self) -> str:
        return self._current_state

    def register(self, ws: WebSocket):
        self._listeners.add(ws)

    def unregister(self, ws: WebSocket):
        self._listeners.discard(ws)

    async def set_state(self, state: str):
        if state not in ["idle", "thinking", "analyzing", "speaking"]:
            return
        if self._current_state == state:
            return
        self._current_state = state
        await self._broadcast({"type": "state_change", "state": state})

    async def _broadcast(self, data: dict):
        disconnected = set()
        for ws in self._listeners:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self._listeners.discard(ws)

state_manager = StateManager()
