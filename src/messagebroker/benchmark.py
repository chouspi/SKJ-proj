from __future__ import annotations

import argparse
import asyncio
import time
from uuid import uuid4

import websockets

from .serialization import SerializationFormat, decode_binary_message, decode_text_message, encode_message


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the message broker.")
    parser.add_argument("--url", default="ws://127.0.0.1:8001/broker")
    parser.add_argument("--format", choices=["json", "msgpack", "both"], default="both")
    parser.add_argument("--publishers", type=int, default=5)
    parser.add_argument("--subscribers", type=int, default=5)
    parser.add_argument("--messages", type=int, default=10_000)
    return parser.parse_args()


async def send_message(
    websocket: websockets.ClientConnection,
    payload: dict[str, object],
    serialization_format: SerializationFormat,
) -> None:
    await websocket.send(encode_message(payload, serialization_format))


async def receive_message(
    websocket: websockets.ClientConnection,
    serialization_format: SerializationFormat,
) -> dict[str, object]:
    raw_message = await websocket.recv()
    if serialization_format == SerializationFormat.JSON:
        if not isinstance(raw_message, str):
            raise ValueError("Expected text frame from broker.")
        return decode_text_message(raw_message)
    if not isinstance(raw_message, bytes):
        raise ValueError("Expected binary frame from broker.")
    return decode_binary_message(raw_message)


async def subscriber_task(
    url: str,
    topic: str,
    serialization_format: SerializationFormat,
    expected_messages: int,
    ready_event: asyncio.Event,
) -> None:
    received_messages = 0
    async with websockets.connect(url) as websocket:
        await send_message(
            websocket,
            {"action": "subscribe", "topic": topic},
            serialization_format,
        )
        await receive_message(websocket, serialization_format)
        ready_event.set()

        while received_messages < expected_messages:
            message = await receive_message(websocket, serialization_format)
            if message.get("action") == "deliver":
                received_messages += 1


async def publisher_task(
    url: str,
    topic: str,
    serialization_format: SerializationFormat,
    messages: int,
    publisher_id: int,
) -> None:
    async with websockets.connect(url) as websocket:
        for index in range(messages):
            await send_message(
                websocket,
                {
                    "action": "publish",
                    "topic": topic,
                    "payload": {
                        "publisher_id": publisher_id,
                        "sequence": index,
                        "sample": "message-broker-benchmark",
                    },
                },
                serialization_format,
            )


async def run_single_benchmark(
    url: str,
    serialization_format: SerializationFormat,
    publishers: int,
    subscribers: int,
    messages: int,
) -> dict[str, float | int | str]:
    topic = f"benchmark-{serialization_format.value}-{uuid4().hex}"
    ready_events = [asyncio.Event() for _ in range(subscribers)]
    expected_messages_per_subscriber = publishers * messages
    total_deliveries = expected_messages_per_subscriber * subscribers

    subscriber_coroutines = [
        subscriber_task(url, topic, serialization_format, expected_messages_per_subscriber, ready_event)
        for ready_event in ready_events
    ]
    subscriber_tasks = [asyncio.create_task(coroutine) for coroutine in subscriber_coroutines]

    await asyncio.gather(*(ready_event.wait() for ready_event in ready_events))

    start = time.perf_counter()
    await asyncio.gather(
        *(
            publisher_task(url, topic, serialization_format, messages, publisher_id)
            for publisher_id in range(publishers)
        )
    )
    await asyncio.gather(*subscriber_tasks)
    elapsed = time.perf_counter() - start

    return {
        "format": serialization_format.value,
        "publishers": publishers,
        "subscribers": subscribers,
        "messages_per_publisher": messages,
        "total_published_messages": publishers * messages,
        "total_deliveries": total_deliveries,
        "elapsed_seconds": elapsed,
        "throughput_msg_per_sec": total_deliveries / elapsed if elapsed > 0 else 0.0,
    }


async def main() -> None:
    arguments = parse_arguments()
    formats = (
        [SerializationFormat.JSON, SerializationFormat.MSGPACK]
        if arguments.format == "both"
        else [SerializationFormat(arguments.format)]
    )

    for serialization_format in formats:
        result = await run_single_benchmark(
            arguments.url,
            serialization_format,
            arguments.publishers,
            arguments.subscribers,
            arguments.messages,
        )
        print(
            f"format={result['format']} total_deliveries={result['total_deliveries']} "
            f"elapsed={result['elapsed_seconds']:.3f}s throughput={result['throughput_msg_per_sec']:.2f} msg/s"
        )


if __name__ == "__main__":
    asyncio.run(main())
