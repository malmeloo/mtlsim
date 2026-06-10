import uuid
from dataclasses import dataclass
from enum import Enum
from typing import override

from .util import lsb


class VerificationResult(Enum):
    VALID = "valid"
    INVALID_INCORRECT_SERIES = "invalid_incorrect_series"
    INVALID_NOT_COVERED = "invalid_not_covered"


type MTLSignature[LeafT] = FullMTLSignature[LeafT] | CondensedMTLSignature[LeafT]


@dataclass
class FullMTLSignature[LeafT]:
    series_id: str
    rungs: list[tuple[int, int]]

    def verify(self) -> VerificationResult:
        """
        Because we don't implement actual cryptographic signatures,
        we need to assume that the signature is always valid.
        Either way it doesn't impact our metrics, because the interesting part
        is whether condensed signatures can be validated using an old full signature.
        """
        return VerificationResult.VALID


@dataclass
class CondensedMTLSignature[LeafT]:
    series_id: str
    message_idx: int
    message: LeafT

    def verify(self, full_sig: FullMTLSignature[LeafT]) -> VerificationResult:
        if self.series_id != full_sig.series_id:
            return VerificationResult.INVALID_INCORRECT_SERIES

        # Note that in the 'real world', the full sig would have already been
        # validated upon receipt, so we don't re-validate it here.

        # Technically speaking, if everything is implemented correctly,
        # the signature is valid as long as message_idx is covered by one
        # of the rungs in the full signature (and the series id matches).
        # However, the official MTL spec is a bit more thorough in its validation
        # (for good reason), so for the sake of staying true to the spec, we will
        # implement the same validation logic here.
        # Source: https://datatracker.ietf.org/doc/draft-harvey-cfrg-mtl-mode/07/ (section 6.7)

        for rung in full_sig.rungs:
            # 1. L <= leaf_index <= R, ensuring the leaf index is covered by the rung
            if not (rung[0] <= self.message_idx <= rung[1]):
                continue

            # 2. (L = 0 or degree <= lsb(L)-1) and R-L+1 = 2^degree, where degree =
            # lsb(R-L+1)-1, ensuring the rung is indeed an apex of a perfect
            # binary tree in the binary rung strategy
            degree = lsb(rung[1] - rung[0] + 1) - 1
            if not (rung[0] == 0 or degree <= lsb(rung[0]) - 1):
                continue
            if not (rung[1] - rung[0] + 1 == 2**degree):
                continue

            # 3. lsb(R-L+1)-1 is less than or equal to the number of sibling hash
            # values in the authentication path, ensuring the authentication
            # path can reach the rung
            # (author note: we don't store authentication paths, so we will assume this is always satisfied)
            pass

            # If we reach here, the signature is valid
            return VerificationResult.VALID

        return VerificationResult.INVALID_NOT_COVERED


class MerkleTree[LeafT]:
    """
    Note: this does not implement a real Merkle tree, but rather one that is
    'good enough' for our purposes. No actual hashing is done.

    Leaf nodes are stored as a simple list, no actual tree structure is built.
    """

    def __init__(
        self,
        idx_start: int = 0,
        initial_leaves: list[LeafT] | None = None,
    ) -> None:
        self._idx_start: int = idx_start
        self._leaves: list[LeafT] = (initial_leaves or []).copy()

        assert len(self._leaves) == 2 ** (len(self._leaves).bit_length() - 1), (
            "Merkle tree size must be power of 2"
        )

    @property
    def rung(self) -> tuple[int, int]:
        return (self._idx_start, self._idx_start + len(self._leaves) - 1)

    @property
    def size(self) -> int:
        return len(self._leaves)

    def add_leaves(self, leaves: list[LeafT]) -> None:
        new_size = len(self._leaves) + len(leaves)
        assert new_size == 2 ** new_size.bit_length(), (
            "Merkle tree size must be power of 2"
        )

        self._leaves.extend(leaves)

    def get_leaf(self, index: int) -> LeafT:
        assert self._idx_start <= index < self._idx_start + len(self._leaves), (
            "Index out of bounds"
        )

        return self._leaves[index - self._idx_start]

    def get_leaves(self) -> list[LeafT]:
        return self._leaves.copy()

    def __add__(self, other: "MerkleTree[LeafT]") -> "MerkleTree[LeafT]":
        assert self.rung[1] + 1 == other.rung[0], "Merkle trees must be adjacent"
        assert self.size == other.size, "Merkle trees must be of the same size"

        new_leaves = self.get_leaves() + other.get_leaves()
        return MerkleTree(
            idx_start=self.rung[0],
            initial_leaves=new_leaves,
        )


class MerkleTreeLadder[LeafT]:
    """
    A ladder of Merkle trees. The ladder is append-only.

    The trees are sorted by their rung start value. Due to the properties of Merkle tree ladders,
    they are also sorted by their size, descending.
    """

    def __init__(self, sid: str | None = None) -> None:
        self._sid: str = sid or str(uuid.uuid4())

        self._trees: list[MerkleTree[LeafT]] = []

    @property
    def series_id(self) -> str:
        return self._sid

    @property
    def rungs(self) -> list[tuple[int, int]]:
        return [tree.rung for tree in self._trees]

    @property
    def size(self) -> int:
        return sum(tree.size for tree in self._trees)

    def get_leaf(self, index: int) -> LeafT:
        assert 0 <= index < self.size, "Index out of bounds"

        for tree in self._trees:
            if tree.rung[0] <= index <= tree.rung[1]:
                return tree.get_leaf(index)

        raise RuntimeError("Crazy cosmic bitflip if this ever happens")

    def add_leaf(self, leaf: LeafT) -> int:
        return self.add_leaves([leaf])[0]

    def add_leaves(self, leaves: list[LeafT]) -> list[int]:
        """
        Adding a leaf to the ladder will always result in a new tree being created.
        When the smallest tree reaches the size of the second smallest tree, they are merged together, and so on.

        To do this efficiently, we create trees as large as possible from the new leaves,
        and then keep merging them with the existing trees in the ladder.
        To maintain the invariant that the trees are sorted by size, the maximum size of a new tree
        is the size of the smallest existing tree in the ladder.

        Returns the indices of the new leaves in the ladder.
        """
        new_leaves = leaves.copy()
        while new_leaves:
            max_new_tree_size = self._trees[-1].size if self._trees else len(new_leaves)
            new_tree_size: int = 2 ** (len(new_leaves).bit_length() - 1)  # pyright: ignore[reportAny]
            new_tree_size = min(new_tree_size, max_new_tree_size)

            new_tree = MerkleTree(
                idx_start=self._trees[-1].rung[1] + 1 if self._trees else 0,
                initial_leaves=new_leaves[:new_tree_size],
            )
            new_leaves = new_leaves[new_tree_size:]

            while self._trees and self._trees[-1].size == new_tree.size:
                new_tree = self._trees.pop(-1) + new_tree

            self._trees.append(new_tree)

        return list(range(self.size - len(leaves), self.size))

    def get_full_signature(self, index: int) -> FullMTLSignature[LeafT]:
        assert self._trees, "Cannot get signature of an empty ladder"
        assert 0 <= index < self.size, "Index out of bounds"

        return FullMTLSignature(
            series_id=self.series_id,
            rungs=self.rungs,
        )

    def get_condensed_signature(self, index: int) -> CondensedMTLSignature[LeafT]:
        assert self._trees, "Cannot get signature of an empty ladder"
        assert 0 <= index < self.size, "Index out of bounds"

        return CondensedMTLSignature(
            series_id=self.series_id,
            message_idx=index,
            message=self.get_leaf(index),
        )

    @override
    def __hash__(self) -> int:
        return hash(self._sid)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MerkleTreeLadder):
            return NotImplemented
        return self._sid == other._sid
