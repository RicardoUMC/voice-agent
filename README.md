# voice-agent

A persistent local voice daemon that connects microphone/STT input to a Pi RPC conversation and TTS playback without depending on the Pi TUI.

## Current status

The repository contains the first implementation slices:

- persistent JSON session registry;
- session-aware cancellation and interruption seams;
- local JSONL Unix-socket service;
- Pi 1.3 RPC conversation adapter;
- SoX/PipeWire-compatible audio boundaries;
- Deepgram Nova-3 STT configuration for `es-419`;
- lazy KittenTTS 2 `emb4` adapter.

The end-to-end process supervisor and live provider validation are still in progress.

## Quick path

Run the daemon with:

```bash
python -m voice_agent \
  --socket "$XDG_RUNTIME_DIR/voice-agent.sock" \
  --state "$HOME/.local/state/voice-agent/sessions.json" \
  --pi-session-dir "$HOME/.local/state/voice-agent/pi-sessions"
```

The default local endpoint is a Unix socket. The daemon does not open a TCP listener.

## Local protocol

Each request and response is one JSON object terminated by LF.

```json
{"op":"sessions"}
{"op":"turn","session_id":"voice-main","text":"Hola"}
{"op":"interrupt","session_id":"voice-main"}
{"op":"stop_recording","session_id":"voice-main"}
```

`stop_recording` ends the microphone capture and continues the turn through STT, Pi RPC, TTS, and playback. `interrupt` cancels the entire turn. The default capture path also uses PCM silence endpointing after speech; tune or disable it with the audio environment variables below.

The protocol is session-addressed from the beginning, but the MVP exposes only one local client. A future authenticated mobile client can use the same logical protocol without changing the conversation model.

## Configuration

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VOICE_AGENT_HOME` | `~/.local/state/voice-agent` | Default daemon state root |
| `VOICE_AGENT_SOCKET` | `<home>/voice-agent.sock` | Unix socket path |
| `VOICE_AGENT_STATE` | `<home>/sessions.json` | Daemon session registry |
| `VOICE_AGENT_PI_SESSION_DIR` | Pi default | Persistent Pi session directory |
| `VOICE_AGENT_PI_COMMAND` | `pi --mode rpc` | Pi executable and startup arguments |
| `DEEPGRAM_API_KEY` | unset | Deepgram credential |
| `DEEPGRAM_MODEL` | `nova-3` | STT model |
| `DEEPGRAM_LANGUAGE` | `es-419` | STT language |
| `VOICE_AGENT_VAD_ENABLED` | `1` | Enable PCM silence endpointing |
| `VOICE_AGENT_SILENCE_THRESHOLD` | `500` | Maximum absolute PCM sample treated as silence |
| `VOICE_AGENT_SILENCE_DURATION` | `0.8` | Trailing silence seconds required to end capture |
| `VOICE_AGENT_MAX_CAPTURE_DURATION` | `30` | Maximum capture duration in seconds |

Pi tools and extensions remain an explicit allowlist decision; the daemon must not inherit an unrestricted interactive Pi configuration by accident.

## Provider boundaries

- `voice_agent.adapters.audio`: SoX-compatible capture and playback processes.
- `voice_agent.adapters.deepgram`: Deepgram STT contract with injectable streaming WebSocket transport and buffered HTTP fallback. The streaming path uses the optional `websocket-client` package and matches the existing Pi dictation settings.
- `voice_agent.adapters.kitten_tts`: lazy `kittenml.KittenTTS("KittenML/kitten-tts-2", weights="emb4")` loading with the model's `Spanish` voice selected by default.
- `voice_agent.conversation.pi_rpc`: persistent Pi child process with strict JSONL framing, readiness confirmation, `agent_settled` completion, and `clear_queue` + `abort` cancellation.

KittenTTS 2 model weights use the separate Stellon Labs Community License. This project currently targets personal, non-commercial use; review the exact model terms before redistribution, commercial use, or public hosting.

## Provider setup

The daemon keeps provider dependencies optional at import time. For the current local setup, install the runtime packages in the daemon environment and keep credentials outside the repository:

```bash
python -m pip install websocket-client kittenml
export DEEPGRAM_API_KEY=...
```

The audio adapter expects SoX (`rec` and `play`) or equivalent commands configured explicitly. KittenTTS 2 requires its model weights to be downloaded on first use; that operation should be performed deliberately, not during daemon import.

## Run as a user service

`deploy/voice-agent.service` provides a systemd user-unit template for this checkout. Create the credential environment file with restrictive permissions, then install and enable the unit:

```bash
install -d -m 700 "$HOME/.config/voice-agent"
printf 'DEEPGRAM_API_KEY=%s\n' "$DEEPGRAM_API_KEY" > "$HOME/.config/voice-agent/environment"
chmod 600 "$HOME/.config/voice-agent/environment"
mkdir -p "$HOME/.config/systemd/user"
cp deploy/voice-agent.service "$HOME/.config/systemd/user/voice-agent.service"
systemctl --user daemon-reload
systemctl --user enable --now voice-agent.service
systemctl --user status voice-agent.service
journalctl --user -u voice-agent.service -f
```

The unit restarts on failure, keeps the Unix socket and session state under the user account, and does not expose a network listener. Do not enable it until the `.venv`, Pi executable, provider credentials, and audio devices are ready.

## Checks

Pytest is not required for the current test slices. Run:

```bash
python -m unittest discover -s tests/daemon -p 'test_*.py' -v
python -m unittest discover -s tests/adapters -p 'test_*.py' -v
python -m unittest discover -s tests/conversation -p 'test_*.py' -v
python -m compileall -q voice_agent tests
python -m voice_agent --help
```

The ODD plan and task evidence live in [`odd/tasks/voice-agent.md`](odd/tasks/voice-agent.md).
