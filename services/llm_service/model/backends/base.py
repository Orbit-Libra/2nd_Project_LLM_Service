# dase.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IBackend(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def warmup(self) -> None: ...

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], gen_params: Dict[str, Any]) -> str: ...

    @abstractmethod
    def close(self) -> None: ...
