import random
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal

from ..util import RRSet


@dataclass(frozen=True, slots=True)
class StrategyDecisionCreateLadder:
    sid: str
    type: Literal["create_ladder"] = "create_ladder"


@dataclass(frozen=True, slots=True)
class StrategyDecisionAddLeaves:
    sid: str
    rrsets: list[RRSet]
    type: Literal["add_leaves"] = "add_leaves"


type StrategyDecision = StrategyDecisionCreateLadder | StrategyDecisionAddLeaves


class BaseLadderStrategy(ABC):
    STRATEGY_ID: str
    STRATEGY_PARAMS: dict[str, Callable[[str], object]]

    def __init__(self) -> None:
        # rrset type and label to ladder ID and leaf index
        self._rrset_to_leaf: dict[tuple[str, str], tuple[str, int]] = {}
        self._ladder_sizes: dict[str, int] = defaultdict(int)

    @property
    def is_empty(self) -> bool:
        """
        Check if the strategy has no active rrsets.
        """
        return not any(self._rrset_to_leaf.values())

    @property
    def active_rrsets(self) -> list[RRSet]:
        """
        Get the set of active rrsets in the strategy.
        """
        rrsets: list[RRSet] = []
        for rrset_type, rrset_label in self._rrset_to_leaf.keys():
            rrsets.append(RRSet(type=rrset_type, label=rrset_label))

        return rrsets

    def get_ladder_size(self, sid: str) -> int:
        """
        Get the number of leaves in a ladder.
        """
        return self._ladder_sizes[sid]

    def get_random_rrset(self, rrset_type: str | None = None) -> tuple[str, str] | None:
        """
        Get a random active rrset of the given type, as a (type, label) tuple. Returns None if there are no active rrsets of the given type.
        """
        if self.is_empty:
            return None

        if rrset_type is None:
            # perf optimization
            return random.choice(list(self._rrset_to_leaf.keys()))

        return random.choice(
            [rrset for rrset in self._rrset_to_leaf.keys() if rrset_type == rrset[0]]
        )

    def get_rrset_location(
        self, rrset_type: str, rrset_label: str
    ) -> tuple[str, int] | None:
        """
        Get ladder ID and leaf index for a given rrset, if it exists.
        """
        return self._rrset_to_leaf.get((rrset_type, rrset_label), None)

    @abstractmethod
    def decide(
        self, rrsets: list[RRSet], datetime: datetime
    ) -> Generator[StrategyDecision, None, None]:
        """
        Decide how to update the ladder(s) given rrsets. The rrsets may be new or updates to existing rrsets.
        """
        raise NotImplementedError

    def update_rrsets(
        self, sid: str, rrsets: list[RRSet], leaf_indices: list[int]
    ) -> None:
        """
        Update rrsets in the strategy's internal state. This should be called after rrsets have been added to a ladder.
        """
        for rrset, leaf_index in zip(rrsets, leaf_indices):
            self._rrset_to_leaf[(rrset.type, rrset.label)] = (sid, leaf_index)
            self._ladder_sizes[sid] += 1

    def remove_rrsets(self, rrsets: list[RRSet]) -> None:
        """
        Remove rrsets from the strategy's internal state. This should be called when rrsets are deleted from the zone.
        """
        for rrset in rrsets:
            _ = self._rrset_to_leaf.pop((rrset.type, rrset.label), None)
