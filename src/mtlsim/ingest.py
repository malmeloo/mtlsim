from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

import dns.zone
import numpy as np
import polars

from .ingesters import DNSQueryEvent, DNSZoneUpdateEvent


def extract_rrsets_from_zone(
    file: Path, origin: str, num_cycles: int = 1
) -> Generator[DNSZoneUpdateEvent, None, None]:
    zone = dns.zone.from_text(
        file.read_text(),
        # always assume root zone, we don't care about the actual origin for our purposes
        origin=origin,
        check_origin=False,
    )

    rrsets: set[tuple[str, str]] = set()
    rrset_expirations: dict[int, set[tuple[str, str]]] = defaultdict(set)
    rrset_validities: dict[tuple[str, str], int] = {}
    earliest_inception: int | None = None

    # extract all rrsigs and the inception/expiration times
    for name, node in zone.nodes.items():
        for rdataset in node.rdatasets:
            if rdataset.rdtype != dns.rdatatype.RRSIG:  # pyright: ignore[reportAttributeAccessIssue]
                continue

            for rdata in rdataset:
                # These are ints like 20260609170000
                if earliest_inception is None or rdata.inception < earliest_inception:
                    earliest_inception = rdata.inception

                rrset = (str(name), dns.rdatatype.to_text(rdataset.rdtype))  # pyright: ignore[reportAttributeAccessIssue]
                rrsets.add(rrset)
                rrset_expirations[rdata.expiration].add(rrset)
                rrset_validities[rrset] = rdata.expiration - rdata.inception

    if not isinstance(earliest_inception, int):
        raise ValueError("No RRSIG records found in zone file")

    # single origin event with all rrsets, using earliest inception as timestamp
    yield DNSZoneUpdateEvent(
        timestamp=datetime.fromtimestamp(earliest_inception),
        added=list(rrsets),
        removed=[],
    )

    for _ in range(num_cycles):
        new_expirations: dict[int, set[tuple[str, str]]] = defaultdict(set)

        # repeat the expirations to simulate multiple cycles of rrset expirations and renewals
        for expiration, exp_rrsets in rrset_expirations.items():
            yield DNSZoneUpdateEvent(
                timestamp=datetime.fromtimestamp(expiration),
                added=list(exp_rrsets),
                removed=[],
            )

            for rrset in exp_rrsets:
                validity = rrset_validities[rrset]
                new_expiration = expiration + validity
                new_expirations[new_expiration].add(rrset)

        rrset_expirations = new_expirations


def extract_rrsets_from_zone_diffs(
    file: Path,
) -> Generator[DNSZoneUpdateEvent, None, None]:
    df = polars.scan_parquet(file).collect(engine="streaming")

    add_events: dict[datetime, set[tuple[str, str]]] = defaultdict(set)
    del_events: dict[datetime, set[tuple[str, str]]] = defaultdict(set)

    seen: set[tuple[str, str]] = set()
    pre_existing: set[tuple[str, str]] = set()

    for row in df.iter_rows(named=True):
        dt = row["datetime"]
        rrset = (row["response_name"], row["rrsig_type_covered"])
        change_type = row["change_type"]

        if rrset not in seen:
            seen.add(rrset)
            if change_type == "modified":
                # First appearance is a modification -> record existed before our window.
                pre_existing.add(rrset)

        if change_type in ("added", "modified"):
            add_events[dt].add(rrset)
        if change_type == "removed":
            del_events[dt].add(rrset)

    all_timestamps = sorted(set(add_events.keys()) | set(del_events.keys()))
    for i, ts in enumerate(all_timestamps):
        added = add_events[ts]
        if i == 0:
            # Inject records that were already in the zone at the start of the diff window.
            added = added | pre_existing
        yield DNSZoneUpdateEvent(
            timestamp=ts,
            added=list(added),
            removed=list(del_events[ts]),
        )


def generate_resolver_queries(
    start: datetime,
    end: datetime,
    exp_rate: float,
    seed: int,
    query_type: str | None,
) -> Generator[DNSQueryEvent, None, None]:
    rng = np.random.default_rng(seed)

    cur_time = start
    while cur_time < end:
        # Exponentially distributed inter-arrival times
        inter_arrival = rng.exponential(1 / exp_rate)
        cur_time += timedelta(seconds=inter_arrival)

        yield DNSQueryEvent(
            timestamp=cur_time,
            type="random",
            query_name=None,
            query_type=query_type,
        )
