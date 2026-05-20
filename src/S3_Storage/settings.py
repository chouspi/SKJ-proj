from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    broker_url: str = os.getenv("S3_BROKER_URL", "ws://127.0.0.1:8001/broker")
    haystack_base_url: str = os.getenv("S3_HAYSTACK_BASE_URL", "http://127.0.0.1:8002")
    storage_write_topic: str = os.getenv("S3_STORAGE_WRITE_TOPIC", "storage.write")
    storage_ack_topic: str = os.getenv("S3_STORAGE_ACK_TOPIC", "storage.ack")
    image_jobs_topic: str = os.getenv("S3_IMAGE_JOBS_TOPIC", "image.jobs")


settings = Settings()
