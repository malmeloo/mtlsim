from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RRSet:
    label: str
    type: str


def lsb(x: int) -> int:
    """
    Position of the least significant bit of x, where
    bit positions start at 1 and lsb(0) = 0
    """
    if x == 0:
        return 0
    return (x & -x).bit_length()


def msb(x: int) -> int:
    """
    Position of the most significant bit of x
    """
    if x == 0:
        return 0
    return x.bit_length()
