from __future__ import annotations

from dataclasses import dataclass

from .model import BoardState


@dataclass(slots=True)
class GameTimeline:
    """In-memory snapshots used for safe backward/forward position review."""

    states: list[BoardState]
    index: int = 0

    @classmethod
    def from_state(cls, state: BoardState) -> "GameTimeline":
        return cls([state.clone()], 0)

    @property
    def latest_index(self) -> int:
        return len(self.states) - 1

    @property
    def can_back(self) -> bool:
        return self.index > 0

    @property
    def can_forward(self) -> bool:
        return self.index < self.latest_index

    @property
    def is_reviewing(self) -> bool:
        return self.index < self.latest_index

    def current(self) -> BoardState:
        return self.states[self.index].clone()

    def latest(self) -> BoardState:
        return self.states[-1].clone()

    def reset(self, state: BoardState) -> None:
        self.states = [state.clone()]
        self.index = 0

    def append(self, state: BoardState) -> None:
        if self.can_forward:
            self.states = self.states[: self.index + 1]
        self.states.append(state.clone())
        self.index = self.latest_index

    def back(self) -> BoardState:
        if self.can_back:
            self.index -= 1
        return self.current()

    def forward(self) -> BoardState:
        if self.can_forward:
            self.index += 1
        return self.current()

    def go_to(self, index: int) -> BoardState:
        if not 0 <= index <= self.latest_index:
            raise IndexError("Timeline position is outside the available history")
        self.index = index
        return self.current()
