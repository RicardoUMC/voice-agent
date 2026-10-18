from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DaemonConfig:
    """Explicit local-only boundaries for the daemon's control and state files."""

    socket_path: Path
    state_path: Path
    socket_mode: int = 0o600

    def __post_init__(self) -> None:
        socket_path = Path(self.socket_path)
        state_path = Path(self.state_path)
        if not socket_path.is_absolute() or not state_path.is_absolute():
            raise ValueError("socket_path and state_path must be absolute local paths")
        if not 0 <= self.socket_mode <= 0o777:
            raise ValueError("socket_mode must be a valid Unix permission mode")
        object.__setattr__(self, "socket_path", socket_path)
        object.__setattr__(self, "state_path", state_path)
