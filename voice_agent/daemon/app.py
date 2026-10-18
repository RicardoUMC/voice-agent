from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from voice_agent.adapters.audio import SoxAudioInput, SoxAudioOutput
from voice_agent.adapters.config import AudioConfig, DeepgramConfig
from voice_agent.adapters.deepgram import DeepgramSTT, DeepgramWebSocketTransport
from voice_agent.adapters.kitten_tts import KittenTTS
from voice_agent.conversation.pi_rpc import PiRpcConfig, PiRpcConversationBackend
from voice_agent.voice.pipeline import LifecycleEvent, VoiceTurnCoordinator

from .config import DaemonConfig
from .core import DaemonCore
from .runtime import PiSessionCoordinator, TextConversationAdapter
from .server import JsonLineUnixServer
from .sessions import JsonSessionRegistry


@dataclass(frozen=True)
class VoiceDaemonSettings:
    socket_path: Path
    state_path: Path
    pi_session_dir: Path | None = None
    pi_command: tuple[str, ...] = ("pi", "--mode", "rpc")
    pi_tools: tuple[str, ...] = ("read", "grep", "find")
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
        audio_config = AudioConfig.from_environment()
        voice = VoiceTurnCoordinator(
            SoxAudioInput(audio_config),
            DeepgramSTT(DeepgramConfig.from_environment(), streaming_transport=DeepgramWebSocketTransport()),
            TextConversationAdapter(coordinator),
            KittenTTS(),
            SoxAudioOutput(audio_config),
            on_event=self._log_event,
        )
        self._voice = voice
        self._server = JsonLineUnixServer(
            config.socket_path,
            DaemonCore(registry, coordinator, voice_coordinator=voice),
            config.socket_mode,
        )

    def _make_backend(self, session_id: str) -> PiRpcConversationBackend:
        return PiRpcConversationBackend(
            PiRpcConfig(
                command=self.settings.pi_command,
                session_id=session_id,
                session_dir=str(self.settings.pi_session_dir) if self.settings.pi_session_dir else None,
                tools=self.settings.pi_tools,
            )
        )

    @staticmethod
    def _log_event(event: LifecycleEvent) -> None:
        import logging

        logging.getLogger("voice_agent.voice").info(
            "voice lifecycle event=%s session=%s stage=%s",
            event.name,
            event.session_id,
            event.stage,
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
    raw_tools = env.get("VOICE_AGENT_PI_TOOLS", "read,grep,find")
    tools = tuple(tool.strip() for tool in raw_tools.split(",") if tool.strip())
    return VoiceDaemonSettings(
        socket_path=socket_path,
        state_path=state_path,
        pi_session_dir=Path(pi_session_dir).expanduser() if pi_session_dir else None,
        pi_command=command,
        pi_tools=tools,
    )
