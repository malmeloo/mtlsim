from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .resolver import DNSResolverQueryErrorEvent, DNSResolverQueryEvent
from .zone import DNSZoneLadderAddEvent, DNSZoneLadderDeleteEvent, DNSZoneRRSetAddEvent


class AnalysisResult(BaseModel):
    run_name: str
    timestamp: datetime | None

    time_between_fullsig: list[float]
    queries_between_fullsig: list[int]
    ladder_sizes: dict[str, list[tuple[datetime, int]]]


# ugh i miss typescript's type system so much

type Event = (
    DNSResolverQueryErrorEvent
    | DNSResolverQueryEvent
    | DNSZoneLadderAddEvent
    | DNSZoneLadderDeleteEvent
    | DNSZoneRRSetAddEvent
)

_EVENTS: tuple[type[Event], ...] = (
    DNSResolverQueryErrorEvent,
    DNSResolverQueryEvent,
    DNSZoneLadderAddEvent,
    DNSZoneLadderDeleteEvent,
    DNSZoneRRSetAddEvent,
)


def _parse_line(line: str) -> Event:
    for cls in _EVENTS:
        try:
            return cls.model_validate_json(line)
        except Exception:
            continue

    raise ValueError(f"Could not parse line into any known event type: {line}")


def analyze_log(
    log_file: Path,
    run_name: str,
    timestamp: datetime | None,
) -> AnalysisResult:
    result = AnalysisResult(
        run_name=run_name,
        timestamp=timestamp,
        time_between_fullsig=[],
        queries_between_fullsig=[],
        ladder_sizes={},
    )

    last_fullsig_time: float | None = None
    fullsig_query_count = 0

    with log_file.open() as f:
        while line := f.readline():
            event = _parse_line(line)

            if isinstance(event, DNSZoneLadderAddEvent):
                result.ladder_sizes[event.sid] = [(event.timestamp, 0)]
            elif isinstance(event, DNSZoneRRSetAddEvent):
                cur_size = result.ladder_sizes[event.sid][-1][-1]
                result.ladder_sizes[event.sid].append(
                    (event.timestamp, cur_size + event.count)
                )
            elif isinstance(event, DNSResolverQueryEvent):
                if event.sig_type == "condensed":
                    fullsig_query_count += 1
                elif event.sig_type == "full":
                    if last_fullsig_time is not None:
                        result.time_between_fullsig.append(
                            (event.timestamp.timestamp() - last_fullsig_time)
                        )
                        result.queries_between_fullsig.append(fullsig_query_count)

                    last_fullsig_time = event.timestamp.timestamp()
                    fullsig_query_count = 0
            elif isinstance(event, DNSZoneLadderDeleteEvent):
                result.ladder_sizes[event.sid].append((event.timestamp, 0))
            elif isinstance(event, DNSResolverQueryErrorEvent):  # pyright: ignore[reportUnnecessaryIsInstance]
                # for now we just ignore these, but maybe in the future we want to track them as well
                pass
            else:
                raise ValueError(
                    f"Analyzer does not understand event type: {type(event)}"
                )

    return result
