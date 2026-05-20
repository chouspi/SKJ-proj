from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import websockets

from .serialization import SerializationFormat, decode_binary_message, decode_text_message, encode_message


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple client for the message broker.")
    parser.add_argument("role", choices=["publisher", "subscriber"])
    parser.add_argument("--url", default="ws://127.0.0.1:8001/broker")
    parser.add_argument("--format", choices=["json", "msgpack"], default="json")
    parser.add_argument("--topic", action="append", required=True, help="Topic to publish or subscribe to.")
    parser.add_argument("--payload", default="{}", help="JSON payload for publisher mode.")
    parser.add_argument("--payload-file", help="Optional binary file attached under payload key.")
    parser.add_argument("--payload-key", default="data", help="Payload key used with --payload-file.")
    parser.add_argument("--object-id", help="Optional object_id inserted into payload.")
    parser.add_argument("--count", type=int, default=1, help="Number of publish messages.")
    parser.add_argument("--interval", type=float, default=0.0, help="Delay between published messages.")
    parser.add_argument("--max-messages", type=int, help="Stop subscriber after this many deliveries.")
    return parser.parse_args()


def build_payload(arguments: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(arguments.payload)
    if not isinstance(payload, dict):
        raise ValueError("Publisher payload must be a JSON object.")
    if arguments.object_id:
        payload["object_id"] = arguments.object_id
    if arguments.payload_file:
        payload[arguments.payload_key] = Path(arguments.payload_file).read_bytes()
    return payload


async def send_message(
    websocket: websockets.ClientConnection,
    payload: dict[str, Any],
    serialization_format: SerializationFormat,
) -> None:
    encoded = encode_message(payload, serialization_format)
    if serialization_format == SerializationFormat.JSON:
        await websocket.send(encoded)
    else:
        await websocket.send(encoded)


async def receive_message(
    websocket: websockets.ClientConnection,
    serialization_format: SerializationFormat,
) -> dict[str, Any]:
    raw_message = await websocket.recv()
    if serialization_format == SerializationFormat.JSON:
        if not isinstance(raw_message, str):
            raise ValueError("Expected text frame from broker.")
        return decode_text_message(raw_message)
    if not isinstance(raw_message, bytes):
        raise ValueError("Expected binary frame from broker.")
    return decode_binary_message(raw_message)


async def run_publisher(arguments: argparse.Namespace, serialization_format: SerializationFormat) -> None:
    payload = build_payload(arguments)
    async with websockets.connect(arguments.url) as websocket:
        for index in range(arguments.count):
            for topic in arguments.topic:
                await send_message(
                    websocket,
                    {
                        "action": "publish",
                        "topic": topic,
                        "payload": {**payload, "sequence": index},
                    },
                    serialization_format,
                )
                print(f"published topic={topic} sequence={index}")
            if arguments.interval > 0:
                await asyncio.sleep(arguments.interval)


async def run_subscriber(arguments: argparse.Namespace, serialization_format: SerializationFormat) -> None:
    received_messages = 0
    async with websockets.connect(arguments.url) as websocket:
        for topic in arguments.topic:
            await send_message(
                websocket,
                {"action": "subscribe", "topic": topic},
                serialization_format,
            )
            confirmation = await receive_message(websocket, serialization_format)
            print(json.dumps(confirmation, default=str))

        while True:
            message = await receive_message(websocket, serialization_format)
            if message.get("action") == "deliver":
                received_messages += 1
            print(json.dumps(message, default=str))
            if arguments.max_messages is not None and received_messages >= arguments.max_messages:
                return


async def main() -> None:
    arguments = parse_arguments()
    serialization_format = SerializationFormat(arguments.format)
    if arguments.role == "publisher":
        await run_publisher(arguments, serialization_format)
        return
    await run_subscriber(arguments, serialization_format)


if __name__ == "__main__":
    asyncio.run(main())
