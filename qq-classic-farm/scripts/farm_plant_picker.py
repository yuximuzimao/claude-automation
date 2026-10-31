"""M2 local picker positioning/verification phase (injectable I/O, no game clicks).

The planner supplies the seed and quantity, never a page/slot. A local
adapter may batch bounded page turns, then independently verify page, icon,
and quantity. No inventory mutation occurs until planting is confirmed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from seed_order import PAGE_SIZE, PickerPosition, compute_picker_position, compute_visible_order


class PickerStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PickerView:
    # Read from a fresh local screenshot. None = page indicator not verified.
    page: int | None
    # Expected-slot local template result; None = not evaluated.
    target_icon_verified: bool | None = None
    # Badge count from the same verified target slot; None = unreadable.
    target_quantity: int | None = None
    # The one-key checkbox exists INSIDE the open picker, not on the bare field.
    # True/False require a separately verified live control; None is unknown.
    one_key_planting: bool | None = None


class PickerAdapter(Protocol):
    def observe(self, expected_slot: int, target_seed: str) -> PickerView: ...
    def turn_pages(self, direction: int, count: int) -> None: ...


def prepare_picker_target(
    adapter: PickerAdapter, *, platform: str, seed: str, needed: int,
    stable_order: Sequence[str], quantities: Mapping[str, int],
) -> dict:
    """Return a verified position; never selects or consumes the seed.

    Normal path uses at most two observations and one bounded local batch.
    The adapter MUST check current window identity/focus/occlusion and local
    time restrictions before any real page-turn events.
    """
    if type(needed) is not int or needed <= 0:
        raise PickerStop("INVALID_PLANT_COUNT", "Target count must be positive")
    position: PickerPosition = compute_picker_position(platform, seed, stable_order, quantities)
    visible = compute_visible_order(stable_order, quantities)
    if quantities.get(seed, 0) < needed:
        raise PickerStop("INSUFFICIENT_INVENTORY", "Local state has insufficient stock")
    max_page = (len(visible) + PAGE_SIZE - 1) // PAGE_SIZE
    def observe() -> PickerView:
        try:
            view = adapter.observe(position.slot, seed)
        except Exception as exc:
            raise PickerStop("PICKER_OBSERVATION_UNAVAILABLE", "Cannot read picker state") from exc
        if not isinstance(view, PickerView):
            raise PickerStop("PICKER_OBSERVATION_UNAVAILABLE", "Invalid picker observation")
        return view

    before = observe()
    if type(before.page) is not int or not 1 <= before.page <= max_page:
        raise PickerStop("PICKER_PAGE_UNKNOWN", "Current picker page is not verified")
    turns = abs(position.page - before.page)
    if turns:
        direction = 1 if position.page > before.page else -1
        try:
            adapter.turn_pages(direction, turns)
        except Exception as exc:
            raise PickerStop("PICKER_NAVIGATION_UNCERTAIN",
                             "Page navigation may be partial; do not retry blindly") from exc
        after = observe()
        if type(after.page) is not int or after.page != position.page:
            raise PickerStop("PICKER_PAGE_DRIFT", "Page indicator differs after bounded navigation")
    else:
        after = before
    if after.target_icon_verified is not True:
        raise PickerStop("STATE_DRIFT", "Expected slot icon not independently verified")
    if type(after.target_quantity) is not int or after.target_quantity < 0:
        raise PickerStop("QUANTITY_UNVERIFIED", "Target quantity badge not verified")
    if after.target_quantity < needed:
        raise PickerStop("INSUFFICIENT_INVENTORY", "Target badge below planned use")
    return {
        "status": "picker_target_verified",
        "platform": platform,
        "seed": seed,
        "position": position.as_dict(),
        "needed": needed,
        "visible_quantity": after.target_quantity,
        "one_key_planting": after.one_key_planting,
        "pages_turned": turns,
        "observations": 1 if turns == 0 else 2,
        "llm_round_trips": 0,
        "selection_sent": False,
        "inventory_mutated": False,
    }
