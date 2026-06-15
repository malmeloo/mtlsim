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

        # flat list for O(1) uniform random sampling across all rrsets
        self._all_rrsets: list[tuple[str, str]] = []
        self._all_rrsets_index: dict[tuple[str, str], int] = {}

        # per-type list for O(1) uniform random sampling by type
        self._rrsets_by_type: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._type_list_index: dict[tuple[str, str], int] = {}

        # mapping from seed to rrset and vice versa for seeded random selection
        self._seed_to_rrset: dict[str, tuple[str, str]] = {}
        self._rrset_to_seed: dict[tuple[str, str], str] = {}

    @property
    def is_empty(self) -> bool:
        """
        Check if the strategy has no active rrsets.
        """
        return not self._all_rrsets

    @property
    def active_rrsets(self) -> list[RRSet]:
        """
        Get the set of active rrsets in the strategy.
        """
        return [RRSet(type=t, label=l) for t, l in self._all_rrsets]

    def get_ladder_size(self, sid: str) -> int:
        """
        Get the number of leaves in a ladder.
        """
        return self._ladder_sizes[sid]

    def get_random_rrset(
        self, rrset_type: str | None = None, seed: str | None = None
    ) -> tuple[str, str] | None:
        """
        Get a random active rrset of the given type, as a (type, label) tuple. Returns None if there are no active rrsets of the given type.
        """
        # get from cache if seed is provided
        if seed is not None and (rrset := self._seed_to_rrset.get(seed, None)):
            if rrset_type is None or rrset[0] == rrset_type:
                return rrset
            # else: seed is associated with an rrset of the wrong type, ignore it

        if seed is not None:
            random.seed(seed)

        bucket = (
            self._all_rrsets
            if rrset_type is None
            else self._rrsets_by_type.get(rrset_type)
        )
        rrset = random.choice(bucket) if bucket else None
        if rrset is None:
            return None

        if seed is not None:
            # cache the seed for future lookups
            self._seed_to_rrset[seed] = rrset
            self._rrset_to_seed[rrset] = seed

        return rrset

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
            key = (rrset.type, rrset.label)
            self._rrset_to_leaf[key] = (sid, leaf_index)

            if key not in self._all_rrsets_index:
                # add to flat index
                self._all_rrsets_index[key] = len(self._all_rrsets)
                self._all_rrsets.append(key)

                # add to per-type index
                bucket = self._rrsets_by_type[rrset.type]
                self._type_list_index[key] = len(bucket)
                bucket.append(key)

        self._ladder_sizes[sid] += 1

    def remove_rrsets(self, rrsets: list[RRSet]) -> None:
        """
        Remove rrsets from the strategy's internal state. This should be called when rrsets
        are deleted from the zone.
        """
        for rrset in rrsets:
            key = (rrset.type, rrset.label)
            if self._rrset_to_leaf.pop(key, None) is None:
                continue

            # swap-and-pop from flat list
            idx = self._all_rrsets_index.pop(key)
            last = self._all_rrsets[-1]
            _ = self._all_rrsets.pop()  # pop first
            if idx < len(
                self._all_rrsets
            ):  # only update if key wasn't the last element
                self._all_rrsets[idx] = last
                self._all_rrsets_index[last] = idx

            # swap-and-pop from per-type list
            bucket = self._rrsets_by_type[rrset.type]
            idx = self._type_list_index.pop(key)
            last = bucket[-1]
            _ = bucket.pop()  # pop first
            if idx < len(bucket):  # only update if key wasn't the last element
                bucket[idx] = last
                self._type_list_index[last] = idx

            # remove from seed cache if it exists
            seed = self._rrset_to_seed.pop(key, None)
            if seed is not None:
                _ = self._seed_to_rrset.pop(seed, None)

            if not bucket:
                del self._rrsets_by_type[rrset.type]
