from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    broker_url: str = os.getenv("IMG_BROKER_URL", "ws://127.0.0.1:8001/broker")
    gateway_base_url: str = os.getenv("IMG_GATEWAY_BASE_URL", "http://127.0.0.1:8000")
    jobs_topic: str = os.getenv("IMG_JOBS_TOPIC", "image.jobs")
    done_topic: str = os.getenv("IMG_DONE_TOPIC", "image.done")


settings = Settings()
