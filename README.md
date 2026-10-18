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
```

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

Pi tools and extensions remain an explicit allowlist decision; the daemon must not inherit an unrestricted interactive Pi configuration by accident.

## Provider boundaries

- `voice_agent.adapters.audio`: SoX-compatible capture and playback processes.
- `voice_agent.adapters.deepgram`: Deepgram STT contract with injectable streaming WebSocket transport and buffered HTTP fallback. The streaming path uses the optional `websocket-client` package and matches the existing Pi dictation settings.
- `voice_agent.adapters.kitten_tts`: lazy `kittenml.KittenTTS("KittenML/kitten-tts-2", weights="emb4")` loading.
- `voice_agent.conversation.pi_rpc`: persistent Pi child process with strict JSONL framing, readiness confirmation, `agent_settled` completion, and `clear_queue` + `abort` cancellation.

KittenTTS 2 model weights use the separate Stellon Labs Community License. This project currently targets personal, non-commercial use; review the exact model terms before redistribution, commercial use, or public hosting.

## Provider setup

The daemon keeps provider dependencies optional at import time. For the current local setup, install the runtime packages in the daemon environment and keep credentials outside the repository:

```bash
python -m pip install websocket-client kittenml
export DEEPGRAM_API_KEY=...
```

The audio adapter expects SoX (`rec` and `play`) or equivalent commands configured explicitly. KittenTTS 2 requires its model weights to be downloaded on first use; that operation should be performed deliberately, not during daemon import.

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
