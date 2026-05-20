from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import httpx

try:
    from .config import settings
except ImportError:
    from config import settings


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact a Haystack volume file.")
    parser.add_argument("volume_id", type=int, help="Volume ID to compact.")
    parser.add_argument("--gateway-url", default=os.getenv("HAYSTACK_GATEWAY_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--volumes-dir", type=Path, default=settings.volumes_dir)
    return parser.parse_args()


def read_exact(volume_path: Path, offset: int, size: int) -> bytes:
    with volume_path.open("rb") as volume_file:
        volume_file.seek(offset)
        data = volume_file.read(size)
    if len(data) != size:
        raise RuntimeError(f"Expected {size} bytes from {volume_path}, got {len(data)} bytes.")
    return data


def compact_volume(volume_id: int, gateway_url: str, volumes_dir: Path) -> None:
    if volume_id < 1:
        raise ValueError("Volume ID must be >= 1.")

    volumes_dir.mkdir(parents=True, exist_ok=True)
    source_path = volumes_dir / f"volume_{volume_id}.dat"
    compacted_path = volumes_dir / f"volume_{volume_id}_compacted.dat"
    backup_path = volumes_dir / f"volume_{volume_id}.bak"

    if not source_path.exists():
        raise FileNotFoundError(f"Volume does not exist: {source_path}")

    with httpx.Client(timeout=60.0) as client:
        response = client.get(f"{gateway_url.rstrip('/')}/internal/volumes/{volume_id}/objects")
        response.raise_for_status()
        live_objects: list[dict[str, Any]] = response.json()

        updates: list[tuple[str, int, int]] = []
        with compacted_path.open("wb") as compacted_file:
            for item in live_objects:
                object_id = item["object_id"]
                old_offset = int(item["offset"])
                size = int(item["size"])
                data = read_exact(source_path, old_offset, size)
                new_offset = compacted_file.tell()
                compacted_file.write(data)
                updates.append((object_id, new_offset, size))

        for object_id, new_offset, size in updates:
            update_response = client.patch(
                f"{gateway_url.rstrip('/')}/internal/objects/{object_id}/location",
                json={
                    "volume_id": volume_id,
                    "offset": new_offset,
                    "size": size,
                },
            )
            update_response.raise_for_status()

    if backup_path.exists():
        backup_path.unlink()
    source_path.replace(backup_path)
    compacted_path.replace(source_path)
    backup_path.unlink(missing_ok=True)

    print(
        f"Compacted volume_{volume_id}.dat: kept {len(live_objects)} objects, "
        f"new_size={source_path.stat().st_size} bytes"
    )


def main() -> None:
    arguments = parse_arguments()
    compact_volume(arguments.volume_id, arguments.gateway_url, arguments.volumes_dir)


if __name__ == "__main__":
    main()
