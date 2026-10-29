"""Pure picker ordering logic. No UI, strategy or I/O side effects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

PAGE_SIZE = 5
PLATFORMS = ("qq", "wechat")


class PickerStateError(ValueError):
    """A state invariant failed; caller must stop, not guess a slot."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PickerPosition:
    page: int
    slot: int
    visible_index: int

    def as_dict(self) -> dict[str, int]:
        return {"page": self.page, "slot": self.slot, "visible_index": self.visible_index}


def _quantity(seed: str, quantities: Mapping[str, int]) -> int:
    value = quantities.get(seed, 0)
    if type(value) is not int or value < 0:
        raise PickerStateError("INVALID_INVENTORY", f"Invalid quantity for {seed}: {value!r}")
    return value


def compute_visible_order(
    stable_order: Sequence[str], quantities: Mapping[str, int]
) -> list[str]:
    """Filter zero stock; never modify stable_order or quantities."""
    if len(stable_order) != len(set(stable_order)) or any(
        not isinstance(seed, str) or not seed.strip() for seed in stable_order
    ):
        raise PickerStateError("ORDER_CONFLICT", "stable_order contains duplicates/invalid seeds")
    if any(type(v) is not int or v < 0 for v in quantities.values()):
        raise PickerStateError("INVALID_INVENTORY", "quantities must be nonnegative integers")
    unexpected = [seed for seed, qty in quantities.items() if qty > 0 and seed not in stable_order]
    if unexpected:
        raise PickerStateError(
            "ORDER_SYNC_REQUIRED",
            f"Positive-stock seeds missing from calibrated stable_order: {unexpected}",
        )
    return [seed for seed in stable_order if _quantity(seed, quantities) > 0]


def compute_picker_position(
    platform: str,
    seed: str,
    stable_order: Sequence[str],
    quantities: Mapping[str, int],
    page_size: int = PAGE_SIZE,
) -> PickerPosition:
    if platform not in PLATFORMS:
        raise PickerStateError("UNKNOWN_PLATFORM", f"Unknown platform: {platform}")
    if type(page_size) is not int or page_size <= 0:
        raise PickerStateError("INVALID_PAGE_SIZE", "page_size must be positive")
    visible = compute_visible_order(stable_order, quantities)
    if seed not in visible:
        raise PickerStateError("TARGET_SEED_NOT_FOUND", f"{platform}: {seed} is not visible")
    index = visible.index(seed)
    return PickerPosition(index // page_size + 1, index % page_size + 1, index)


def consume_confirmed(
    stable_order: Sequence[str], quantities: Mapping[str, int], seed: str, used: int
) -> dict[str, int]:
    """Return a new quantity map after *confirmed* planting; caller owns verification."""
    if type(used) is not int or used <= 0:
        raise PickerStateError("INVALID_CONSUMPTION", "used must be positive integer")
    compute_visible_order(stable_order, quantities)
    available = _quantity(seed, quantities)
    if seed not in stable_order or available < used:
        raise PickerStateError(
            "INSUFFICIENT_INVENTORY",
            f"{seed}: need {used}, have {available}",
        )
    updated = dict(quantities)
    updated[seed] = available - used
    return updated
