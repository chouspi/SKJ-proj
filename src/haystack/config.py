from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VOLUMES_DIR = DATA_DIR / "volumes"


@dataclass(slots=True)
class Settings:
    broker_url: str = os.getenv("HAYSTACK_BROKER_URL", "ws://127.0.0.1:8001/broker")
    write_topic: str = os.getenv("HAYSTACK_WRITE_TOPIC", "storage.write")
    ack_topic: str = os.getenv("HAYSTACK_ACK_TOPIC", "storage.ack")
    max_volume_size_bytes: int = int(
        os.getenv("HAYSTACK_MAX_VOLUME_SIZE_BYTES", str(100 * 1024 * 1024))
    )
    volumes_dir: Path = VOLUMES_DIR


settings = Settings()
