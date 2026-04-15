from __future__ import annotations

from abc import ABC, abstractmethod


class SchedulerAdapter(ABC):
    name: str

    @abstractmethod
    def prepare(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        raise NotImplementedError
