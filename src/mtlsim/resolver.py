from datetime import datetime
from enum import Enum
from typing import Literal, final

from .events import Event, EventLogger
from .mtl import FullMTLSignature, VerificationResult
from .util import RRSet
from .zone import DNSZone


class DNSQueryResponse(Enum):
    OK_CONDENSED = "ok_condensed"
    OK_FULL = "ok_full"
    ERR_NOT_FOUND = "not_found"
    ERR_VERIFY_FAIL = "verify_fail"


class DNSResolverQueryEvent(Event):
    type: str = "query"
    sig_type: Literal["condensed", "full"]


class DNSResolverQueryErrorEvent(Event):
    type: str = "query_error"
    cause: Literal["not_found", "verify_fail"]


@final
class DNSResolver:
    def __init__(self, zone: DNSZone, logger: EventLogger | None = None) -> None:
        self._zone = zone
        self._logger = logger

        # ladder sid -> full signature for that ladder
        self._full_sig_cache: dict[str, FullMTLSignature[RRSet]] = {}

    def _log(self, event: Event):
        if self._logger is not None:
            self._logger.log(event)

    def query(
        self,
        rrset_type: str,
        rrset_label: str,
        timestamp: datetime | None = None,
    ) -> DNSQueryResponse:
        """Wrapper for logging."""
        dt = timestamp or datetime.now()
        resp = self._query(rrset_type, rrset_label, dt)

        if resp == DNSQueryResponse.ERR_NOT_FOUND:
            self._log(DNSResolverQueryErrorEvent(timestamp=dt, cause="not_found"))
        elif resp == DNSQueryResponse.ERR_VERIFY_FAIL:
            self._log(DNSResolverQueryErrorEvent(timestamp=dt, cause="verify_fail"))
        elif resp == DNSQueryResponse.OK_CONDENSED:
            self._log(DNSResolverQueryEvent(timestamp=dt, sig_type="condensed"))
        elif resp == DNSQueryResponse.OK_FULL:
            self._log(DNSResolverQueryEvent(timestamp=dt, sig_type="full"))

        return resp

    def query_random(
        self,
        timestamp: datetime | None = None,
        query_type: str | None = None,
        seed: str | None = None,
    ) -> DNSQueryResponse:
        """Query a random rrset of the given type (or any type if query_type is None)."""
        rrset = self._zone.get_random_rrset(query_type, seed)
        if rrset is None:
            return DNSQueryResponse.ERR_NOT_FOUND

        rrset_type, rrset_label = rrset
        return self.query(rrset_type, rrset_label, timestamp)

    def _query(
        self, rrset_type: str, rrset_label: str, timestamp: datetime
    ) -> DNSQueryResponse:
        """Query an rrset in the zone, returning the appropriate response."""
        loc = self._zone.get_rrset_location(rrset_type, rrset_label)
        if loc is None:
            return DNSQueryResponse.ERR_NOT_FOUND

        sid, leaf_index = loc

        condensed_sig = self._zone.get_signature(
            sid, leaf_index, timestamp, "condensed"
        )
        full_sig = self._full_sig_cache.get(sid, None)

        if condensed_sig is None:
            return DNSQueryResponse.ERR_NOT_FOUND

        if (
            full_sig is None
            or not condensed_sig.verify(full_sig) == VerificationResult.VALID
        ):
            # cache miss or full sig is outdated, fetch new full sig
            full_sig = self._zone.get_signature(sid, leaf_index, timestamp, "full")
            if full_sig is None:
                return DNSQueryResponse.ERR_NOT_FOUND

            self._full_sig_cache[sid] = full_sig

            return (
                DNSQueryResponse.OK_FULL
                if full_sig.verify() == VerificationResult.VALID
                else DNSQueryResponse.ERR_VERIFY_FAIL
            )

        return DNSQueryResponse.OK_CONDENSED
