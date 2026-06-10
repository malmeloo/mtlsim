import logging
from abc import ABC
from collections.abc import Generator
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from threading import Condition, Thread

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class BaseEventModel(BaseModel):
    timestamp: datetime


class BaseEventIngester[EventT: BaseEventModel](ABC):
    """
    Base class for event ingesters. Subclasses should implement the _get_next method to read the next event from the source.
    """

    def __init__(self, src: Path, evt_type: type[EventT]) -> None:
        self._src: Path = src
        self._evt_type: type[EventT] = evt_type

        self._src_handle: TextIOWrapper | None = None

        self._running: bool = False
        self._thread: Thread = Thread(target=self._ingest_loop)
        self._next_evt: EventT | None = None
        self._cv: Condition = Condition()

    @property
    def src(self) -> Path:
        return self._src

    def peek(self) -> EventT | None:
        with self._cv:
            while self._running and self._next_evt is None:
                # Either just started up and haven't ingested the first event yet,
                # or we've consumed all events and are waiting for the next one.
                _ = self._cv.wait()

            return self._next_evt

    def __iter__(self):
        self._running = True
        if not self._thread.is_alive():
            self._thread = Thread(target=self._ingest_loop)
            self._thread.start()

        return self

    def __next__(self) -> EventT:
        with self._cv:
            while self._running and self._next_evt is None:
                # Wait until producer posts an event or signals completion.
                _ = self._cv.wait()

            if self._next_evt is None:
                raise StopIteration

            evt = self._next_evt
            self._next_evt = None
            # Wake producer so it can fetch and publish the next event.
            self._cv.notify_all()
            return evt

    def _ingest_loop(self) -> None:
        try:
            while self._running:
                evt = self._get_next()
                with self._cv:
                    while self._running and self._next_evt is not None:
                        # Wait until consumer has taken the previous event.
                        _ = self._cv.wait()

                    if not self._running:
                        break

                    self._next_evt = evt
                    self._cv.notify_all()
        except StopIteration:
            with self._cv:
                self._running = False
                self._cv.notify_all()

    def _get_next(self) -> EventT:
        if self._src_handle is None:
            self._src_handle = self._src.open("r")

        evt: EventT | None = None
        while evt is None:
            line = self._src_handle.readline().strip()
            if not line:
                # EOF
                raise StopIteration

            try:
                evt = self._evt_type.model_validate_json(line)
            except ValidationError as e:
                logger.warning(f"Failed to validate line: {line} - {e}")

        return evt

    def __del__(self) -> None:
        # cleanup
        if self._src_handle is not None:
            self._src_handle.close()
            self._src_handle = None


def ingest_multiple[EventT: BaseEventModel](
    *ingesters: BaseEventIngester[EventT],
    allow_missing_timestamps: bool = False,
) -> Generator[EventT, None, None]:
    """
    Ingest events from multiple ingesters, yielding them in chronological order.
    """

    _ = allow_missing_timestamps  # for now, we require timestamps for all events

    iters = [iter(ingester) for ingester in ingesters]

    while iters:
        next_evt: EventT | None = None
        next_evt_i: int | None = None

        iter_i = 0
        while iter_i < len(iters):
            iter_evt = iters[iter_i].peek()
            if iter_evt is None:
                # this ingester is done, remove it
                del iters[iter_i]
                continue

            if next_evt is not None and iter_evt.timestamp == next_evt.timestamp:
                ingester_names = [iters[iter_i].__class__.__name__]
                if next_evt_i is not None:
                    ingester_names.append(iters[next_evt_i].__class__.__name__)

                logger.warning(
                    "Events with identical timestamps detected. This may lead to non-deterministic behavior.\n"
                    + f"Offending ingesters: {ingester_names} (ts: {next_evt.timestamp})"
                )

            if next_evt is None or iter_evt.timestamp < next_evt.timestamp:
                next_evt = iter_evt
                next_evt_i = iter_i

            iter_i += 1

        if next_evt is None or next_evt_i is None:
            # no more events to ingest
            break

        yield next(iters[next_evt_i])
