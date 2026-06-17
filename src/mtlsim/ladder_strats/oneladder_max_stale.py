import uuid
from datetime import datetime, timedelta
from typing import final, override

from ..util import RRSet
from ._base import (
    BaseLadderStrategy,
    StrategyDecisionAddLeaves,
    StrategyDecisionCreateLadder,
    StrategyDecisionDeleteLadder,
)


@final
class OneLadderMaxStaleStrategy(BaseLadderStrategy):
    STRATEGY_ID = "single_maxstale"
    STRATEGY_PARAMS = {
        "max_stale_count": int,
    }

    def __init__(self, max_stale_count: int):
        super().__init__()

        self._max_stale_count = max_stale_count

        self._seen_rrsets: set[tuple[str, str]] = set()
        self._cur_stale_count = 0
        self._cur_ladder_sid: str | None = None

    @override
    def decide(self, rrsets: list[RRSet], datetime: datetime):
        for rrset in rrsets:
            if (rrset.type, rrset.label) in self._seen_rrsets:
                self._cur_stale_count += 1
            self._seen_rrsets.add((rrset.type, rrset.label))

        cur_active: list[RRSet] = []
        if (
            self._cur_ladder_sid is None
            or self._cur_stale_count >= self._max_stale_count
        ):
            if self._cur_ladder_sid is not None:
                yield StrategyDecisionDeleteLadder(sid=self._cur_ladder_sid)

            self._cur_ladder_sid = str(uuid.uuid4())

            # create new ladder and migrate existing rrsets to it
            cur_active = self.active_rrsets
            yield StrategyDecisionCreateLadder(sid=self._cur_ladder_sid)
            if cur_active:
                yield StrategyDecisionAddLeaves(
                    sid=self._cur_ladder_sid, rrsets=cur_active
                )

            # reset stale count
            self._seen_rrsets.clear()
            self._cur_stale_count = 0

        # only add rrsets that were not just migrated to the new ladder
        upd_rrsets = list(set(rrsets) - set(cur_active))
        if upd_rrsets:
            yield StrategyDecisionAddLeaves(
                sid=self._cur_ladder_sid,
                rrsets=upd_rrsets,
            )
