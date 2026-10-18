from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from voice_agent.conversation.pi_rpc import PiRpcConfig, PiRpcConversationBackend

from .config import DaemonConfig
from .core import DaemonCore
from .runtime import PiSessionCoordinator
from .server import JsonLineUnixServer
from .sessions import JsonSessionRegistry


@dataclass(frozen=True)
class VoiceDaemonSettings:
    socket_path: Path
    state_path: Path
    pi_session_dir: Path | None = None
    pi_command: tuple[str, ...] = ("pi", "--mode", "rpc")
    socket_mode: int = 0o600

    def daemon_config(self) -> DaemonConfig:
        return DaemonConfig(self.socket_path, self.state_path, self.socket_mode)


class VoiceDaemon:
    def __init__(self, settings: VoiceDaemonSettings):
        self.settings = settings
        config = settings.daemon_config()
        registry = JsonSessionRegistry(config.state_path)
        coordinator = PiSessionCoordinator(self._make_backend)
        self._coordinator = coordinator
        self._server = JsonLineUnixServer(config.socket_path, DaemonCore(registry, coordinator), config.socket_mode)

    def _make_backend(self, session_id: str) -> PiRpcConversationBackend:
        return PiRpcConversationBackend(
            PiRpcConfig(
                command=self.settings.pi_command,
                session_id=session_id,
                session_dir=str(self.settings.pi_session_dir) if self.settings.pi_session_dir else None,
            )
        )

    @property
    def ready(self):
        return self._server.ready

    def serve_forever(self) -> None:
        try:
            self._server.serve_forever()
        finally:
            self._coordinator.close()

    def close(self) -> None:
        self._server.close()
        self._coordinator.close()


def settings_from_environment(environ: dict[str, str] | None = None) -> VoiceDaemonSettings:
    import os

    env = os.environ if environ is None else environ
    root = Path(env.get("VOICE_AGENT_HOME", Path.home() / ".local" / "state" / "voice-agent")).expanduser()
    socket_path = Path(env.get("VOICE_AGENT_SOCKET", root / "voice-agent.sock")).expanduser()
    state_path = Path(env.get("VOICE_AGENT_STATE", root / "sessions.json")).expanduser()
    pi_session_dir = env.get("VOICE_AGENT_PI_SESSION_DIR")
    command = tuple(shlex.split(env.get("VOICE_AGENT_PI_COMMAND", "pi --mode rpc")))
    return VoiceDaemonSettings(
        socket_path=socket_path,
        state_path=state_path,
        pi_session_dir=Path(pi_session_dir).expanduser() if pi_session_dir else None,
        pi_command=command,
    )
