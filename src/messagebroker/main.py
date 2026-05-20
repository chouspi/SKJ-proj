from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .manager import ConnectionManager
from .protocol import DeliverEvent, ErrorEvent, PublishCommand, SubscribedEvent, incoming_message_adapter
from .serialization import SerializationFormat, decode_incoming_frame


def create_app() -> FastAPI:
    app = FastAPI(
        title="Message Broker",
        description="Async Pub/Sub message broker using FastAPI WebSockets.",
        version="1.0.0",
    )
    manager = ConnectionManager()
    app.state.manager = manager

    @app.get("/")
    async def health() -> dict[str, str]:
        return {"message": "Message broker is running."}

    @app.websocket("/broker")
    async def broker_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        last_format = SerializationFormat.JSON

        try:
            while True:
                frame = await websocket.receive()
                if frame.get("type") == "websocket.disconnect":
                    break

                try:
                    serialization_format, payload = decode_incoming_frame(frame)
                    last_format = serialization_format
                    await manager.set_serialization_format(websocket, serialization_format)
                    incoming = incoming_message_adapter.validate_python(payload)
                except (ValidationError, ValueError) as exc:
                    error_event = ErrorEvent(detail=str(exc))
                    await manager.send_to_websocket(
                        websocket,
                        last_format,
                        error_event.model_dump(mode="json"),
                    )
                    continue

                if isinstance(incoming, PublishCommand):
                    delivery_event = DeliverEvent(
                        topic=incoming.topic,
                        message_id=await manager.next_message_id(),
                        payload=incoming.payload,
                    )
                    await manager.broadcast(incoming.topic, delivery_event.model_dump(mode="json"))
                    continue

                await manager.subscribe(websocket, incoming.topic)
                subscribed_event = SubscribedEvent(topic=incoming.topic)
                await manager.send_to_websocket(
                    websocket,
                    last_format,
                    subscribed_event.model_dump(mode="json"),
                )
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(websocket)

    return app


app = create_app()
