from __future__ import annotations

from abc import ABC, abstractmethod


class IdGenerator(ABC):
    @abstractmethod
    def new_id(self) -> str: ...
