from ._base import ingest_multiple
from .dnsquery import DNSQueryEvent, DNSQueryIngester
from .zoneupdate import DNSZoneUpdateEvent, DNSZoneUpdateIngester

__all__ = [
    "ingest_multiple",
    "DNSQueryIngester",
    "DNSQueryEvent",
    "DNSZoneUpdateIngester",
    "DNSZoneUpdateEvent",
]
