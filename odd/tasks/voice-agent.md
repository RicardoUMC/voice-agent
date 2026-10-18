# ODD plan: voice-agent
Status: MVP implementation complete; one external provider check remains intentionally skipped.
Scope: external persistent voice conversation daemon integrated with Pi through RPC.

## Specs

S1. User objective (verbatim):
> Objetivo: diseñar e implementar un daemon de conversación por voz que funcione independientemente de la interfaz de Pi. Debe conectar micrófono/STT → Pi mediante RPC → TTS → altavoces, seguir funcionando aunque se cierre la TUI y permitir cambiar proveedores o modelos sin rehacer la arquitectura.

S2. Initial architectural decisions (verbatim):
> - Usar un proceso externo persistente, no una extensión acoplada a Pi.
> - Usar Pi RPC como primer backend conversacional.
> - Usar KittenTTS como primer proveedor TTS.
> - Encapsular STT, TTS, audio y conversación detrás de adaptadores.
> - Empezar con una sesión de voz dedicada para evitar escrituras concurrentes sobre una misma sesión.
> - Diseñar desde el inicio para múltiples sesiones.
> - No usar MCP como dependencia central.
> - Priorizar configuración, seguridad local, cancelación, interrupciones y recuperación ante fallos.

S3. Planning gate (verbatim):
> No implementes hasta cerrar ese plan.

S4. Follow-up decisions and preferences (verbatim):
> Yo creo que sí, las sesiones sí deberían de sobrevivir a los reinicios del demon, y que además yo creo que para la plataforma de audio y backend inicial, usemos la que ahorita tenemos configurada dentro de Pi, que es la que ahorita yo he tenido más comodidad, más facilidad de uso, entonces estoy ya familiarizado con ella, me gusta. Yo creo que es la que vamos a estar utilizando inicialmente.
> 
> El runtime, modelo y licencia en no sé, yo creo que seguiré una recomendación que tú me des realmente,
> 
> ¿Y podríamos utilizar ahorita un único cliente local? No creo utilizarla en algún otro lado, a lo mejor desde el celular poder hacer puede ser que, si tú ves conveniente, ir preparando una API. Ya para poder utilizarlo desde varios clientes. Pero lo dejo a tu consideración, cualquiera de los 2 días me gusta. Siento que la API a lo mejor daría un poquito más de libertad, pero realmente lo dejo a tu consideración.

## Tasks

T1 | S1-S3 | Define architecture, adapter contracts, lifecycle/state model, security boundaries, and MVP acceptance criteria | plan | 552b6d5
T2 | S1-S3 | Implement daemon process, configuration, local control surface, and supervised lifecycle | implementation | ac93f9b, 560fa2e (b56f32b hygiene)
T3 | S1-S3 | Implement Pi RPC conversation adapter with dedicated-session serialization, streaming, cancellation, and recovery | implementation | a941bcc
T4 | S1-S2 | Implement audio/STT/TTS adapters with KittenTTS first and provider/model substitution points | implementation | 7b6084e, ccc7a06, e29f7ae
T5 | S1-S3 | Add multi-session model, observability, failure-path tests, and operational documentation | implementation | 15c83d1
T6 | S1-S4 | Verify MVP end to end and record unresolved platform/provider decisions | verification | e29f7ae plus final evidence; live generated-audio Deepgram path passed
T7 | S4 | Validate the KittenTTS model/runtime/weight license and Spanish voice quality before implementation lock-in | plan | research complete; runtime/quality validated in `.venv`
T8 | S1-S4 | Package operational startup, systemd user supervision, logs, and restart/recovery guidance | implementation | 0aec6cb, b5b81eb, 714138a, d26198a
T9 | S1-S4 | Add configurable silence endpointing and an explicit recording-stop protocol for live voice turns | implementation | 1aa1438, 30f83dc, 61be508, 6729144, a656712
T10 | S1-S4 | Add a local CLI client for sessions, text turns, voice turns, recording stop, and interruption | implementation | 26f3b5d
T11 | S1-S4 | Calibrate and document VAD settings using measured microphone noise | configuration | 428c2d3
T12 | S1-S4 | Add an installable CLI entry point for the daemon client | implementation | d94c206
T13 | S1-S4 | Make the Pi tool and extension allowlist explicit in daemon configuration | implementation | TBD

## Log

L1. User request (verbatim):
> Estamos retomando el proyecto voice-agent.
> 
> Primero recuperá el contexto desde Engram y revisá el repositorio actual. No escribas código todavía.
> 
> Objetivo: diseñar e implementar un daemon de conversación por voz que funcione independientemente de la interfaz de Pi. Debe conectar micrófono/STT → Pi mediante RPC → TTS
> → altavoces, seguir funcionando aunque se cierre la TUI y permitir cambiar proveedores o modelos sin rehacer la arquitectura.
> 
> Decisiones iniciales:
> - Usar un proceso externo persistente, no una extensión acoplada a Pi.
> - Usar Pi RPC como primer backend conversacional.
> - Usar KittenTTS como primer proveedor TTS.
> - Encapsular STT, TTS, audio y conversación detrás de adaptadores.
> - Empezar con una sesión de voz dedicada para evitar escrituras concurrentes sobre una misma sesión.
> - Diseñar desde el inicio para múltiples sesiones.
> - No usar MCP como dependencia central.
> - Priorizar configuración, seguridad local, cancelación, interrupciones y recuperación ante fallos.
> 
> Leé primero toda la documentación relevante de Pi y verificá el estado del repositorio. Después creá o reconciliá el documento de planificación ODD y presentame la
> arquitectura, los límites del MVP y las decisiones que todavía requieren confirmación. No implementes hasta cerrar ese plan.

L2. Product decision recorded: `Allowlist explícita` — habilitar únicamente herramientas/extensiones definidas en configuración; diseñar y validar esa allowlist antes de implementar.

L3. User follow-up (verbatim):
> Yo creo que sí, las sesiones sí deberían de sobrevivir a los reinicios del demon, y que además yo creo que para la plataforma de audio y backend inicial, usemos la que ahorita tenemos configurada dentro de Pi, que es la que ahorita yo he tenido más comodidad, más facilidad de uso, entonces estoy ya familiarizado con ella, me gusta. Yo creo que es la que vamos a estar utilizando inicialmente. El runtime, modelo y licencia en no sé, yo creo que seguiré una recomendación que tú me des realmente, ¿Y podríamos utilizar ahorita un único cliente local? No creo utilizarla en algún otro lado, a lo mejor desde el celular poder hacer puede ser que, si tú ves conveniente, ir preparando una API. Ya para poder utilizarlo desde varios clientes. Pero lo dejo a tu consideración, cualquiera de los 2 días me gusta. Siento que la API a lo mejor daría un poquito más de libertad, pero realmente lo dejo a tu consideración.

L4. Architecture recommendation recorded: implement a session-addressed local API from the start, bind it only to a Unix socket for the MVP, and keep the protocol transport-neutral so a future authenticated phone client can be added without redesigning the daemon. Deploy and test only one local client initially.

L5. Environment evidence: the current Pi dictation package uses Deepgram Nova-3 streaming with 16 kHz mono PCM captured through `rec`/SoX; this host has `rec`, `sox`, PipeWire capture/playback tools, and active microphone/sink devices. The daemon should reuse Deepgram as the initial STT backend while isolating capture/playback behind adapters.

L6. Product confirmation recorded: KittenTTS 2 with `emb4` CPU weights is accepted for the personal/non-commercial MVP, subject to validating Spanish voice quality and documenting the separate model license.

L7. Implementation evidence: commits `ac93f9b`, `7b6084e`, `a941bcc`, `b56f32b`, and `560fa2e` add the persistent session core, provider adapter boundaries, Pi RPC adapter, Python artifact hygiene, and local Unix-socket daemon service. Focused stdlib checks pass: daemon 11 tests, adapters 7 tests, conversation 4 tests, plus `compileall` and `python -m voice_agent --help`. Pytest is not installed.

L8. Integration evidence: `ccc7a06` adds injectable Deepgram streaming transport and `15c83d1` wires the cancellable voice pipeline into `voice_turn`, including persistent transcript/response storage, lifecycle events, redacted failures, and WAV-aware playback. Current checks pass: daemon 12 tests, adapters 9 tests, conversation 5 tests, voice pipeline 3 tests, `compileall`, and CLI help. Live provider validation is pending because `websocket-client` and `kittenml` were not installed at the time of this check; a project-local `.venv` installation is in progress.

L9. Final local provider evidence: `ea094b0` selects the installed KittenTTS `Spanish` voice after live validation rejected the previous `expr-voice-4-f` default. KittenTTS 2 `emb4` synthesis succeeded in the project `.venv`, producing a 24 kHz WAV with 81,120 frames. `websocket-client` 1.9.2, `kittenml` 0.9.4, VoiceDaemon provider wiring, all focused suites, compileall, CLI help, and Pi RPC readiness passed. A live Deepgram network/audio turn was intentionally not run; no external provider cost or credential use was added beyond local runtime setup.

L10. Authorized live STT evidence: `e29f7ae` fixes Deepgram WebSocket PCM metadata, streaming response shape, `Finalize`/`CloseStream` ordering, and realtime pacing. The full authorized path KittenTTS Spanish WAV -> ffmpeg 16 kHz mono PCM -> real Deepgram Nova-3 WebSocket returned non-empty Spanish text (`Hola, esta es una prueba real de la gente de voz.`). Recognition differed slightly from the source phrase (`agente`/`gente`), so this proves transport and provider operation, not word-perfect accuracy. Final focused checks pass: daemon 12, adapters 10, conversation 5, voice pipeline 3, compileall, CLI help, Pi readiness, and live TTS/STT.

L11. User continuation (verbatim):
> Vale, sigamos entonces

L12. Operational slice evidence: added `deploy/voice-agent.service`, README installation/logging guidance, and standard logging configuration in `python -m voice_agent`. Focused suites, compileall, CLI help, `systemd-analyze verify`, and `git diff --check` pass. The service was not enabled automatically; installation remains an explicit operator action.

L13. Live service evidence: after enabling the user unit, the first real `voice_turn` exposed a cancellation interface mismatch (`CancellationState` lacked `is_set`), fixed in `b5b81eb`. A second real capture verified interrupt behavior and exposed an uncaught cancellation traceback, fixed in `714138a`. The deployed daemon now returns `{"ok":false,"error":"voice turn cancelled during audio_input"}` cleanly and remains active. Full spoken microphone-to-Pi-to-TTS-to-speaker validation remains pending user speech during capture.

L14. User endpoint decision (verbatim):
> Ambos

L15. Endpointing implementation evidence: `1aa1438` adds PCM VAD with configurable trailing silence/max duration, `stop_recording` separate from `interrupt`, environment controls, README protocol/config documentation, and regression tests. All focused suites pass. The deployed systemd unit still needs restart before live endpointing validation.

L16. Live endpoint robustness evidence: `30f83dc` adds bounded polling around the SoX stdout file descriptor and checks `stop_requested` before reads, fixing a real idle-capture block that prevented endpoint control. Adapter 13, daemon 15, conversation 5, and pipeline 3 tests pass.

L17. Blocked-read evidence: `61be508` adds a watcher that terminates the SoX process when `stop_recording` or `interrupt` is requested, covering the case where `stdout.read` is already blocked. Adapter 14, daemon 15, conversation 5, and pipeline 3 tests pass. A fresh live full-turn validation remains pending deployment of this watcher.

L18. Capture cleanup evidence: `6729144` escalates capture cleanup from `terminate()` to `kill()` after a bounded wait because the real SoX process survived the first watcher. Adapter 14, daemon 15, conversation 5, and pipeline 3 tests pass. Deployment and live endpoint validation remain pending.

L19. Structured voice error evidence: `a656712` treats intentional capture termination as a normal endpoint and maps `VoiceTurnError` to a redacted JSONL error response. Adapter 14, daemon 16, conversation 5, and pipeline 3 tests pass. A fresh deployed live check remains pending.

L20. Live conversation diagnosis: Pi RPC readiness succeeded, but the selected `openai-codex/gpt-5.5` model returned `The 'gpt-5.5' model is not supported when using Codex with a ChatGPT account.` Direct RPC validation succeeded with `openai-codex/gpt-5.6-luna`; the user service environment was updated accordingly. A daemon text turn then returned `{"ok":true,"session_id":"voice-main","text":"hola"}`. README now records the model-selection requirement.

L21. Final live voice evidence: with the supervised service active, the configured supported model, Deepgram STT, and endpoint controls deployed, the full microphone -> Deepgram -> Pi RPC -> KittenTTS -> audio output turn completed successfully. The daemon returned `{"ok":true,"transcript":"Ok, probando 1, 2, 3, 4, 5, 6.","text":"Recibido."}`. This closes T8/T9 operational validation; VAD did not auto-end in the ambient-noise setup, but explicit `stop_recording` completed the same turn successfully.

L22. User continuation and CLI choice (verbatim):
> Vale, otra cosa. Relacionada al problema del modelo que tuvimos hace rato. ¿Hay alguna manera más sencilla de modificar mi perfil de modelos que no sea editar los archivos directamente?
> Vale, ya quedó, podemos regresar a lo que estábamos haciendo antes y continuar con lo del voice-agent
> 2. Crear cliente local CLI

L23. CLI evidence: `26f3b5d` adds `python -m voice_agent.client` with `sessions`, `status`, `turn`, `voice`, `stop`, and `interrupt`, JSON output, socket override, timeout, structured exit codes, README usage, and 3 client tests. Full prior suites remain green; live sessions/status probes returned the daemon's persistent session list.

L24. User requested the remaining improvements sequentially through item 3 (verbatim):
> Vale, sigamos uno po uno hasta el punto 3 porfa

L25. Improvement evidence: VAD ambient measurement was peak 95/RMS 37.5; `VOICE_AGENT_SILENCE_THRESHOLD=250`, `VOICE_AGENT_SILENCE_DURATION=0.8`, and related values were applied to the user service and verified in the running process. `d94c206` adds editable packaging and `voice-agent`/`voice-agent-client` entry points. The allowlist implementation emits `--tools read,grep,find` by default or `--no-tools` when empty, parses `VOICE_AGENT_PI_TOOLS`, documents extension behavior, and the restarted service reports `VOICE_AGENT_PI_TOOLS=read,grep,find` while serving sessions.
