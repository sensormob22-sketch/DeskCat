from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""
    timeout_seconds: float = 30.0
    enabled: bool = False


class DialogueService(Protocol):
    """Implement in a worker thread; never block the Qt event loop."""
    def reply(self, message: str) -> str: ...
