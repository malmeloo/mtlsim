from pathlib import Path
from typing import Literal, final

from ._base import BaseEventIngester, BaseEventModel


class DNSQueryEvent(BaseEventModel):
    """
    Not the ideal way to communicate this, but:
    - given: the event contains the query name and type
    - random: the event contains a record type, and the query name is randomly generated from the zone
    - random_seeded: same as random, but the random generator is seeded for reproducibility
    """

    type: Literal["given", "random", "random_seeded"] = "given"
    query_name: str | None
    query_type: str | None
    seed: str | None


class DNSQueryEventRandom(BaseEventModel):
    record_type: str


@final
class DNSQueryIngester(BaseEventIngester[DNSQueryEvent]):
    """
    Ingester for DNS query events. Events follow a custom JSON format.
    """

    def __init__(self, src: Path) -> None:
        super().__init__(src, DNSQueryEvent)
