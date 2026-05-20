from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import BinaryIO


class VolumeManager:
    def __init__(self, volumes_dir: Path, max_volume_size_bytes: int) -> None:
        self.volumes_dir = volumes_dir
        self.max_volume_size_bytes = max_volume_size_bytes
        self._lock = asyncio.Lock()
        self._current_volume_id = 0
        self._current_file: BinaryIO | None = None

    @property
    def current_volume_id(self) -> int:
        return self._current_volume_id

    async def initialize(self) -> None:
        self.volumes_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._close_sync)

    async def append(self, data: bytes) -> tuple[int, int, int]:
        async with self._lock:
            return await asyncio.to_thread(self._append_sync, data)

    async def read(self, volume_id: int, offset: int, size: int) -> bytes:
        return await asyncio.to_thread(self._read_sync, volume_id, offset, size)

    def _initialize_sync(self) -> None:
        existing_volume_ids = sorted(
            int(path.stem.split("_")[1])
            for path in self.volumes_dir.glob("volume_*.dat")
            if path.stem.split("_")[1].isdigit()
        )
        initial_volume_id = existing_volume_ids[-1] if existing_volume_ids else 1
        self._open_volume_sync(initial_volume_id)

    def _close_sync(self) -> None:
        if self._current_file is not None:
            self._current_file.close()
            self._current_file = None

    def _append_sync(self, data: bytes) -> tuple[int, int, int]:
        if self._current_file is None:
            self._open_volume_sync(1)

        assert self._current_file is not None
        self._current_file.seek(0, os.SEEK_END)
        current_size = self._current_file.tell()
        if current_size > 0 and current_size + len(data) > self.max_volume_size_bytes:
            self._open_volume_sync(self._current_volume_id + 1)

        assert self._current_file is not None
        self._current_file.seek(0, os.SEEK_END)
        offset = self._current_file.tell()
        self._current_file.write(data)
        self._current_file.flush()

        return self._current_volume_id, offset, len(data)

    def _read_sync(self, volume_id: int, offset: int, size: int) -> bytes:
        volume_path = self._get_volume_path(volume_id)
        if not volume_path.exists():
            raise FileNotFoundError(f"Volume {volume_id} does not exist.")

        with volume_path.open("rb") as volume_file:
            volume_file.seek(offset)
            return volume_file.read(size)

    def _open_volume_sync(self, volume_id: int) -> None:
        self._close_sync()
        volume_path = self._get_volume_path(volume_id)
        self._current_file = volume_path.open("ab+")
        self._current_file.seek(0, os.SEEK_END)
        self._current_volume_id = volume_id

    def _get_volume_path(self, volume_id: int) -> Path:
        return self.volumes_dir / f"volume_{volume_id}.dat"
