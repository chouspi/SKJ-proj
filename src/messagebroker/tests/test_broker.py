from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.messagebroker.main import create_app


@pytest.mark.asyncio
async def test_client_can_connect_and_disconnect() -> None:
    app = create_app()

    def scenario() -> None:
        with TestClient(app) as client:
            with client.websocket_connect("/broker") as websocket:
                websocket.send_json({"action": "subscribe", "topic": "status"})
                confirmation = websocket.receive_json()
                assert confirmation == {"action": "subscribed", "topic": "status"}

            assert app.state.manager.active_connections == {}

    await asyncio.to_thread(scenario)


@pytest.mark.asyncio
async def test_message_reaches_matching_topic_subscriber() -> None:
    app = create_app()

    def scenario() -> None:
        with TestClient(app) as client:
            with client.websocket_connect("/broker") as subscriber:
                subscriber.send_json({"action": "subscribe", "topic": "topic-x"})
                assert subscriber.receive_json() == {"action": "subscribed", "topic": "topic-x"}

                with client.websocket_connect("/broker") as publisher:
                    publisher.send_json(
                        {
                            "action": "publish",
                            "topic": "topic-x",
                            "payload": {"value": 42},
                        }
                    )

                delivered = subscriber.receive_json()
                assert delivered["action"] == "deliver"
                assert delivered["topic"] == "topic-x"
                assert delivered["payload"] == {"value": 42}
                assert delivered["message_id"] >= 1

    await asyncio.to_thread(scenario)


@pytest.mark.asyncio
async def test_message_does_not_reach_other_topic_subscriber() -> None:
    app = create_app()

    def scenario() -> None:
        with TestClient(app) as client:
            with client.websocket_connect("/broker") as subscriber:
                subscriber.send_json({"action": "subscribe", "topic": "topic-x"})
                assert subscriber.receive_json() == {"action": "subscribed", "topic": "topic-x"}

                with client.websocket_connect("/broker") as publisher:
                    publisher.send_json(
                        {
                            "action": "publish",
                            "topic": "topic-y",
                            "payload": {"value": "wrong-topic"},
                        }
                    )
                    publisher.send_json(
                        {
                            "action": "publish",
                            "topic": "topic-x",
                            "payload": {"value": "correct-topic"},
                        }
                    )

                delivered = subscriber.receive_json()
                assert delivered["topic"] == "topic-x"
                assert delivered["payload"] == {"value": "correct-topic"}

    await asyncio.to_thread(scenario)
