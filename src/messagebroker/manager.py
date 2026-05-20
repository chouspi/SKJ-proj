from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from fastapi import WebSocket

from .serialization import SerializationFormat, encode_message


@dataclass(slots=True)
class ClientConnection:
    websocket: WebSocket
    serialization_format: SerializationFormat = SerializationFormat.JSON
    topics: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, dict[int, ClientConnection]] = {}
        self.clients: dict[int, ClientConnection] = {}
        self._lock = asyncio.Lock()
        self._message_ids = count(1)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients[id(websocket)] = ClientConnection(websocket=websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            client = self.clients.pop(id(websocket), None)
            if client is None:
                return

            for topic in list(client.topics):
                subscribers = self.active_connections.get(topic)
                if subscribers is None:
                    continue
                subscribers.pop(id(websocket), None)
                if not subscribers:
                    del self.active_connections[topic]

    async def set_serialization_format(
        self,
        websocket: WebSocket,
        serialization_format: SerializationFormat,
    ) -> ClientConnection:
        async with self._lock:
            client = self.clients[id(websocket)]
            client.serialization_format = serialization_format
            return client

    async def subscribe(self, websocket: WebSocket, topic: str) -> ClientConnection:
        async with self._lock:
            client = self.clients[id(websocket)]
            client.topics.add(topic)
            self.active_connections.setdefault(topic, {})[id(websocket)] = client
            return client

    async def next_message_id(self) -> int:
        async with self._lock:
            return next(self._message_ids)

    async def send_to_client(self, client: ClientConnection, payload: dict[str, Any]) -> None:
        encoded = encode_message(payload, client.serialization_format)
        if client.serialization_format == SerializationFormat.JSON:
            await client.websocket.send_text(encoded)
        else:
            await client.websocket.send_bytes(encoded)

    async def send_to_websocket(
        self,
        websocket: WebSocket,
        serialization_format: SerializationFormat,
        payload: dict[str, Any],
    ) -> None:
        encoded = encode_message(payload, serialization_format)
        if serialization_format == SerializationFormat.JSON:
            await websocket.send_text(encoded)
        else:
            await websocket.send_bytes(encoded)

    async def broadcast(self, topic: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self.active_connections.get(topic, {}).values())

        failed_clients: list[ClientConnection] = []

        async def _send(client: ClientConnection) -> None:
            try:
                await self.send_to_client(client, payload)
            except Exception:
                failed_clients.append(client)

        if subscribers:
            await asyncio.gather(*(_send(client) for client in subscribers))

        for client in failed_clients:
            await self.disconnect(client.websocket)
