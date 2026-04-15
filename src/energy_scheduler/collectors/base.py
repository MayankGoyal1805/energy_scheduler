from __future__ import annotations

from abc import ABC, abstractmethod

from energy_scheduler.models import CollectorReading


class Collector(ABC):
    name: str

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> CollectorReading:
        raise NotImplementedError
