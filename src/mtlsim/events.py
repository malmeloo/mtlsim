import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Self, final

from pydantic import BaseModel


class Event(BaseModel):
    timestamp: datetime


@final
class EventLogger:
    _WRITE_INTERVAL = 1.0  # seconds

    def __init__(self, file: Path):
        self._file = file
        if self._file.exists():
            raise RuntimeError(f"Output file already exists: {file}")
        # ensure parent dirs exist
        self._file.parent.mkdir(parents=True, exist_ok=True)

        self._event_buf: list[Event] = []
        self._write_thread: Thread | None = None
        self._closed = False

    @classmethod
    def new(cls, base_path: Path, tag: str) -> Self:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file = base_path / f"{tag}_{timestamp}.jsonl"
        return cls(file)

    def _write_loop(self):
        while self._event_buf:
            # thread-safe way to get all events in buf
            to_write: list[Event] = []
            while self._event_buf:
                to_write.append(self._event_buf.pop(0))

            with self._file.open("a") as f:
                for event in to_write:
                    data = event.model_dump_json()
                    _ = f.write(data + "\n")

            time.sleep(self._WRITE_INTERVAL)

    def _ensure_thread(self):
        if self._write_thread is None or not self._write_thread.is_alive():
            self._write_thread = Thread(target=self._write_loop, daemon=True)
            self._write_thread.start()

    def log(self, event: Event):
        if self._closed:
            raise RuntimeError("Cannot log event, logger is closed")

        self._event_buf.append(event)

        self._ensure_thread()

    def wait(self) -> None:
        self._closed = True

        if self._write_thread is not None:
            self._write_thread.join()
