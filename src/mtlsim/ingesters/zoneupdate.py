from pathlib import Path
from typing import final

from ..util import RRSet
from ._base import BaseEventIngester, BaseEventModel


class DNSZoneUpdateEvent(BaseEventModel):
    removed: list[tuple[str, str]]
    added: list[tuple[str, str]]

    def get_removed_rrsets(self) -> set[RRSet]:
        return set(RRSet(label, type) for label, type in self.removed)

    def get_added_rrsets(self) -> set[RRSet]:
        return set(RRSet(label, type) for label, type in self.added)


@final
class DNSZoneUpdateIngester(BaseEventIngester[DNSZoneUpdateEvent]):
    """
    Ingester for DNS zone update events. Events follow a custom JSON format.
    """

    def __init__(self, src: Path) -> None:
        super().__init__(src, DNSZoneUpdateEvent)
