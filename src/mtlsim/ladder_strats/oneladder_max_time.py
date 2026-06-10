import uuid
from datetime import datetime, timedelta
from typing import final, override

from ..util import RRSet
from ._base import (
    BaseLadderStrategy,
    StrategyDecisionAddLeaves,
    StrategyDecisionCreateLadder,
)


@final
class OneLadderMaxTimeStrategy(BaseLadderStrategy):
    STRATEGY_ID = "single_maxtime"
    STRATEGY_PARAMS = {
        "endurance_seconds": int,
    }

    def __init__(self, endurance_seconds: int):
        super().__init__()

        self._endurance_seconds = timedelta(seconds=endurance_seconds)

        self._last_create_time: datetime | None = None
        self._cur_ladder_sid: str = str(uuid.uuid4())

    @override
    def decide(self, rrsets: list[RRSet], datetime: datetime):
        cur_active = []
        if (
            self._last_create_time is None
            or (datetime - self._last_create_time) >= self._endurance_seconds
        ):
            self._cur_ladder_sid = str(uuid.uuid4())
            self._last_create_time = datetime

            # create new ladder and migrate existing rrsets to it
            cur_active = self.active_rrsets
            yield StrategyDecisionCreateLadder(sid=self._cur_ladder_sid)
            if cur_active:
                yield StrategyDecisionAddLeaves(
                    sid=self._cur_ladder_sid, rrsets=cur_active
                )

        # only add rrsets that were not just migrated to the new ladder
        upd_rrsets = list(set(rrsets) - set(cur_active))
        if upd_rrsets:
            yield StrategyDecisionAddLeaves(
                sid=self._cur_ladder_sid,
                rrsets=upd_rrsets,
            )
