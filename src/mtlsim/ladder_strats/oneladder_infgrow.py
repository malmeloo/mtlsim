import uuid
from datetime import datetime
from typing import final, override

from ..util import RRSet
from ._base import (
    BaseLadderStrategy,
    StrategyDecisionAddLeaves,
    StrategyDecisionCreateLadder,
)


@final
class OneLadderInfGrowStrategy(BaseLadderStrategy):
    STRATEGY_ID = "single_inf"
    STRATEGY_PARAMS = {}

    _LADDER_SID = str(uuid.uuid4())

    @override
    def decide(self, rrsets: list[RRSet], datetime: datetime):
        if not rrsets:
            return

        if self.is_empty:
            # first record, create ladder
            yield StrategyDecisionCreateLadder(sid=self._LADDER_SID)

        yield StrategyDecisionAddLeaves(
            rrsets=rrsets,
            sid=self._LADDER_SID,
        )
