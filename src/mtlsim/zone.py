import logging
from datetime import datetime
from typing import Literal, final, overload

from mtlsim.ladder_strats._base import StrategyDecisionDeleteLadder

from .events import Event, EventLogger
from .ladder_strats import (
    BaseLadderStrategy,
    StrategyDecisionAddLeaves,
    StrategyDecisionCreateLadder,
)
from .mtl import CondensedMTLSignature, FullMTLSignature, MerkleTreeLadder, MTLSignature
from .util import RRSet

logger = logging.getLogger(__name__)


class DNSZoneLadderAddEvent(Event):
    type: Literal["new_ladder"] = "new_ladder"
    sid: str


class DNSZoneLadderDeleteEvent(Event):
    type: Literal["delete_ladder"] = "delete_ladder"
    sid: str


class DNSZoneRRSetAddEvent(Event):
    type: Literal["ladder_add"] = "ladder_add"
    sid: str
    count: int


@final
class DNSZone:
    def __init__(
        self,
        ladder_strat: BaseLadderStrategy,
        logger: EventLogger | None = None,
    ) -> None:
        self._ladder_strat = ladder_strat
        self._logger = logger

        self._ladders: dict[str, MerkleTreeLadder[RRSet]] = {}

    @property
    def ladder_sizes(self) -> dict[str, int]:
        return {sid: ladder.size for sid, ladder in self._ladders.items()}

    def get_random_rrset(
        self, rrset_type: str | None = None, seed: str | None = None
    ) -> tuple[str, str] | None:
        return self._ladder_strat.get_random_rrset(rrset_type, seed)

    def update_rrsets(
        self, rrsets: list[RRSet], timestamp: datetime | None = None
    ) -> None:
        dt = timestamp or datetime.now()

        for action in self._ladder_strat.decide(rrsets, dt):
            match action:
                case StrategyDecisionCreateLadder(sid=sid):
                    if sid in self._ladders:
                        raise RuntimeError(
                            f"Strategy error: Ladder already exists for sid: {sid}"
                        )

                    ladder = MerkleTreeLadder[RRSet](sid)
                    self._ladders[sid] = ladder

                    self._log(DNSZoneLadderAddEvent(timestamp=dt, sid=sid))

                case StrategyDecisionDeleteLadder(sid=sid):
                    if sid not in self._ladders:
                        raise RuntimeError(
                            f"Strategy error: Ladder {sid} not found to delete"
                        )

                    del self._ladders[sid]

                    self._log(DNSZoneLadderDeleteEvent(timestamp=dt, sid=sid))

                case StrategyDecisionAddLeaves(
                    sid=sid,
                    rrsets=rrsets,
                ):
                    self._log(
                        DNSZoneRRSetAddEvent(timestamp=dt, sid=sid, count=len(rrsets))
                    )

                    ladder = self._ladders.get(sid, None)
                    if ladder is None:
                        raise RuntimeError(
                            f"Strategy error: Ladder {sid} not found to add rrsets to (timestamp: {dt})"
                        )

                    leaf_i = ladder.add_leaves(rrsets)
                    self._ladder_strat.update_rrsets(sid, rrsets, leaf_i)

    def delete_rrsets(self, rrsets: list[RRSet]) -> None:
        self._ladder_strat.remove_rrsets(rrsets)

    def get_rrset_location(
        self,
        rrset_type: str,
        rrset_label: str,
    ) -> tuple[str, int] | None:
        return self._ladder_strat.get_rrset_location(rrset_type, rrset_label)

    @overload
    def get_signature(
        self,
        sid: str,
        leaf_index: int,
        timestamp: datetime,
        sig_type: Literal["full"],
    ) -> FullMTLSignature[RRSet] | None: ...

    @overload
    def get_signature(
        self,
        sid: str,
        leaf_index: int,
        timestamp: datetime,
        sig_type: Literal["condensed"],
    ) -> CondensedMTLSignature[RRSet] | None: ...

    def get_signature(
        self,
        sid: str,
        leaf_index: int,
        timestamp: datetime,
        sig_type: Literal["full"] | Literal["condensed"],
    ) -> MTLSignature[RRSet] | None:
        self.update_rrsets(
            [], timestamp
        )  # trigger any pending ladder updates before getting signature

        ladder = self._ladders.get(sid)
        if ladder is None:
            return None

        if sig_type == "full":
            return ladder.get_full_signature(leaf_index)
        elif sig_type == "condensed":
            return ladder.get_condensed_signature(leaf_index)

        raise ValueError(f"Invalid signature type: {sig_type}")  # pyright: ignore[reportUnreachable]

    def _log(self, event: Event):
        if self._logger is not None:
            self._logger.log(event)
