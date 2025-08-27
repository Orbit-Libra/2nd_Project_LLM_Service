from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List

class BaseTool(ABC):
    name: str
    def __init__(self, cfg: Dict[str, Any]): self.cfg = cfg

    @abstractmethod
    def can_handle(self, query: str, hints: List[str]) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def run(self, query: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    # 관리용
    def admin_sync(self, **kwargs) -> Dict[str, Any]: raise NotImplementedError
    def admin_reset(self) -> Dict[str, Any]: raise NotImplementedError
